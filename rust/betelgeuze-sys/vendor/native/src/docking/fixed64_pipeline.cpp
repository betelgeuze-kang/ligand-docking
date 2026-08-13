#include "../dynamics/sha256.hpp"
#include "../internal.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <vector>

namespace betelgeuze::native::docking::fixed64_pipeline {
namespace {

using dynamics::Sha256;

constexpr std::size_t kCandidateCount = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kMovesPerCandidate = BG_DOCKING_TORSION_V7_MAX_MOVES;
constexpr char kProfileId[] =
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0";
constexpr char kProfileIdV2[] =
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0";
constexpr char kAdmissionContextSchema[] =
    "betelgeuze.engine_v2_native_fixed64_admission_context/1.0.0";
constexpr char kRefinementContextSchema[] =
    "betelgeuze.engine_v2_native_fixed64_refinement_context/1.0.0";
constexpr char kScorerContextSchema[] =
    "betelgeuze.engine_v2_native_fixed64_scorer_context/1.0.0";
constexpr char kValidityContextSchema[] =
    "betelgeuze.engine_v2_native_fixed64_validity_context/1.0.0";
constexpr char kComponentBindingSchema[] =
    "betelgeuze.engine_v2_native_fixed64_component_binding/1.0.0";
constexpr char kPolicySchema[] =
    "betelgeuze.engine_v2_native_fixed64_refinement_policy_receipt/1.0.0";
constexpr char kRefinementEvidenceSchema[] =
    "betelgeuze.engine_v2_native_fixed64_refinement_evidence/1.0.0";
constexpr char kScorerEvidenceSchema[] =
    "betelgeuze.engine_v2_native_fixed64_scorer_evidence/1.0.0";
constexpr char kValidityEvidenceSchema[] =
    "betelgeuze.engine_v2_native_fixed64_validity_evidence/1.0.0";
constexpr char kRankingEvidenceSchema[] =
    "betelgeuze.engine_v2_native_fixed64_ranking_evidence/1.0.0";
constexpr char kClusterEvidenceSchema[] =
    "betelgeuze.engine_v2_native_fixed64_cluster_evidence/1.0.0";
constexpr char kRowSchema[] =
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline_row/1.0.0";
constexpr char kBatchSchema[] =
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline_batch/1.0.0";
constexpr char kPostAdmissionPolicySchemaV2[] =
    "betelgeuze.engine_v2_native_fixed64_post_admission_policy_receipt/2.0.0";
constexpr char kRowSchemaV2[] =
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline_row/2.0.0";
constexpr char kBatchSchemaV2[] =
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline_batch/2.0.0";

struct MemoryRange final {
    uintptr_t begin = 0;
    uintptr_t end = 0;
};

class CanonicalHash final {
  public:
    explicit CanonicalHash(const char *domain) noexcept { string(domain); }

    void byte(uint8_t value) noexcept { hash_.update(&value, 1); }

    void u32(uint32_t value) noexcept {
        std::array<uint8_t, 4> bytes{};
        for (std::size_t index = 0; index < bytes.size(); ++index) {
            bytes[bytes.size() - 1U - index] = static_cast<uint8_t>(
                value >> static_cast<uint32_t>(index * 8U));
        }
        hash_.update(bytes.data(), bytes.size());
    }

    void i32(int32_t value) noexcept { u32(static_cast<uint32_t>(value)); }

    void u64(uint64_t value) noexcept {
        std::array<uint8_t, 8> bytes{};
        for (std::size_t index = 0; index < bytes.size(); ++index) {
            bytes[bytes.size() - 1U - index] = static_cast<uint8_t>(
                value >> static_cast<uint32_t>(index * 8U));
        }
        hash_.update(bytes.data(), bytes.size());
    }

    void size(std::size_t value) noexcept { u64(static_cast<uint64_t>(value)); }

    void f64(double value) noexcept {
        if (value == 0.0) value = 0.0;
        uint64_t bits = 0;
        static_assert(sizeof(bits) == sizeof(value));
        std::memcpy(&bits, &value, sizeof(bits));
        u64(bits);
    }

    void bytes(const uint8_t *values, std::size_t count) noexcept {
        size(count);
        hash_.update(values, count);
    }

    void string(const char *value) noexcept {
        bytes(reinterpret_cast<const uint8_t *>(value), std::strlen(value));
    }

    void digest(const uint8_t (&value)[32]) noexcept {
        hash_.update(value, 32);
    }

    void digest(const std::array<uint8_t, 32> &value) noexcept {
        hash_.update(value.data(), value.size());
    }

    [[nodiscard]] std::array<uint8_t, 32> finish() noexcept {
        return hash_.finish();
    }

  private:
    Sha256 hash_;
};

template <typename Type>
[[nodiscard]] bool make_range(
    const Type *pointer,
    std::size_t count,
    MemoryRange *output) noexcept {
    if (output == nullptr) return false;
    if (pointer == nullptr || count == 0) {
        *output = {};
        return true;
    }
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(Type)) {
        return false;
    }
    const std::size_t bytes = count * sizeof(Type);
    const uintptr_t begin = reinterpret_cast<uintptr_t>(pointer);
    if (begin > std::numeric_limits<uintptr_t>::max() - bytes) return false;
    *output = {begin, begin + bytes};
    return true;
}

[[nodiscard]] bool overlaps(MemoryRange left, MemoryRange right) noexcept {
    return left.begin != left.end && right.begin != right.end &&
           left.begin < right.end && right.begin < left.end;
}

template <typename Type>
[[nodiscard]] bg_status append_range(
    std::vector<MemoryRange> *ranges,
    const Type *pointer,
    std::size_t count,
    const char *message) {
    MemoryRange range{};
    if (!make_range(pointer, count, &range)) {
        return fail(BG_STATUS_CAPACITY_OVERFLOW, message);
    }
    if (range.begin != range.end) ranges->push_back(range);
    return BG_STATUS_OK;
}

[[nodiscard]] bool digest_present(const uint8_t (&digest)[32]) noexcept {
    return std::any_of(
        std::begin(digest), std::end(digest),
        [](uint8_t value) { return value != UINT8_C(0); });
}

[[nodiscard]] bool same_digest(
    const std::array<uint8_t, 32> &left,
    const uint8_t (&right)[32]) noexcept {
    return std::memcmp(left.data(), right, left.size()) == 0;
}

[[nodiscard]] bool same_digest(
    const uint8_t (&left)[32],
    const uint8_t (&right)[32]) noexcept {
    return std::memcmp(left, right, 32) == 0;
}

[[nodiscard]] bool channels_equal(
    const double *left,
    const double *right,
    std::size_t count) noexcept {
    if (left == nullptr || right == nullptr) return false;
    for (std::size_t index = 0; index < count; ++index) {
        if (left[index] != right[index]) return false;
    }
    return true;
}

[[nodiscard]] bool valid_requested_mode(
    bg_docking_rigid_refinement_candidate_mode mode) noexcept {
    return mode == BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION ||
           mode ==
               BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION ||
           mode ==
               BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE ||
           mode ==
               BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
}

[[nodiscard]] bg_status validate_created_binding(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_refinement_pipeline_v1 &refinement,
    const bg_docking_scorer_v1_context_soa_v1 &scorer,
    const bg_docking_pose_validity_context_soa_v1 &validity) noexcept {
    if (context.backend != admission.backend ||
        context.backend != refinement.backend ||
        context.unit_system != admission.unit_system ||
        context.unit_system != refinement.unit_system ||
        context.device_ordinal != admission.device_ordinal ||
        context.device_ordinal != refinement.device_ordinal ||
        admission.receptor_atom_count != scorer.receptor_atom_count ||
        admission.ligand_atom_count != scorer.ligand_atom_count ||
        refinement.ligand_atom_count != scorer.ligand_atom_count ||
        scorer.receptor_atom_count == 0 || scorer.ligand_atom_count == 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline component denominators or backend binding are cross-wired");
    }
    const auto receptor_count =
        static_cast<std::size_t>(scorer.receptor_atom_count);
    const auto ligand_count = static_cast<std::size_t>(scorer.ligand_atom_count);
    if (!channels_equal(
            admission.receptor_x_angstrom.data(),
            scorer.receptor_x_angstrom,
            receptor_count) ||
        !channels_equal(
            admission.receptor_y_angstrom.data(),
            scorer.receptor_y_angstrom,
            receptor_count) ||
        !channels_equal(
            admission.receptor_z_angstrom.data(),
            scorer.receptor_z_angstrom,
            receptor_count) ||
        !channels_equal(
            admission.receptor_vdw_radius_angstrom.data(),
            scorer.receptor_vdw_radius_angstrom,
            receptor_count) ||
        !channels_equal(
            admission.ligand_vdw_radius_angstrom.data(),
            scorer.ligand_vdw_radius_angstrom,
            ligand_count) ||
        !channels_equal(
            admission.pocket_center_angstrom.data(),
            scorer.pocket_center_angstrom,
            3) ||
        admission.pocket_radius_angstrom != scorer.pocket_radius_angstrom ||
        !same_digest(
            admission.authority_input_receipt_sha256,
            scorer.authority_input_receipt_sha256) ||
        !same_digest(
            admission.receptor_system_sha256,
            scorer.receptor_system_sha256) ||
        !same_digest(
            admission.ligand_system_sha256,
            scorer.ligand_system_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline admission and refinement identities are cross-wired");
    }
    if (!channels_equal(
            validity.receptor_x_angstrom,
            scorer.receptor_x_angstrom,
            receptor_count) ||
        !channels_equal(
            validity.receptor_y_angstrom,
            scorer.receptor_y_angstrom,
            receptor_count) ||
        !channels_equal(
            validity.receptor_z_angstrom,
            scorer.receptor_z_angstrom,
            receptor_count) ||
        !channels_equal(
            validity.receptor_vdw_radius_angstrom,
            scorer.receptor_vdw_radius_angstrom,
            receptor_count) ||
        !channels_equal(
            validity.ligand_reference_x_angstrom,
            scorer.ligand_reference_x_angstrom,
            ligand_count) ||
        !channels_equal(
            validity.ligand_reference_y_angstrom,
            scorer.ligand_reference_y_angstrom,
            ligand_count) ||
        !channels_equal(
            validity.ligand_reference_z_angstrom,
            scorer.ligand_reference_z_angstrom,
            ligand_count) ||
        !channels_equal(
            validity.pocket_center_angstrom,
            scorer.pocket_center_angstrom,
            3) ||
        !same_digest(
            validity.authority_input_receipt_sha256,
            scorer.authority_input_receipt_sha256) ||
        !same_digest(
            validity.receptor_system_sha256,
            scorer.receptor_system_sha256) ||
        !same_digest(
            validity.ligand_system_sha256,
            scorer.ligand_system_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline validity molecular identity is cross-wired");
    }
    return BG_STATUS_OK;
}

template <typename Type>
[[nodiscard]] bg_status append_u64_range(
    std::vector<MemoryRange> *ranges,
    const Type *pointer,
    uint64_t count,
    const char *message) {
    if (count > static_cast<uint64_t>(
                    std::numeric_limits<std::size_t>::max())) {
        return fail(BG_STATUS_CAPACITY_OVERFLOW, message);
    }
    return append_range(
        ranges, pointer, static_cast<std::size_t>(count), message);
}

[[nodiscard]] bg_status validate_create_output_overlap(
    const bg_context &context,
    const bg_docking_geometric_admission_context_soa_v1 &admission,
    const bg_docking_rigid_refinement_context_soa_v1 &rigid,
    const bg_docking_torsion_v7_context_soa_v1 &torsion,
    const bg_docking_scorer_v1_context_soa_v1 &scorer,
    const bg_docking_pose_validity_context_soa_v1 &validity,
    bg_docking_fixed64_pipeline_v1 **out_pipeline) {
    std::vector<MemoryRange> inputs;
    inputs.reserve(72);
    bg_status status = BG_STATUS_OK;
#define BG_APPEND_CREATE(pointer, count, message)                            \
    do {                                                                     \
        status = append_u64_range(                                           \
            &inputs, (pointer), static_cast<uint64_t>(count), (message));    \
        if (status != BG_STATUS_OK) return status;                           \
    } while (false)
    BG_APPEND_CREATE(&context, 1, "complete pipeline context range overflows");
    BG_APPEND_CREATE(&admission, 1, "complete pipeline admission range overflows");
    BG_APPEND_CREATE(&rigid, 1, "complete pipeline rigid range overflows");
    BG_APPEND_CREATE(&torsion, 1, "complete pipeline torsion range overflows");
    BG_APPEND_CREATE(&scorer, 1, "complete pipeline scorer range overflows");
    BG_APPEND_CREATE(&validity, 1, "complete pipeline validity range overflows");

    for (const double *channel : {
             admission.receptor_x_angstrom,
             admission.receptor_y_angstrom,
             admission.receptor_z_angstrom,
             admission.receptor_vdw_radius_angstrom}) {
        BG_APPEND_CREATE(
            channel,
            admission.receptor_atom_count,
            "complete pipeline admission receptor channel overflows");
    }
    BG_APPEND_CREATE(
        admission.ligand_vdw_radius_angstrom,
        admission.ligand_atom_count,
        "complete pipeline admission ligand radii overflow");
    BG_APPEND_CREATE(
        admission.ligand_heavy_atom_mask,
        admission.ligand_atom_count,
        "complete pipeline admission heavy-mask overflow");

    for (const double *channel : {
             rigid.receptor_x_angstrom,
             rigid.receptor_y_angstrom,
             rigid.receptor_z_angstrom,
             rigid.receptor_vdw_radius_angstrom}) {
        BG_APPEND_CREATE(
            channel,
            rigid.receptor_atom_count,
            "complete pipeline rigid receptor channel overflows");
    }
    BG_APPEND_CREATE(
        rigid.ligand_vdw_radius_angstrom,
        rigid.ligand_atom_count,
        "complete pipeline rigid ligand radii overflow");

    for (const double *channel : {
             torsion.receptor_x_angstrom,
             torsion.receptor_y_angstrom,
             torsion.receptor_z_angstrom,
             torsion.receptor_vdw_radius_angstrom}) {
        BG_APPEND_CREATE(
            channel,
            torsion.receptor_atom_count,
            "complete pipeline torsion receptor channel overflows");
    }
    BG_APPEND_CREATE(
        torsion.ligand_vdw_radius_angstrom,
        torsion.ligand_atom_count,
        "complete pipeline torsion ligand radii overflow");
    BG_APPEND_CREATE(
        torsion.parent_atom_index,
        torsion.ligand_atom_count,
        "complete pipeline torsion parent channel overflows");
    BG_APPEND_CREATE(
        torsion.rotatable_child_atom_index,
        torsion.rotor_count,
        "complete pipeline torsion rotor channel overflows");
    BG_APPEND_CREATE(
        torsion.internal_pair_atom_i,
        torsion.internal_pair_count,
        "complete pipeline torsion internal-i channel overflows");
    BG_APPEND_CREATE(
        torsion.internal_pair_atom_j,
        torsion.internal_pair_count,
        "complete pipeline torsion internal-j channel overflows");

    for (const double *channel : {
             scorer.receptor_x_angstrom,
             scorer.receptor_y_angstrom,
             scorer.receptor_z_angstrom,
             scorer.receptor_charge_elementary,
             scorer.receptor_vdw_radius_angstrom,
             scorer.receptor_epsilon_kcal_per_mol}) {
        BG_APPEND_CREATE(
            channel,
            scorer.receptor_atom_count,
            "complete pipeline scorer receptor channel overflows");
    }
    BG_APPEND_CREATE(
        scorer.receptor_hydrophobic,
        scorer.receptor_atom_count,
        "complete pipeline scorer receptor hydrophobic channel overflows");
    BG_APPEND_CREATE(
        scorer.receptor_acceptor,
        scorer.receptor_atom_count,
        "complete pipeline scorer receptor acceptor channel overflows");
    for (const double *channel : {
             scorer.ligand_reference_x_angstrom,
             scorer.ligand_reference_y_angstrom,
             scorer.ligand_reference_z_angstrom,
             scorer.ligand_charge_elementary,
             scorer.ligand_vdw_radius_angstrom,
             scorer.ligand_epsilon_kcal_per_mol}) {
        BG_APPEND_CREATE(
            channel,
            scorer.ligand_atom_count,
            "complete pipeline scorer ligand channel overflows");
    }
    BG_APPEND_CREATE(
        scorer.ligand_hydrophobic,
        scorer.ligand_atom_count,
        "complete pipeline scorer ligand hydrophobic channel overflows");
    BG_APPEND_CREATE(
        scorer.ligand_acceptor,
        scorer.ligand_atom_count,
        "complete pipeline scorer ligand acceptor channel overflows");
    for (const uint64_t *channel : {
             scorer.receptor_donor_atom_index,
             scorer.receptor_hydrogen_atom_index}) {
        BG_APPEND_CREATE(
            channel,
            scorer.receptor_donor_count,
            "complete pipeline scorer receptor donor channel overflows");
    }
    for (const uint64_t *channel : {
             scorer.ligand_donor_atom_index,
             scorer.ligand_hydrogen_atom_index}) {
        BG_APPEND_CREATE(
            channel,
            scorer.ligand_donor_count,
            "complete pipeline scorer ligand donor channel overflows");
    }
    for (const uint64_t *channel : {
             scorer.ligand_exclusion_atom_i,
             scorer.ligand_exclusion_atom_j}) {
        BG_APPEND_CREATE(
            channel,
            scorer.ligand_exclusion_count,
            "complete pipeline scorer exclusion channel overflows");
    }
    for (const uint64_t *channel : {
             scorer.rotor_atom_i,
             scorer.rotor_atom_j,
             scorer.rotor_atom_k,
             scorer.rotor_atom_l}) {
        BG_APPEND_CREATE(
            channel,
            scorer.rotor_count,
            "complete pipeline scorer rotor channel overflows");
    }

    for (const double *channel : {
             validity.receptor_x_angstrom,
             validity.receptor_y_angstrom,
             validity.receptor_z_angstrom,
             validity.receptor_vdw_radius_angstrom}) {
        BG_APPEND_CREATE(
            channel,
            validity.receptor_atom_count,
            "complete pipeline validity receptor channel overflows");
    }
    for (const double *channel : {
             validity.ligand_reference_x_angstrom,
             validity.ligand_reference_y_angstrom,
             validity.ligand_reference_z_angstrom,
             validity.ligand_vdw_radius_angstrom}) {
        BG_APPEND_CREATE(
            channel,
            validity.ligand_atom_count,
            "complete pipeline validity ligand channel overflows");
    }
    for (const uint64_t *channel : {
             validity.bond_atom_i,
             validity.bond_atom_j}) {
        BG_APPEND_CREATE(
            channel,
            validity.bond_count,
            "complete pipeline validity bond channel overflows");
    }
    for (const uint64_t *channel : {
             validity.ligand_exclusion_atom_i,
             validity.ligand_exclusion_atom_j}) {
        BG_APPEND_CREATE(
            channel,
            validity.ligand_exclusion_count,
            "complete pipeline validity exclusion channel overflows");
    }
    for (const uint64_t *channel : {
             validity.chirality_center_atom,
             validity.chirality_atom_i,
             validity.chirality_atom_j,
             validity.chirality_atom_k}) {
        BG_APPEND_CREATE(
            channel,
            validity.chirality_center_count,
            "complete pipeline validity chirality channel overflows");
    }
#undef BG_APPEND_CREATE
    MemoryRange output{};
    if (!make_range(out_pipeline, 1, &output)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "complete pipeline handle output range overflows");
    }
    for (MemoryRange input : inputs) {
        if (overlaps(output, input)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "complete pipeline handle output overlaps a create input");
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_input(
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    const bg_docking_fixed64_pipeline_input_v1 &input,
    std::size_t *coordinate_count) noexcept {
    bg_status status = validate_descriptor_header(
        input.struct_size,
        sizeof(input),
        input.abi_version,
        "fixed64 complete pipeline input size does not match ABI v1",
        "fixed64 complete pipeline input ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (input.producer_input == nullptr ||
        !pointer_is_aligned(input.producer_input) ||
        !std::isfinite(input.rmsd_threshold_angstrom) ||
        input.rmsd_threshold_angstrom <= 0.0 ||
        !digest_present(input.predeclared_refinement_policy_sha256) ||
        !reserved_is_zero(input.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline input descriptor is invalid");
    }
    status = validate_descriptor_header(
        input.producer_input->struct_size,
        sizeof(*input.producer_input),
        input.producer_input->abi_version,
        "fixed64 complete pipeline producer input size does not match ABI v1",
        "fixed64 complete pipeline producer input ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (input.producer_input->allocation_input == nullptr ||
        !pointer_is_aligned(input.producer_input->allocation_input)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline producer allocation is null or misaligned");
    }
    const auto &allocation = *input.producer_input->allocation_input;
    status = validate_descriptor_header(
        allocation.struct_size,
        sizeof(allocation),
        allocation.abi_version,
        "fixed64 complete pipeline allocation size does not match ABI v1",
        "fixed64 complete pipeline allocation ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (!same_digest(
            pipeline.admission->ligand_system_sha256,
            allocation.exact_v11_source.prepared_ligand_topology_sha256) ||
        !same_digest(
            pipeline.admission->receptor_system_sha256,
            allocation.exact_v11_source.prepared_receptor_topology_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline producer topology identity is cross-wired");
    }
    const std::array<const void *, 5> channels = {
        input.candidate_mode,
        input.rigid_max_steps,
        input.proposal_is_torsion_eligible,
        input.torsion_max_steps,
        input.baseline_torsion_angles_radians,
    };
    if (std::any_of(channels.begin(), channels.end(), [](const void *pointer) {
            return pointer == nullptr;
        }) ||
        !pointer_is_aligned(input.candidate_mode) ||
        !pointer_is_aligned(input.rigid_max_steps) ||
        !pointer_is_aligned(input.proposal_is_torsion_eligible) ||
        !pointer_is_aligned(input.torsion_max_steps) ||
        !pointer_is_aligned(input.baseline_torsion_angles_radians)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline policy channels are null or misaligned");
    }
    if (pipeline.ligand_atom_count >
        std::numeric_limits<std::size_t>::max() / kCandidateCount) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 complete pipeline coordinate denominator overflows");
    }
    *coordinate_count =
        static_cast<std::size_t>(pipeline.ligand_atom_count) * kCandidateCount;
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        if (!valid_requested_mode(input.candidate_mode[slot]) ||
            input.proposal_is_torsion_eligible[slot] > UINT8_C(1)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline policy row is not predeclared");
        }
    }
    for (std::size_t index = 0; index < *coordinate_count; ++index) {
        const double angle = input.baseline_torsion_angles_radians[index];
        if (!std::isfinite(angle)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline torsion baseline is non-finite");
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_output(
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    bg_docking_fixed64_pipeline_output_v1 &output) noexcept {
    bg_status status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "fixed64 complete pipeline output size does not match ABI v1",
        "fixed64 complete pipeline output ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (output.row_capacity < kCandidateCount || output.rows == nullptr ||
        !pointer_is_aligned(output.rows)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "fixed64 complete pipeline output requires 64 aligned rows");
    }
    if (output.unit_system != pipeline.unit_system ||
        output.result_dependent_input_consumed != UINT8_C(0) ||
        output.fallback_allowed != UINT8_C(0) ||
        output.denominator_preserved > UINT8_C(1) ||
        output.molecular_execution_authorized != UINT8_C(0) ||
        output.reservation_authorized != UINT8_C(0) ||
        output.benchmark_execution_authorized != UINT8_C(0) ||
        output.existing_rank_auto_change_authorized != UINT8_C(0) ||
        output.customer_pose_emission_authorized != UINT8_C(0) ||
        output.production_claim_authorized != UINT8_C(0) ||
        output.scientific_claim_authorized != UINT8_C(0) ||
        !std::all_of(
            std::begin(output.reserved0),
            std::end(output.reserved0),
            [](uint8_t value) { return value == UINT8_C(0); }) ||
        !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline output authority or reserved fields are invalid");
    }
    return BG_STATUS_OK;
}

void make_v1_input_view(
    const bg_docking_fixed64_pipeline_input_v2 &input,
    bg_docking_fixed64_pipeline_input_v1 *view) noexcept {
    *view = {};
    view->struct_size = sizeof(*view);
    view->abi_version = BG_ABI_VERSION;
    view->producer_input = input.producer_input;
    view->rmsd_threshold_angstrom = input.rmsd_threshold_angstrom;
    view->candidate_mode = input.candidate_mode;
    view->rigid_max_steps = input.rigid_max_steps;
    view->proposal_is_torsion_eligible = input.proposal_is_torsion_eligible;
    view->torsion_max_steps = input.torsion_max_steps;
    view->baseline_torsion_angles_radians =
        input.baseline_torsion_angles_radians;
    std::copy_n(
        input.predeclared_refinement_policy_sha256,
        32,
        view->predeclared_refinement_policy_sha256);
}

[[nodiscard]] bg_status validate_input_v2(
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    const bg_docking_fixed64_pipeline_input_v2 &input,
    std::size_t *coordinate_count,
    bg_docking_fixed64_pipeline_input_v1 *view) noexcept {
    bg_status status = validate_descriptor_header(
        input.struct_size,
        sizeof(input),
        input.abi_version,
        "fixed64 complete pipeline input size does not match ABI v2",
        "fixed64 complete pipeline input ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (!digest_present(
            input.predeclared_post_refinement_admission_policy_sha256) ||
        !reserved_is_zero(input.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline v2 post-admission policy is absent or reserved fields are non-zero");
    }
    make_v1_input_view(input, view);
    return validate_input(pipeline, *view, coordinate_count);
}

[[nodiscard]] bg_status validate_output_v2(
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    bg_docking_fixed64_pipeline_output_v2 &output) noexcept {
    bg_status status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "fixed64 complete pipeline output size does not match ABI v2",
        "fixed64 complete pipeline output ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (output.row_capacity < kCandidateCount || output.rows == nullptr ||
        !pointer_is_aligned(output.rows)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "fixed64 complete pipeline v2 output requires 64 aligned rows");
    }
    if (output.unit_system != pipeline.unit_system ||
        output.result_dependent_input_consumed != UINT8_C(0) ||
        output.fallback_allowed != UINT8_C(0) ||
        output.denominator_preserved > UINT8_C(1) ||
        output.molecular_execution_authorized != UINT8_C(0) ||
        output.reservation_authorized != UINT8_C(0) ||
        output.benchmark_execution_authorized != UINT8_C(0) ||
        output.existing_rank_auto_change_authorized != UINT8_C(0) ||
        output.customer_pose_emission_authorized != UINT8_C(0) ||
        output.production_claim_authorized != UINT8_C(0) ||
        output.scientific_claim_authorized != UINT8_C(0) ||
        !std::all_of(
            std::begin(output.reserved1),
            std::end(output.reserved1),
            [](uint8_t value) { return value == UINT8_C(0); }) ||
        !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 complete pipeline v2 output authority or reserved fields are invalid");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_post_admission_output(
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    bg_docking_geometric_admission_output_v1 &output) noexcept {
    bg_status status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "fixed64 post-admission output size does not match ABI v1",
        "fixed64 post-admission output ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (output.row_capacity < kCandidateCount || output.rows == nullptr ||
        !pointer_is_aligned(output.rows)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "fixed64 post-admission output requires 64 aligned rows");
    }
    if (output.unit_system != pipeline.unit_system || output.reserved0 != 0 ||
        output.molecular_execution_authorized != UINT8_C(0) ||
        output.reservation_authorized != UINT8_C(0) ||
        output.benchmark_execution_authorized != UINT8_C(0) ||
        output.existing_rank_auto_change_authorized != UINT8_C(0) ||
        output.customer_pose_emission_authorized != UINT8_C(0) ||
        output.production_claim_authorized != UINT8_C(0) ||
        output.scientific_claim_authorized != UINT8_C(0) ||
        output.reserved1 != UINT8_C(0)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 post-admission output units, authority, or reserved fields are invalid");
    }
    return BG_STATUS_OK;
}

void hash_rigid_evidence_value(
    CanonicalHash *hash,
    const bg_docking_rigid_refinement_evidence_v1 &value) noexcept {
    hash->i32(value.profile);
    hash->byte(value.available);
    hash->u64(value.accepted_steps);
    hash->u64(value.accepted_translation_steps);
    hash->u64(value.accepted_rotation_steps);
    hash->u64(value.line_search_evaluation_count);
    hash->u64(value.fallback_direction_step_count);
    hash->f64(value.initial_penalty);
    hash->f64(value.final_penalty);
    for (double component : value.total_translation_angstrom) hash->f64(component);
    for (double component : value.total_rotation_vector_radians) hash->f64(component);
    hash->f64(value.total_rotation_path_radians);
    hash->f64(value.initial_centroid_offset_angstrom);
    hash->f64(value.final_centroid_offset_angstrom);
    hash->f64(value.maximum_centroid_offset_angstrom);
}

void hash_coordinate_triplet(
    CanonicalHash *hash,
    const double *x,
    const double *y,
    const double *z,
    std::size_t offset,
    std::size_t count) noexcept {
    hash->size(count);
    for (std::size_t index = 0; index < count; ++index) {
        hash->f64(x[offset + index]);
        hash->f64(y[offset + index]);
        hash->f64(z[offset + index]);
    }
}

void hash_scalar_channel(
    CanonicalHash *hash,
    const double *values,
    std::size_t offset,
    std::size_t count) noexcept {
    hash->size(count);
    for (std::size_t index = 0; index < count; ++index) {
        hash->f64(values[offset + index]);
    }
}

void hash_double_channel(
    CanonicalHash *hash,
    const double *values,
    std::size_t count) noexcept {
    hash_scalar_channel(hash, values, 0, count);
}

void hash_u64_channel(
    CanonicalHash *hash,
    const uint64_t *values,
    std::size_t count) noexcept {
    hash->size(count);
    for (std::size_t index = 0; index < count; ++index) {
        hash->u64(values[index]);
    }
}

void hash_i32_channel(
    CanonicalHash *hash,
    const int32_t *values,
    std::size_t count) noexcept {
    hash->size(count);
    for (std::size_t index = 0; index < count; ++index) {
        hash->i32(values[index]);
    }
}

void hash_u8_channel(
    CanonicalHash *hash,
    const uint8_t *values,
    std::size_t count) noexcept {
    hash->size(count);
    for (std::size_t index = 0; index < count; ++index) {
        hash->byte(values[index]);
    }
}

void hash_rigid_v2_config(
    CanonicalHash *hash,
    const bg_docking_rigid_v2_config_v1 &config) noexcept {
    hash->f64(config.overlap_scale);
    hash->f64(config.maximum_step_angstrom);
    hash->f64(config.minimum_step_angstrom);
    hash->f64(config.maximum_total_translation_angstrom);
    hash->u64(config.maximum_backtracking_evaluations);
    hash->f64(config.penalty_tolerance);
    hash->f64(config.epsilon_angstrom);
}

void hash_rigid_v3_config(
    CanonicalHash *hash,
    const bg_docking_rigid_v3_config_v1 &config) noexcept {
    hash_rigid_v2_config(hash, config.v2);
    hash->f64(config.maximum_rotation_step_radians);
    hash->f64(config.minimum_rotation_step_radians);
    hash->f64(config.maximum_total_rotation_radians);
    hash->u64(config.maximum_rotation_steps);
    hash->f64(config.minimum_rotation_relative_penalty_reduction);
    hash->f64(config.maximum_centroid_offset_angstrom);
}

[[nodiscard]] std::array<uint8_t, 32> admission_context_receipt(
    const bg_context &context,
    const bg_docking_geometric_admission_context_soa_v1 &descriptor) noexcept {
    const auto receptor_count =
        static_cast<std::size_t>(descriptor.receptor_atom_count);
    const auto ligand_count =
        static_cast<std::size_t>(descriptor.ligand_atom_count);
    CanonicalHash hash(kAdmissionContextSchema);
    hash.i32(context.backend);
    hash.i32(context.unit_system);
    hash.i32(context.device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    hash_double_channel(&hash, descriptor.receptor_x_angstrom, receptor_count);
    hash_double_channel(&hash, descriptor.receptor_y_angstrom, receptor_count);
    hash_double_channel(&hash, descriptor.receptor_z_angstrom, receptor_count);
    hash_double_channel(
        &hash, descriptor.receptor_vdw_radius_angstrom, receptor_count);
    hash_double_channel(
        &hash, descriptor.ligand_vdw_radius_angstrom, ligand_count);
    hash_u8_channel(
        &hash, descriptor.ligand_heavy_atom_mask, ligand_count);
    hash_double_channel(&hash, descriptor.pocket_center_angstrom, 3);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash.f64(descriptor.hard_rejection_minimum_vdw_ratio);
    hash.u64(descriptor.max_batch_exact_pair_evaluations);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> refinement_context_receipt(
    const bg_context &context,
    const bg_docking_rigid_refinement_context_soa_v1 &rigid,
    const bg_docking_torsion_v7_context_soa_v1 &torsion) noexcept {
    const auto receptor_count =
        static_cast<std::size_t>(rigid.receptor_atom_count);
    const auto ligand_count =
        static_cast<std::size_t>(rigid.ligand_atom_count);
    CanonicalHash hash(kRefinementContextSchema);
    hash.i32(context.backend);
    hash.i32(context.unit_system);
    hash.i32(context.device_ordinal);
    hash.i32(rigid.unit_system);
    hash.u64(rigid.receptor_atom_count);
    hash.u64(rigid.ligand_atom_count);
    hash_double_channel(&hash, rigid.receptor_x_angstrom, receptor_count);
    hash_double_channel(&hash, rigid.receptor_y_angstrom, receptor_count);
    hash_double_channel(&hash, rigid.receptor_z_angstrom, receptor_count);
    hash_double_channel(
        &hash, rigid.receptor_vdw_radius_angstrom, receptor_count);
    hash_double_channel(
        &hash, rigid.ligand_vdw_radius_angstrom, ligand_count);
    hash_double_channel(&hash, rigid.pocket_center_angstrom, 3);
    hash.f64(rigid.pocket_radius_angstrom);
    hash_rigid_v2_config(&hash, rigid.v2);
    hash_rigid_v3_config(&hash, rigid.v3);
    hash_rigid_v3_config(&hash, rigid.clearance_v4);

    const auto torsion_receptor_count =
        static_cast<std::size_t>(torsion.receptor_atom_count);
    const auto torsion_ligand_count =
        static_cast<std::size_t>(torsion.ligand_atom_count);
    const auto rotor_count = static_cast<std::size_t>(torsion.rotor_count);
    const auto internal_pair_count =
        static_cast<std::size_t>(torsion.internal_pair_count);
    hash.i32(torsion.unit_system);
    hash.u64(torsion.receptor_atom_count);
    hash.u64(torsion.ligand_atom_count);
    hash.u64(torsion.rotor_count);
    hash.u64(torsion.internal_pair_count);
    hash_double_channel(
        &hash, torsion.receptor_x_angstrom, torsion_receptor_count);
    hash_double_channel(
        &hash, torsion.receptor_y_angstrom, torsion_receptor_count);
    hash_double_channel(
        &hash, torsion.receptor_z_angstrom, torsion_receptor_count);
    hash_double_channel(
        &hash,
        torsion.receptor_vdw_radius_angstrom,
        torsion_receptor_count);
    hash_double_channel(
        &hash, torsion.ligand_vdw_radius_angstrom, torsion_ligand_count);
    hash_double_channel(&hash, torsion.pocket_center_angstrom, 3);
    hash_i32_channel(
        &hash, torsion.parent_atom_index, torsion_ligand_count);
    hash_u64_channel(
        &hash, torsion.rotatable_child_atom_index, rotor_count);
    hash_u64_channel(
        &hash, torsion.internal_pair_atom_i, internal_pair_count);
    hash_u64_channel(
        &hash, torsion.internal_pair_atom_j, internal_pair_count);
    hash.f64(torsion.receptor_overlap_scale);
    hash.f64(torsion.internal_overlap_scale);
    hash.f64(torsion.internal_overlap_weight);
    hash.u64(torsion.maximum_baseline_v6_steps);
    hash.u64(torsion.maximum_torsions_evaluated);
    hash.u64(torsion.maximum_torsion_steps);
    hash.u64(torsion.maximum_backtracking_evaluations);
    hash.f64(torsion.maximum_torsion_step_radians);
    hash.f64(torsion.minimum_torsion_step_radians);
    hash.f64(torsion.maximum_total_torsion_path_radians);
    hash.f64(torsion.maximum_centroid_offset_angstrom);
    hash.f64(torsion.minimum_selected_final_receptor_penalty);
    hash.f64(torsion.maximum_selected_final_receptor_penalty);
    hash.f64(torsion.penalty_tolerance);
    hash.f64(torsion.epsilon_angstrom);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> scorer_context_receipt(
    const bg_context &context,
    const bg_docking_scorer_v1_context_soa_v1 &descriptor) noexcept {
    const auto receptor_count =
        static_cast<std::size_t>(descriptor.receptor_atom_count);
    const auto ligand_count =
        static_cast<std::size_t>(descriptor.ligand_atom_count);
    CanonicalHash hash(kScorerContextSchema);
    hash.i32(context.backend);
    hash.i32(context.unit_system);
    hash.i32(context.device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    for (const double *channel : {
             descriptor.receptor_x_angstrom,
             descriptor.receptor_y_angstrom,
             descriptor.receptor_z_angstrom,
             descriptor.receptor_charge_elementary,
             descriptor.receptor_vdw_radius_angstrom,
             descriptor.receptor_epsilon_kcal_per_mol}) {
        hash_double_channel(&hash, channel, receptor_count);
    }
    hash_u8_channel(&hash, descriptor.receptor_hydrophobic, receptor_count);
    hash_u8_channel(&hash, descriptor.receptor_acceptor, receptor_count);
    for (const double *channel : {
             descriptor.ligand_reference_x_angstrom,
             descriptor.ligand_reference_y_angstrom,
             descriptor.ligand_reference_z_angstrom,
             descriptor.ligand_charge_elementary,
             descriptor.ligand_vdw_radius_angstrom,
             descriptor.ligand_epsilon_kcal_per_mol}) {
        hash_double_channel(&hash, channel, ligand_count);
    }
    hash_u8_channel(&hash, descriptor.ligand_hydrophobic, ligand_count);
    hash_u8_channel(&hash, descriptor.ligand_acceptor, ligand_count);
    const auto receptor_donor_count =
        static_cast<std::size_t>(descriptor.receptor_donor_count);
    const auto ligand_donor_count =
        static_cast<std::size_t>(descriptor.ligand_donor_count);
    const auto exclusion_count =
        static_cast<std::size_t>(descriptor.ligand_exclusion_count);
    const auto rotor_count = static_cast<std::size_t>(descriptor.rotor_count);
    hash_u64_channel(
        &hash, descriptor.receptor_donor_atom_index, receptor_donor_count);
    hash_u64_channel(
        &hash, descriptor.receptor_hydrogen_atom_index, receptor_donor_count);
    hash_u64_channel(
        &hash, descriptor.ligand_donor_atom_index, ligand_donor_count);
    hash_u64_channel(
        &hash, descriptor.ligand_hydrogen_atom_index, ligand_donor_count);
    hash_u64_channel(
        &hash, descriptor.ligand_exclusion_atom_i, exclusion_count);
    hash_u64_channel(
        &hash, descriptor.ligand_exclusion_atom_j, exclusion_count);
    hash_u64_channel(&hash, descriptor.rotor_atom_i, rotor_count);
    hash_u64_channel(&hash, descriptor.rotor_atom_j, rotor_count);
    hash_u64_channel(&hash, descriptor.rotor_atom_k, rotor_count);
    hash_u64_channel(&hash, descriptor.rotor_atom_l, rotor_count);
    hash_double_channel(&hash, descriptor.pocket_center_angstrom, 3);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash_double_channel(
        &hash, descriptor.weights, BG_DOCKING_SCORER_V1_TERM_COUNT);
    hash.f64(descriptor.electrostatic_dielectric);
    hash.f64(descriptor.pair_cutoff_angstrom);
    hash.f64(descriptor.hbond_distance_max_angstrom);
    hash.f64(descriptor.polar_burial_distance_angstrom);
    hash.u64(descriptor.max_receptor_candidate_pairs);
    hash.u64(descriptor.max_ligand_pair_checks);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> validity_context_receipt(
    const bg_context &context,
    const bg_docking_pose_validity_context_soa_v1 &descriptor) noexcept {
    const auto receptor_count =
        static_cast<std::size_t>(descriptor.receptor_atom_count);
    const auto ligand_count =
        static_cast<std::size_t>(descriptor.ligand_atom_count);
    CanonicalHash hash(kValidityContextSchema);
    hash.i32(context.backend);
    hash.i32(context.unit_system);
    hash.i32(context.device_ordinal);
    hash.i32(descriptor.unit_system);
    hash.u64(descriptor.receptor_atom_count);
    hash.u64(descriptor.ligand_atom_count);
    for (const double *channel : {
             descriptor.receptor_x_angstrom,
             descriptor.receptor_y_angstrom,
             descriptor.receptor_z_angstrom,
             descriptor.receptor_vdw_radius_angstrom}) {
        hash_double_channel(&hash, channel, receptor_count);
    }
    for (const double *channel : {
             descriptor.ligand_reference_x_angstrom,
             descriptor.ligand_reference_y_angstrom,
             descriptor.ligand_reference_z_angstrom,
             descriptor.ligand_vdw_radius_angstrom}) {
        hash_double_channel(&hash, channel, ligand_count);
    }
    const auto bond_count = static_cast<std::size_t>(descriptor.bond_count);
    const auto exclusion_count =
        static_cast<std::size_t>(descriptor.ligand_exclusion_count);
    const auto chirality_count =
        static_cast<std::size_t>(descriptor.chirality_center_count);
    hash_u64_channel(&hash, descriptor.bond_atom_i, bond_count);
    hash_u64_channel(&hash, descriptor.bond_atom_j, bond_count);
    hash_u64_channel(
        &hash, descriptor.ligand_exclusion_atom_i, exclusion_count);
    hash_u64_channel(
        &hash, descriptor.ligand_exclusion_atom_j, exclusion_count);
    hash_u64_channel(
        &hash, descriptor.chirality_center_atom, chirality_count);
    hash_u64_channel(&hash, descriptor.chirality_atom_i, chirality_count);
    hash_u64_channel(&hash, descriptor.chirality_atom_j, chirality_count);
    hash_u64_channel(&hash, descriptor.chirality_atom_k, chirality_count);
    hash_double_channel(&hash, descriptor.pocket_center_angstrom, 3);
    hash.f64(descriptor.pocket_radius_angstrom);
    hash.f64(descriptor.bond_length_tolerance_angstrom);
    hash.f64(descriptor.ligand_self_clash_angstrom);
    hash.f64(descriptor.receptor_ligand_clash_angstrom);
    hash.f64(descriptor.rotation_tolerance);
    hash.f64(descriptor.chirality_volume_tolerance);
    hash.f64(descriptor.severe_overlap_scale);
    hash.f64(descriptor.contact_cell_size_angstrom);
    hash.u64(descriptor.max_pair_checks);
    hash.u64(descriptor.max_cross_checks);
    hash.u64(descriptor.max_element_ligand_pair_checks);
    hash.u64(descriptor.max_element_receptor_candidate_pairs);
    hash.digest(descriptor.authority_input_receipt_sha256);
    hash.digest(descriptor.receptor_system_sha256);
    hash.digest(descriptor.ligand_system_sha256);
    hash.digest(descriptor.scorer_context_receipt_sha256);
    hash.digest(descriptor.backend_receipt_sha256);
    hash.digest(descriptor.contact_policy_sha256);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> component_binding_receipt(
    const bg_context &context,
    const std::array<uint8_t, 32> &admission,
    const std::array<uint8_t, 32> &refinement,
    const std::array<uint8_t, 32> &scorer,
    const std::array<uint8_t, 32> &validity) noexcept {
    CanonicalHash hash(kComponentBindingSchema);
    hash.string(kProfileId);
    hash.i32(context.backend);
    hash.i32(context.unit_system);
    hash.i32(context.device_ordinal);
    hash.digest(admission);
    hash.digest(refinement);
    hash.digest(scorer);
    hash.digest(validity);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> refinement_evidence(
    std::size_t slot,
    std::size_t ligand_atom_count,
    const bg_docking_rigid_refinement_output_v1 &rigid,
    const bg_docking_torsion_v7_output_v1 &torsion,
    const bg_docking_fixed64_refinement_output_v1 &refinement) noexcept {
    const auto &rigid_row = rigid.rows[slot];
    const auto &torsion_row = torsion.rows[slot];
    const auto &final_row = refinement.rows[slot];
    CanonicalHash hash(kRefinementEvidenceSchema);
    hash.size(slot);
    hash.i32(rigid_row.status);
    hash.i32(rigid_row.failure_code);
    hash.i32(rigid_row.candidate_mode);
    hash.i32(rigid_row.selected_profile);
    hash.byte(rigid_row.baseline_duplicate_of_v2);
    hash.byte(rigid_row.clearance_evaluated);
    hash.byte(rigid_row.clearance_selected);
    hash_rigid_evidence_value(&hash, rigid_row.selected);
    hash_rigid_evidence_value(&hash, rigid_row.comparison_v2);
    hash_rigid_evidence_value(&hash, rigid_row.baseline_v3);
    hash_rigid_evidence_value(&hash, rigid_row.clearance_v4);
    const std::size_t coordinate_offset = slot * ligand_atom_count;
    hash_coordinate_triplet(
        &hash,
        rigid.selected_x_angstrom,
        rigid.selected_y_angstrom,
        rigid.selected_z_angstrom,
        coordinate_offset,
        ligand_atom_count);
    hash_coordinate_triplet(
        &hash,
        rigid.comparison_v2_x_angstrom,
        rigid.comparison_v2_y_angstrom,
        rigid.comparison_v2_z_angstrom,
        coordinate_offset,
        ligand_atom_count);
    hash_coordinate_triplet(
        &hash,
        rigid.baseline_v3_x_angstrom,
        rigid.baseline_v3_y_angstrom,
        rigid.baseline_v3_z_angstrom,
        coordinate_offset,
        ligand_atom_count);
    hash_coordinate_triplet(
        &hash,
        rigid.clearance_v4_x_angstrom,
        rigid.clearance_v4_y_angstrom,
        rigid.clearance_v4_z_angstrom,
        coordinate_offset,
        ligand_atom_count);
    hash.i32(torsion_row.status);
    hash.i32(torsion_row.failure_code);
    hash.i32(torsion_row.skip_reason);
    hash.i32(torsion_row.selection_reason);
    hash.byte(torsion_row.selection_window_reachable);
    hash.byte(
        torsion_row.evaluation_stopped_after_selection_window_became_unreachable);
    hash.byte(torsion_row.torsion_evaluated);
    hash.byte(torsion_row.torsion_variant_available);
    hash.byte(torsion_row.torsion_selected);
    hash.u64(torsion_row.torsion_step_budget);
    hash.u64(torsion_row.fixed_objective_evaluation_count);
    hash.u64(torsion_row.torsion_trial_objective_evaluation_count);
    hash.u64(torsion_row.evaluated_torsion_steps);
    hash.u64(torsion_row.accepted_torsion_steps);
    hash.u64(torsion_row.baseline_v6_accepted_steps);
    for (double value : {
             torsion_row.source_receptor_penalty,
             torsion_row.source_internal_penalty,
             torsion_row.source_combined_penalty,
             torsion_row.baseline_receptor_penalty,
             torsion_row.baseline_internal_penalty,
             torsion_row.baseline_combined_penalty,
             torsion_row.optimized_receptor_penalty,
             torsion_row.optimized_internal_penalty,
             torsion_row.optimized_combined_penalty,
             torsion_row.final_receptor_penalty,
             torsion_row.final_internal_penalty,
             torsion_row.final_combined_penalty,
             torsion_row.evaluated_total_torsion_path_radians,
             torsion_row.accepted_total_torsion_path_radians}) {
        hash.f64(value);
    }
    const std::size_t move_offset = slot * kMovesPerCandidate;
    for (std::size_t index = 0; index < kMovesPerCandidate; ++index) {
        const auto &move = torsion.moves[move_offset + index];
        hash.u32(move.slot_index);
        hash.u32(move.move_index);
        hash.byte(move.evaluated);
        hash.byte(move.selected);
        hash.u64(move.rotatable_child_atom_index);
        hash.f64(move.delta_radians);
        hash.f64(move.receptor_penalty);
        hash.f64(move.internal_penalty);
        hash.f64(move.combined_penalty);
    }
    hash_coordinate_triplet(
        &hash,
        torsion.optimized_x_angstrom,
        torsion.optimized_y_angstrom,
        torsion.optimized_z_angstrom,
        coordinate_offset,
        ligand_atom_count);
    hash_scalar_channel(
        &hash,
        torsion.optimized_torsion_angles_radians,
        coordinate_offset,
        ligand_atom_count);
    hash_coordinate_triplet(
        &hash,
        torsion.final_x_angstrom,
        torsion.final_y_angstrom,
        torsion.final_z_angstrom,
        coordinate_offset,
        ligand_atom_count);
    hash_scalar_channel(
        &hash,
        torsion.final_torsion_angles_radians,
        coordinate_offset,
        ligand_atom_count);
    hash.i32(final_row.status);
    hash.i32(final_row.failure_stage);
    hash.i32(final_row.coordinate_origin);
    hash.i32(final_row.rigid_failure_code);
    hash.i32(final_row.torsion_v7_failure_code);
    hash.i32(final_row.selected_rigid_profile);
    hash.i32(final_row.downstream_candidate_state);
    hash.byte(final_row.torsion_v7_applicable);
    hash.byte(final_row.torsion_v7_selected);
    hash.byte(final_row.coordinate_available);
    hash.digest(final_row.coordinate_sha256);
    hash_coordinate_triplet(
        &hash,
        refinement.final_x_angstrom,
        refinement.final_y_angstrom,
        refinement.final_z_angstrom,
        coordinate_offset,
        ligand_atom_count);
    hash.f64(refinement.final_quaternion_x[slot]);
    hash.f64(refinement.final_quaternion_y[slot]);
    hash.f64(refinement.final_quaternion_z[slot]);
    hash.f64(refinement.final_quaternion_w[slot]);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> scorer_evidence(
    const bg_docking_scorer_v1_row_v1 &row) noexcept {
    CanonicalHash hash(kScorerEvidenceSchema);
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.i32(row.failure_code);
    for (double term : row.weighted_terms) hash.f64(term);
    hash.f64(row.total_score);
    hash.u64(row.receptor_candidate_pair_count);
    hash.u64(row.ligand_pair_count);
    hash.u64(row.hbond_count);
    hash.u64(row.hydrophobic_contact_count);
    hash.u64(row.buried_polar_count);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> validity_evidence(
    const bg_docking_pose_validity_row_v1 &row) noexcept {
    CanonicalHash hash(kValidityEvidenceSchema);
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.i32(row.failure_code);
    hash.i32(row.upstream_scorer_failure_code);
    hash.u32(row.passed_check_mask);
    hash.u32(row.blocker_mask);
    hash.u64(row.observed_count);
    hash.u64(row.atom_count);
    hash.f64(row.rotation_orthogonality_max_error);
    hash.f64(row.rotation_determinant);
    hash.f64(row.max_bond_length_delta_angstrom);
    hash.f64(row.minimum_ligand_nonbonded_distance_angstrom);
    hash.u64(row.evaluated_ligand_nonbonded_pair_count);
    hash.u64(row.excluded_ligand_pair_count);
    hash.f64(row.minimum_receptor_ligand_distance_angstrom);
    hash.u64(row.evaluated_receptor_ligand_pair_count);
    hash.f64(row.minimum_declared_chiral_volume);
    hash.u64(row.declared_chirality_center_count);
    hash.f64(row.maximum_pocket_center_distance_angstrom);
    hash.u64(row.element_vdw_ligand_pair_count);
    hash.u64(row.element_vdw_ligand_severe_overlap_count);
    hash.f64(row.element_vdw_ligand_minimum_distance_angstrom);
    hash.f64(row.element_vdw_ligand_minimum_ratio);
    hash.u64(row.element_vdw_receptor_candidate_pair_count);
    hash.u64(row.element_vdw_receptor_full_cartesian_pair_count);
    hash.u64(row.element_vdw_receptor_cell_count);
    hash.u64(row.element_vdw_receptor_severe_overlap_count);
    hash.f64(row.element_vdw_receptor_minimum_distance_angstrom);
    hash.f64(row.element_vdw_receptor_minimum_ratio);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> ranking_evidence(
    const bg_docking_stable_top_k_row_v1 &row) noexcept {
    CanonicalHash hash(kRankingEvidenceSchema);
    hash.u32(row.slot_index);
    hash.byte(row.rank_eligible);
    hash.byte(row.valid_rank_eligible);
    hash.u32(row.stable_rank);
    hash.u32(row.stable_valid_rank);
    hash.f64(row.total_score);
    hash.digest(row.coordinate_sha256);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> cluster_evidence(
    const bg_docking_rmsd_cluster_row_v1 &row) noexcept {
    CanonicalHash hash(kClusterEvidenceSchema);
    hash.u32(row.slot_index);
    hash.i32(row.status);
    hash.byte(row.cluster_eligible);
    hash.byte(row.representative);
    hash.byte(row.top_k_representative);
    hash.u32(row.stable_valid_rank);
    hash.u32(row.cluster_id);
    hash.u32(row.representative_slot_index);
    hash.u32(row.cluster_rank);
    hash.u32(row.top_k_rank);
    hash.u32(row.cluster_size);
    hash.f64(row.direct_rmsd_to_representative_angstrom);
    hash.digest(row.coordinate_sha256);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> policy_receipt(
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    const bg_docking_fixed64_pipeline_input_v1 &input,
    const bg_docking_fixed64_producer_output_v1 &producer,
    std::size_t coordinate_count) noexcept {
    CanonicalHash hash(kPolicySchema);
    hash.string(kProfileId);
    hash.digest(pipeline.refinement_context_receipt_sha256);
    hash.digest(pipeline.component_binding_receipt_sha256);
    hash.digest(input.predeclared_refinement_policy_sha256);
    hash.digest(producer.allocation_receipt_sha256);
    hash.f64(input.rmsd_threshold_angstrom);
    hash.size(kCandidateCount);
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        hash.i32(input.candidate_mode[slot]);
        hash.u64(input.rigid_max_steps[slot]);
        hash.byte(input.proposal_is_torsion_eligible[slot]);
        hash.u64(input.torsion_max_steps[slot]);
    }
    hash.size(coordinate_count);
    for (std::size_t index = 0; index < coordinate_count; ++index) {
        hash.f64(input.baseline_torsion_angles_radians[index]);
    }
    hash.byte(UINT8_C(0));
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> policy_receipt_v2(
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    const bg_docking_fixed64_pipeline_input_v2 &input,
    const bg_docking_fixed64_producer_output_v1 &producer,
    std::size_t coordinate_count) noexcept {
    CanonicalHash hash(kPolicySchema);
    hash.string(kProfileIdV2);
    hash.digest(pipeline.refinement_context_receipt_sha256);
    hash.digest(pipeline.component_binding_receipt_sha256);
    hash.digest(input.predeclared_refinement_policy_sha256);
    hash.digest(producer.allocation_receipt_sha256);
    hash.f64(input.rmsd_threshold_angstrom);
    hash.size(kCandidateCount);
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        hash.i32(input.candidate_mode[slot]);
        hash.u64(input.rigid_max_steps[slot]);
        hash.byte(input.proposal_is_torsion_eligible[slot]);
        hash.u64(input.torsion_max_steps[slot]);
    }
    hash.size(coordinate_count);
    for (std::size_t index = 0; index < coordinate_count; ++index) {
        hash.f64(input.baseline_torsion_angles_radians[index]);
    }
    hash.byte(UINT8_C(0));
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> post_admission_policy_receipt_v2(
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    const bg_docking_fixed64_pipeline_input_v2 &input,
    const bg_docking_fixed64_producer_output_v1 &producer,
    const std::array<uint8_t, 32> &refinement_policy) noexcept {
    CanonicalHash hash(kPostAdmissionPolicySchemaV2);
    hash.string(kProfileIdV2);
    hash.digest(pipeline.admission_context_receipt_sha256);
    hash.digest(pipeline.component_binding_receipt_sha256);
    hash.digest(refinement_policy);
    hash.digest(input.predeclared_post_refinement_admission_policy_sha256);
    hash.digest(producer.allocation_receipt_sha256);
    hash.size(kCandidateCount);
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    return hash.finish();
}

void copy_digest(
    const std::array<uint8_t, 32> &source,
    uint8_t (&destination)[32]) noexcept {
    std::copy(source.begin(), source.end(), destination);
}

[[nodiscard]] bg_status validate_bridge_overlap(
    const bg_context &context,
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    const bg_docking_fixed64_pipeline_input_v1 &input,
    std::size_t coordinate_count,
    const bg_docking_fixed64_producer_output_v1 &producer,
    const bg_docking_rigid_refinement_output_v1 &rigid,
    const bg_docking_torsion_v7_output_v1 &torsion,
    const bg_docking_scorer_v1_output_v1 &scorer,
    const bg_docking_pose_validity_output_v1 &validity,
    const bg_docking_stable_top_k_output_v1 &ranking,
    const bg_docking_rmsd_cluster_output_v1 &cluster,
    const bg_docking_fixed64_refinement_output_v1 &refinement,
    const bg_docking_fixed64_pipeline_output_v1 &output) {
    std::vector<MemoryRange> bridge;
    std::vector<MemoryRange> downstream;
    std::vector<MemoryRange> inputs;
    bridge.reserve(7);
    downstream.reserve(44);
    inputs.reserve(64);
    bg_status status = append_range(
        &bridge, &producer, 1, "fixed64 complete producer range overflows");
    if (status != BG_STATUS_OK) return status;
#define BG_APPEND_TYPED(list, pointer, count, message)                       \
    do {                                                                     \
        status = append_range((list), (pointer), (count), (message));        \
        if (status != BG_STATUS_OK) return status;                           \
    } while (false)
    BG_APPEND_TYPED(&bridge, producer.rows, kCandidateCount, "producer rows overflow");
    BG_APPEND_TYPED(&bridge, producer.x_angstrom, coordinate_count, "producer x overflows");
    BG_APPEND_TYPED(&bridge, producer.y_angstrom, coordinate_count, "producer y overflows");
    BG_APPEND_TYPED(&bridge, producer.z_angstrom, coordinate_count, "producer z overflows");
    BG_APPEND_TYPED(&bridge, &output, 1, "pipeline output overflows");
    BG_APPEND_TYPED(&bridge, output.rows, kCandidateCount, "pipeline rows overflow");

    BG_APPEND_TYPED(&downstream, &rigid, 1, "rigid output overflows");
    BG_APPEND_TYPED(&downstream, rigid.rows, kCandidateCount, "rigid rows overflow");
    for (const double *pointer : {
             rigid.selected_x_angstrom, rigid.selected_y_angstrom,
             rigid.selected_z_angstrom, rigid.comparison_v2_x_angstrom,
             rigid.comparison_v2_y_angstrom, rigid.comparison_v2_z_angstrom,
             rigid.baseline_v3_x_angstrom, rigid.baseline_v3_y_angstrom,
             rigid.baseline_v3_z_angstrom, rigid.clearance_v4_x_angstrom,
             rigid.clearance_v4_y_angstrom, rigid.clearance_v4_z_angstrom}) {
        BG_APPEND_TYPED(&downstream, pointer, coordinate_count, "rigid coordinates overflow");
    }
    BG_APPEND_TYPED(&downstream, &torsion, 1, "torsion output overflows");
    BG_APPEND_TYPED(&downstream, torsion.rows, kCandidateCount, "torsion rows overflow");
    BG_APPEND_TYPED(
        &downstream,
        torsion.moves,
        kCandidateCount * kMovesPerCandidate,
        "torsion moves overflow");
    for (const double *pointer : {
             torsion.optimized_x_angstrom, torsion.optimized_y_angstrom,
             torsion.optimized_z_angstrom,
             torsion.optimized_torsion_angles_radians,
             torsion.final_x_angstrom, torsion.final_y_angstrom,
             torsion.final_z_angstrom, torsion.final_torsion_angles_radians}) {
        BG_APPEND_TYPED(&downstream, pointer, coordinate_count, "torsion coordinates overflow");
    }
    BG_APPEND_TYPED(&downstream, &scorer, 1, "scorer output overflows");
    BG_APPEND_TYPED(&downstream, scorer.rows, kCandidateCount, "scorer rows overflow");
    BG_APPEND_TYPED(&downstream, &validity, 1, "validity output overflows");
    BG_APPEND_TYPED(&downstream, validity.rows, kCandidateCount, "validity rows overflow");
    BG_APPEND_TYPED(&downstream, &ranking, 1, "ranking output overflows");
    BG_APPEND_TYPED(&downstream, ranking.rows, kCandidateCount, "ranking rows overflow");
    BG_APPEND_TYPED(
        &downstream, ranking.primary_slot_indices, kCandidateCount,
        "primary indices overflow");
    BG_APPEND_TYPED(
        &downstream, ranking.valid_slot_indices, kCandidateCount,
        "valid indices overflow");
    BG_APPEND_TYPED(&downstream, &cluster, 1, "cluster output overflows");
    BG_APPEND_TYPED(&downstream, cluster.rows, kCandidateCount, "cluster rows overflow");
    BG_APPEND_TYPED(
        &downstream, cluster.representative_slot_indices, kCandidateCount,
        "cluster representatives overflow");
    BG_APPEND_TYPED(
        &downstream, cluster.top_k_slot_indices,
        BG_DOCKING_STABLE_TOP_K_LIMIT, "cluster top-k overflows");
    BG_APPEND_TYPED(&downstream, &refinement, 1, "refinement output overflows");
    BG_APPEND_TYPED(&downstream, refinement.rows, kCandidateCount, "refinement rows overflow");
    for (const double *pointer : {
             refinement.final_x_angstrom, refinement.final_y_angstrom,
             refinement.final_z_angstrom}) {
        BG_APPEND_TYPED(&downstream, pointer, coordinate_count, "final coordinates overflow");
    }
    for (const double *pointer : {
             refinement.final_quaternion_x, refinement.final_quaternion_y,
             refinement.final_quaternion_z, refinement.final_quaternion_w}) {
        BG_APPEND_TYPED(&downstream, pointer, kCandidateCount, "final quaternions overflow");
    }
    BG_APPEND_TYPED(&inputs, &context, 1, "pipeline context overflows");
    BG_APPEND_TYPED(&inputs, &pipeline, 1, "pipeline handle overflows");
    BG_APPEND_TYPED(&inputs, &input, 1, "pipeline input overflows");
    BG_APPEND_TYPED(&inputs, input.producer_input, 1, "producer input overflows");
    BG_APPEND_TYPED(&inputs, input.candidate_mode, kCandidateCount, "mode input overflows");
    BG_APPEND_TYPED(&inputs, input.rigid_max_steps, kCandidateCount, "rigid budget overflows");
    BG_APPEND_TYPED(
        &inputs, input.proposal_is_torsion_eligible, kCandidateCount,
        "torsion eligibility overflows");
    BG_APPEND_TYPED(&inputs, input.torsion_max_steps, kCandidateCount, "torsion budget overflows");
    BG_APPEND_TYPED(
        &inputs, input.baseline_torsion_angles_radians, coordinate_count,
        "torsion baseline overflows");
    const auto &producer_input = *input.producer_input;
    BG_APPEND_TYPED(
        &inputs,
        producer_input.allocation_input,
        1,
        "producer allocation input overflows");
    const auto &allocation = *producer_input.allocation_input;
    BG_APPEND_TYPED(
        &inputs,
        allocation.atomic_features,
        static_cast<std::size_t>(allocation.atomic_feature_count),
        "producer allocation features overflow");
    BG_APPEND_TYPED(
        &inputs,
        allocation.v7_control_sources,
        static_cast<std::size_t>(allocation.v7_control_source_count),
        "producer allocation V7 sources overflow");
    BG_APPEND_TYPED(
        &inputs,
        allocation.conformer_sources,
        static_cast<std::size_t>(allocation.conformer_source_count),
        "producer allocation conformer sources overflow");
    BG_APPEND_TYPED(
        &inputs,
        allocation.retained_sources,
        static_cast<std::size_t>(allocation.retained_source_count),
        "producer allocation retained sources overflow");
    BG_APPEND_TYPED(
        &inputs,
        producer_input.v7_control_sources,
        static_cast<std::size_t>(producer_input.v7_control_source_count),
        "producer V7 source descriptors overflow");
    BG_APPEND_TYPED(
        &inputs,
        producer_input.conformer_sources,
        static_cast<std::size_t>(producer_input.conformer_source_count),
        "producer conformer source descriptors overflow");
    BG_APPEND_TYPED(
        &inputs,
        producer_input.retained_sources,
        static_cast<std::size_t>(producer_input.retained_source_count),
        "producer retained source descriptors overflow");
    BG_APPEND_TYPED(
        &inputs,
        producer_input.feature_geometry_rows,
        static_cast<std::size_t>(producer_input.feature_geometry_count),
        "producer feature geometry rows overflow");
    BG_APPEND_TYPED(
        &inputs,
        producer_input.feature_atom_indices,
        static_cast<std::size_t>(producer_input.feature_atom_index_count),
        "producer feature atom indices overflow");
    const auto append_source = [&](
        const bg_docking_fixed64_coordinate_source_v1 &source) -> bg_status {
        const auto atom_count =
            static_cast<std::size_t>(source.ligand_atom_count);
        for (const double *channel : {
                 source.x_angstrom,
                 source.y_angstrom,
                 source.z_angstrom}) {
            const bg_status source_status = append_range(
                &inputs,
                channel,
                atom_count,
                "producer source coordinate channel overflows");
            if (source_status != BG_STATUS_OK) return source_status;
        }
        return BG_STATUS_OK;
    };
    if (producer_input.exact_v11_source != nullptr) {
        BG_APPEND_TYPED(
            &inputs,
            producer_input.exact_v11_source,
            1,
            "producer exact source descriptor overflows");
        status = append_source(*producer_input.exact_v11_source);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < producer_input.v7_control_source_count;
         ++index) {
        status = append_source(producer_input.v7_control_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < producer_input.conformer_source_count;
         ++index) {
        status = append_source(producer_input.conformer_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < producer_input.retained_source_count;
         ++index) {
        status = append_source(producer_input.retained_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
#undef BG_APPEND_TYPED
    for (std::size_t left = 0; left < bridge.size(); ++left) {
        for (std::size_t right = left + 1; right < bridge.size(); ++right) {
            if (overlaps(bridge[left], bridge[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 complete pipeline bridge outputs overlap");
            }
        }
        for (MemoryRange range : downstream) {
            if (overlaps(bridge[left], range)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 complete pipeline component outputs overlap");
            }
        }
        for (MemoryRange range : inputs) {
            if (overlaps(bridge[left], range)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 complete pipeline input and output overlap");
            }
        }
    }
    for (MemoryRange output_range : downstream) {
        for (MemoryRange input_range : inputs) {
            if (overlaps(output_range, input_range)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 complete pipeline input and downstream output overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_v2_overlap(
    const bg_context &context,
    const bg_docking_fixed64_pipeline_v2 &handle,
    const bg_docking_fixed64_pipeline_v1 &pipeline,
    const bg_docking_fixed64_pipeline_input_v2 &input,
    std::size_t coordinate_count,
    const bg_docking_fixed64_producer_output_v1 &producer,
    const bg_docking_rigid_refinement_output_v1 &rigid,
    const bg_docking_torsion_v7_output_v1 &torsion,
    const bg_docking_scorer_v1_output_v1 &scorer,
    const bg_docking_pose_validity_output_v1 &validity,
    const bg_docking_stable_top_k_output_v1 &ranking,
    const bg_docking_rmsd_cluster_output_v1 &cluster,
    const bg_docking_fixed64_refinement_output_v1 &refinement,
    const bg_docking_geometric_admission_output_v1 &post_admission,
    const bg_docking_fixed64_pipeline_output_v2 &output) {
    std::vector<MemoryRange> outputs;
    std::vector<MemoryRange> inputs;
    outputs.reserve(55);
    inputs.reserve(64);
    bg_status status = BG_STATUS_OK;
#define BG_APPEND_V2(list, pointer, count, message)                         \
    do {                                                                    \
        status = append_range((list), (pointer), (count), (message));        \
        if (status != BG_STATUS_OK) return status;                           \
    } while (false)
    BG_APPEND_V2(&outputs, &producer, 1, "v2 producer output overflows");
    BG_APPEND_V2(&outputs, producer.rows, kCandidateCount, "v2 producer rows overflow");
    BG_APPEND_V2(&outputs, producer.x_angstrom, coordinate_count, "v2 producer x overflows");
    BG_APPEND_V2(&outputs, producer.y_angstrom, coordinate_count, "v2 producer y overflows");
    BG_APPEND_V2(&outputs, producer.z_angstrom, coordinate_count, "v2 producer z overflows");
    BG_APPEND_V2(&outputs, &rigid, 1, "v2 rigid output overflows");
    BG_APPEND_V2(&outputs, rigid.rows, kCandidateCount, "v2 rigid rows overflow");
    for (const double *channel : {
             rigid.selected_x_angstrom,
             rigid.selected_y_angstrom,
             rigid.selected_z_angstrom,
             rigid.comparison_v2_x_angstrom,
             rigid.comparison_v2_y_angstrom,
             rigid.comparison_v2_z_angstrom,
             rigid.baseline_v3_x_angstrom,
             rigid.baseline_v3_y_angstrom,
             rigid.baseline_v3_z_angstrom,
             rigid.clearance_v4_x_angstrom,
             rigid.clearance_v4_y_angstrom,
             rigid.clearance_v4_z_angstrom}) {
        BG_APPEND_V2(&outputs, channel, coordinate_count, "v2 rigid coordinate overflows");
    }
    BG_APPEND_V2(&outputs, &torsion, 1, "v2 torsion output overflows");
    BG_APPEND_V2(&outputs, torsion.rows, kCandidateCount, "v2 torsion rows overflow");
    BG_APPEND_V2(
        &outputs,
        torsion.moves,
        kCandidateCount * kMovesPerCandidate,
        "v2 torsion moves overflow");
    for (const double *channel : {
             torsion.optimized_x_angstrom,
             torsion.optimized_y_angstrom,
             torsion.optimized_z_angstrom,
             torsion.optimized_torsion_angles_radians,
             torsion.final_x_angstrom,
             torsion.final_y_angstrom,
             torsion.final_z_angstrom,
             torsion.final_torsion_angles_radians}) {
        BG_APPEND_V2(&outputs, channel, coordinate_count, "v2 torsion coordinate overflows");
    }
    BG_APPEND_V2(&outputs, &scorer, 1, "v2 scorer output overflows");
    BG_APPEND_V2(&outputs, scorer.rows, kCandidateCount, "v2 scorer rows overflow");
    BG_APPEND_V2(&outputs, &validity, 1, "v2 validity output overflows");
    BG_APPEND_V2(&outputs, validity.rows, kCandidateCount, "v2 validity rows overflow");
    BG_APPEND_V2(&outputs, &ranking, 1, "v2 ranking output overflows");
    BG_APPEND_V2(&outputs, ranking.rows, kCandidateCount, "v2 ranking rows overflow");
    BG_APPEND_V2(
        &outputs,
        ranking.primary_slot_indices,
        kCandidateCount,
        "v2 primary indices overflow");
    BG_APPEND_V2(
        &outputs,
        ranking.valid_slot_indices,
        kCandidateCount,
        "v2 valid indices overflow");
    BG_APPEND_V2(&outputs, &cluster, 1, "v2 cluster output overflows");
    BG_APPEND_V2(&outputs, cluster.rows, kCandidateCount, "v2 cluster rows overflow");
    BG_APPEND_V2(
        &outputs,
        cluster.representative_slot_indices,
        kCandidateCount,
        "v2 cluster representatives overflow");
    BG_APPEND_V2(
        &outputs,
        cluster.top_k_slot_indices,
        BG_DOCKING_STABLE_TOP_K_LIMIT,
        "v2 cluster top-k overflows");
    BG_APPEND_V2(&outputs, &refinement, 1, "v2 refinement output overflows");
    BG_APPEND_V2(&outputs, refinement.rows, kCandidateCount, "v2 refinement rows overflow");
    for (const double *channel : {
             refinement.final_x_angstrom,
             refinement.final_y_angstrom,
             refinement.final_z_angstrom}) {
        BG_APPEND_V2(&outputs, channel, coordinate_count, "v2 final coordinate overflows");
    }
    for (const double *channel : {
             refinement.final_quaternion_x,
             refinement.final_quaternion_y,
             refinement.final_quaternion_z,
             refinement.final_quaternion_w}) {
        BG_APPEND_V2(&outputs, channel, kCandidateCount, "v2 final quaternion overflows");
    }
    BG_APPEND_V2(&outputs, &post_admission, 1, "v2 post-admission output overflows");
    BG_APPEND_V2(
        &outputs,
        post_admission.rows,
        kCandidateCount,
        "v2 post-admission rows overflow");
    BG_APPEND_V2(&outputs, &output, 1, "v2 pipeline output overflows");
    BG_APPEND_V2(&outputs, output.rows, kCandidateCount, "v2 pipeline rows overflow");

    BG_APPEND_V2(&inputs, &context, 1, "v2 context overflows");
    BG_APPEND_V2(&inputs, &handle, 1, "v2 handle overflows");
    BG_APPEND_V2(&inputs, &pipeline, 1, "v2 component handle overflows");
    BG_APPEND_V2(&inputs, &input, 1, "v2 input overflows");
    BG_APPEND_V2(&inputs, input.producer_input, 1, "v2 producer input overflows");
    BG_APPEND_V2(&inputs, input.candidate_mode, kCandidateCount, "v2 mode input overflows");
    BG_APPEND_V2(&inputs, input.rigid_max_steps, kCandidateCount, "v2 rigid budget overflows");
    BG_APPEND_V2(
        &inputs,
        input.proposal_is_torsion_eligible,
        kCandidateCount,
        "v2 torsion eligibility overflows");
    BG_APPEND_V2(&inputs, input.torsion_max_steps, kCandidateCount, "v2 torsion budget overflows");
    BG_APPEND_V2(
        &inputs,
        input.baseline_torsion_angles_radians,
        coordinate_count,
        "v2 torsion baseline overflows");
    const auto &producer_input = *input.producer_input;
    BG_APPEND_V2(
        &inputs,
        producer_input.allocation_input,
        1,
        "v2 allocation input overflows");
    const auto &allocation = *producer_input.allocation_input;
    BG_APPEND_V2(
        &inputs,
        allocation.atomic_features,
        static_cast<std::size_t>(allocation.atomic_feature_count),
        "v2 atomic features overflow");
    BG_APPEND_V2(
        &inputs,
        allocation.v7_control_sources,
        static_cast<std::size_t>(allocation.v7_control_source_count),
        "v2 V7 sources overflow");
    BG_APPEND_V2(
        &inputs,
        allocation.conformer_sources,
        static_cast<std::size_t>(allocation.conformer_source_count),
        "v2 conformer sources overflow");
    BG_APPEND_V2(
        &inputs,
        allocation.retained_sources,
        static_cast<std::size_t>(allocation.retained_source_count),
        "v2 retained sources overflow");
    BG_APPEND_V2(
        &inputs,
        producer_input.v7_control_sources,
        static_cast<std::size_t>(producer_input.v7_control_source_count),
        "v2 V7 source descriptors overflow");
    BG_APPEND_V2(
        &inputs,
        producer_input.conformer_sources,
        static_cast<std::size_t>(producer_input.conformer_source_count),
        "v2 conformer source descriptors overflow");
    BG_APPEND_V2(
        &inputs,
        producer_input.retained_sources,
        static_cast<std::size_t>(producer_input.retained_source_count),
        "v2 retained source descriptors overflow");
    BG_APPEND_V2(
        &inputs,
        producer_input.feature_geometry_rows,
        static_cast<std::size_t>(producer_input.feature_geometry_count),
        "v2 feature geometry rows overflow");
    BG_APPEND_V2(
        &inputs,
        producer_input.feature_atom_indices,
        static_cast<std::size_t>(producer_input.feature_atom_index_count),
        "v2 feature atom indices overflow");
    const auto append_source = [&inputs](
                                   const bg_docking_fixed64_coordinate_source_v1
                                       &source) -> bg_status {
        const auto atom_count = static_cast<std::size_t>(source.ligand_atom_count);
        for (const double *channel : {
                 source.x_angstrom,
                 source.y_angstrom,
                 source.z_angstrom}) {
            const bg_status source_status = append_range(
                &inputs,
                channel,
                atom_count,
                "v2 source coordinate channel overflows");
            if (source_status != BG_STATUS_OK) return source_status;
        }
        return BG_STATUS_OK;
    };
    if (producer_input.exact_v11_source != nullptr) {
        BG_APPEND_V2(
            &inputs,
            producer_input.exact_v11_source,
            1,
            "v2 exact source descriptor overflows");
        status = append_source(*producer_input.exact_v11_source);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < producer_input.v7_control_source_count;
         ++index) {
        status = append_source(producer_input.v7_control_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < producer_input.conformer_source_count;
         ++index) {
        status = append_source(producer_input.conformer_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < producer_input.retained_source_count;
         ++index) {
        status = append_source(producer_input.retained_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
#undef BG_APPEND_V2
    for (std::size_t left = 0; left < outputs.size(); ++left) {
        for (std::size_t right = left + 1; right < outputs.size(); ++right) {
            if (overlaps(outputs[left], outputs[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 complete pipeline v2 output buffers overlap");
            }
        }
        for (MemoryRange input_range : inputs) {
            if (overlaps(outputs[left], input_range)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 complete pipeline v2 input and output overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

void destroy_components(bg_docking_fixed64_pipeline_v1 *pipeline) noexcept {
    if (pipeline == nullptr) return;
    bg_docking_fixed64_refinement_pipeline_v1_destroy(pipeline->refinement);
    bg_docking_geometric_admission_v1_destroy(pipeline->admission);
    pipeline->refinement = nullptr;
    pipeline->admission = nullptr;
}

}  // namespace
}  // namespace betelgeuze::native::docking::fixed64_pipeline

using betelgeuze::native::fail;
using betelgeuze::native::guarded_status;
using betelgeuze::native::pointer_is_aligned;
using betelgeuze::native::validate_descriptor_header;
using betelgeuze::native::validate_initializer_compatibility;

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_input_v1_init(
    bg_docking_fixed64_pipeline_input_v1 *input,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input,
            caller_struct_size,
            sizeof(*input),
            caller_abi_version,
            "fixed64 complete pipeline input initializer pointer is null",
            "fixed64 complete pipeline input initializer size does not match",
            "fixed64 complete pipeline input initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *input = bg_docking_fixed64_pipeline_input_v1{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_output_v1_init(
    bg_docking_fixed64_pipeline_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(*output),
            caller_abi_version,
            "fixed64 complete pipeline output initializer pointer is null",
            "fixed64 complete pipeline output initializer size does not match",
            "fixed64 complete pipeline output initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *output = bg_docking_fixed64_pipeline_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_input_v2_init(
    bg_docking_fixed64_pipeline_input_v2 *input,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input,
            caller_struct_size,
            sizeof(*input),
            caller_abi_version,
            "fixed64 complete pipeline v2 input initializer pointer is null",
            "fixed64 complete pipeline v2 input initializer size does not match",
            "fixed64 complete pipeline v2 input initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *input = bg_docking_fixed64_pipeline_input_v2{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_output_v2_init(
    bg_docking_fixed64_pipeline_output_v2 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(*output),
            caller_abi_version,
            "fixed64 complete pipeline v2 output initializer pointer is null",
            "fixed64 complete pipeline v2 output initializer size does not match",
            "fixed64 complete pipeline v2 output initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *output = bg_docking_fixed64_pipeline_output_v2{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_v1_create(
    const bg_context *context,
    const bg_docking_geometric_admission_context_soa_v1 *admission_descriptor,
    const bg_docking_rigid_refinement_context_soa_v1 *rigid_descriptor,
    const bg_docking_torsion_v7_context_soa_v1 *torsion_descriptor,
    const bg_docking_scorer_v1_context_soa_v1 *scorer_descriptor,
    const bg_docking_pose_validity_context_soa_v1 *validity_descriptor,
    bg_docking_fixed64_pipeline_v1 **out_pipeline) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_pipeline;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || admission_descriptor == nullptr ||
            rigid_descriptor == nullptr || torsion_descriptor == nullptr ||
            scorer_descriptor == nullptr || validity_descriptor == nullptr ||
            out_pipeline == nullptr || !pointer_is_aligned(context) ||
            !pointer_is_aligned(admission_descriptor) ||
            !pointer_is_aligned(rigid_descriptor) ||
            !pointer_is_aligned(torsion_descriptor) ||
            !pointer_is_aligned(scorer_descriptor) ||
            !pointer_is_aligned(validity_descriptor) ||
            !pointer_is_aligned(out_pipeline)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline create descriptors are null or misaligned");
        }
        bg_status status = validate_descriptor_header(
            admission_descriptor->struct_size,
            sizeof(*admission_descriptor),
            admission_descriptor->abi_version,
            "fixed64 complete pipeline admission descriptor size does not match ABI v1",
            "fixed64 complete pipeline admission descriptor ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        status = validate_descriptor_header(
            rigid_descriptor->struct_size,
            sizeof(*rigid_descriptor),
            rigid_descriptor->abi_version,
            "fixed64 complete pipeline rigid descriptor size does not match ABI v1",
            "fixed64 complete pipeline rigid descriptor ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        status = validate_descriptor_header(
            torsion_descriptor->struct_size,
            sizeof(*torsion_descriptor),
            torsion_descriptor->abi_version,
            "fixed64 complete pipeline torsion descriptor size does not match ABI v1",
            "fixed64 complete pipeline torsion descriptor ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        status = validate_descriptor_header(
            scorer_descriptor->struct_size,
            sizeof(*scorer_descriptor),
            scorer_descriptor->abi_version,
            "fixed64 complete pipeline scorer descriptor size does not match ABI v1",
            "fixed64 complete pipeline scorer descriptor ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        status = validate_descriptor_header(
            validity_descriptor->struct_size,
            sizeof(*validity_descriptor),
            validity_descriptor->abi_version,
            "fixed64 complete pipeline validity descriptor size does not match ABI v1",
            "fixed64 complete pipeline validity descriptor ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        status = validate_create_output_overlap(
            *context,
            *admission_descriptor,
            *rigid_descriptor,
            *torsion_descriptor,
            *scorer_descriptor,
            *validity_descriptor,
            out_pipeline);
        if (status != BG_STATUS_OK) return status;
        *out_pipeline = nullptr;
        auto pipeline = std::make_unique<bg_docking_fixed64_pipeline_v1>();
        status = bg_docking_geometric_admission_v1_create(
            context, admission_descriptor, &pipeline->admission);
        if (status != BG_STATUS_OK) return status;
        status = bg_docking_fixed64_refinement_pipeline_v1_create(
            context,
            rigid_descriptor,
            torsion_descriptor,
            scorer_descriptor,
            validity_descriptor,
            &pipeline->refinement);
        if (status != BG_STATUS_OK) {
            destroy_components(pipeline.get());
            return status;
        }
        status = validate_created_binding(
            *context,
            *pipeline->admission,
            *pipeline->refinement,
            *scorer_descriptor,
            *validity_descriptor);
        if (status != BG_STATUS_OK) {
            destroy_components(pipeline.get());
            return status;
        }
        pipeline->backend = context->backend;
        pipeline->unit_system = context->unit_system;
        pipeline->device_ordinal = context->device_ordinal;
        pipeline->receptor_atom_count = scorer_descriptor->receptor_atom_count;
        pipeline->ligand_atom_count = scorer_descriptor->ligand_atom_count;
        pipeline->admission_context_receipt_sha256 =
            admission_context_receipt(*context, *admission_descriptor);
        pipeline->refinement_context_receipt_sha256 =
            refinement_context_receipt(
                *context, *rigid_descriptor, *torsion_descriptor);
        pipeline->scorer_context_receipt_sha256 =
            scorer_context_receipt(*context, *scorer_descriptor);
        pipeline->validity_context_receipt_sha256 =
            validity_context_receipt(*context, *validity_descriptor);
        pipeline->component_binding_receipt_sha256 =
            component_binding_receipt(
                *context,
                pipeline->admission_context_receipt_sha256,
                pipeline->refinement_context_receipt_sha256,
                pipeline->scorer_context_receipt_sha256,
                pipeline->validity_context_receipt_sha256);
        *out_pipeline = pipeline.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_docking_fixed64_pipeline_v1_destroy(
    bg_docking_fixed64_pipeline_v1 *pipeline) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_pipeline;
    destroy_components(pipeline);
    delete pipeline;
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_v1_get_backend(
    const bg_docking_fixed64_pipeline_v1 *pipeline,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_pipeline;
    return guarded_status([&]() -> bg_status {
        if (pipeline == nullptr || backend == nullptr ||
            !pointer_is_aligned(pipeline) || !pointer_is_aligned(backend)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline and backend output are null or misaligned");
        }
        MemoryRange pipeline_range{};
        MemoryRange output_range{};
        if (!make_range(pipeline, 1, &pipeline_range) ||
            !make_range(backend, 1, &output_range)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "fixed64 complete pipeline backend range overflows");
        }
        if (overlaps(pipeline_range, output_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline backend output overlaps its handle");
        }
        *backend = pipeline->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API const char *BG_CALL bg_docking_fixed64_pipeline_v1_profile_id(
    void) BG_NOEXCEPT {
    return betelgeuze::native::docking::fixed64_pipeline::kProfileId;
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_v2_create(
    const bg_context *context,
    const bg_docking_geometric_admission_context_soa_v1 *admission_descriptor,
    const bg_docking_rigid_refinement_context_soa_v1 *rigid_descriptor,
    const bg_docking_torsion_v7_context_soa_v1 *torsion_descriptor,
    const bg_docking_scorer_v1_context_soa_v1 *scorer_descriptor,
    const bg_docking_pose_validity_context_soa_v1 *validity_descriptor,
    bg_docking_fixed64_pipeline_v2 **out_pipeline) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_pipeline;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || admission_descriptor == nullptr ||
            rigid_descriptor == nullptr || torsion_descriptor == nullptr ||
            scorer_descriptor == nullptr || validity_descriptor == nullptr ||
            out_pipeline == nullptr || !pointer_is_aligned(context) ||
            !pointer_is_aligned(admission_descriptor) ||
            !pointer_is_aligned(rigid_descriptor) ||
            !pointer_is_aligned(torsion_descriptor) ||
            !pointer_is_aligned(scorer_descriptor) ||
            !pointer_is_aligned(validity_descriptor) ||
            !pointer_is_aligned(out_pipeline)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline v2 create descriptors are null or misaligned");
        }
        bg_status status = validate_create_output_overlap(
            *context,
            *admission_descriptor,
            *rigid_descriptor,
            *torsion_descriptor,
            *scorer_descriptor,
            *validity_descriptor,
            reinterpret_cast<bg_docking_fixed64_pipeline_v1 **>(out_pipeline));
        if (status != BG_STATUS_OK) return status;
        bg_docking_fixed64_pipeline_v1 *components = nullptr;
        status = bg_docking_fixed64_pipeline_v1_create(
            context,
            admission_descriptor,
            rigid_descriptor,
            torsion_descriptor,
            scorer_descriptor,
            validity_descriptor,
            &components);
        if (status != BG_STATUS_OK) return status;
        std::unique_ptr<bg_docking_fixed64_pipeline_v2> pipeline(
            new (std::nothrow) bg_docking_fixed64_pipeline_v2{});
        if (!pipeline) {
            bg_docking_fixed64_pipeline_v1_destroy(components);
            return fail(
                BG_STATUS_OUT_OF_MEMORY,
                "fixed64 complete pipeline v2 allocation failed");
        }
        pipeline->components = components;
        *out_pipeline = pipeline.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_docking_fixed64_pipeline_v2_destroy(
    bg_docking_fixed64_pipeline_v2 *pipeline) BG_NOEXCEPT {
    if (pipeline == nullptr) return;
    bg_docking_fixed64_pipeline_v1_destroy(pipeline->components);
    pipeline->components = nullptr;
    delete pipeline;
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_v2_get_backend(
    const bg_docking_fixed64_pipeline_v2 *pipeline,
    bg_backend *backend) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        if (pipeline == nullptr || pipeline->components == nullptr ||
            backend == nullptr || !pointer_is_aligned(pipeline) ||
            !pointer_is_aligned(backend)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline v2 and backend output are null, invalid, or misaligned");
        }
        betelgeuze::native::docking::fixed64_pipeline::MemoryRange
            pipeline_range{};
        betelgeuze::native::docking::fixed64_pipeline::MemoryRange output_range{};
        if (!betelgeuze::native::docking::fixed64_pipeline::make_range(
                pipeline, 1, &pipeline_range) ||
            !betelgeuze::native::docking::fixed64_pipeline::make_range(
                backend, 1, &output_range)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "fixed64 complete pipeline v2 backend range overflows");
        }
        if (betelgeuze::native::docking::fixed64_pipeline::overlaps(
                pipeline_range, output_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline v2 backend output overlaps its handle");
        }
        *backend = pipeline->components->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API const char *BG_CALL bg_docking_fixed64_pipeline_v2_profile_id(
    void) BG_NOEXCEPT {
    return betelgeuze::native::docking::fixed64_pipeline::kProfileIdV2;
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_v1_run(
    const bg_context *context,
    const bg_docking_fixed64_pipeline_v1 *pipeline,
    const bg_docking_fixed64_pipeline_input_v1 *input,
    bg_docking_fixed64_producer_output_v1 *producer_output,
    bg_docking_rigid_refinement_output_v1 *rigid_output,
    bg_docking_torsion_v7_output_v1 *torsion_output,
    bg_docking_scorer_v1_output_v1 *scorer_output,
    bg_docking_pose_validity_output_v1 *validity_output,
    bg_docking_stable_top_k_output_v1 *ranking_output,
    bg_docking_rmsd_cluster_output_v1 *cluster_output,
    bg_docking_fixed64_refinement_output_v1 *refinement_output,
    bg_docking_fixed64_pipeline_output_v1 *pipeline_output) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_pipeline;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || pipeline == nullptr || input == nullptr ||
            producer_output == nullptr || rigid_output == nullptr ||
            torsion_output == nullptr || scorer_output == nullptr ||
            validity_output == nullptr || ranking_output == nullptr ||
            cluster_output == nullptr || refinement_output == nullptr ||
            pipeline_output == nullptr || !pointer_is_aligned(context) ||
            !pointer_is_aligned(pipeline) || !pointer_is_aligned(input) ||
            !pointer_is_aligned(producer_output) ||
            !pointer_is_aligned(rigid_output) ||
            !pointer_is_aligned(torsion_output) ||
            !pointer_is_aligned(scorer_output) ||
            !pointer_is_aligned(validity_output) ||
            !pointer_is_aligned(ranking_output) ||
            !pointer_is_aligned(cluster_output) ||
            !pointer_is_aligned(refinement_output) ||
            !pointer_is_aligned(pipeline_output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline run descriptors are null or misaligned");
        }
        if (context->backend != pipeline->backend ||
            context->unit_system != pipeline->unit_system ||
            context->device_ordinal != pipeline->device_ordinal ||
            pipeline->admission == nullptr || pipeline->refinement == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline context binding is invalid");
        }
        std::size_t coordinate_count = 0;
        bg_status status = validate_input(*pipeline, *input, &coordinate_count);
        if (status != BG_STATUS_OK) return status;
        status = validate_output(*pipeline, *pipeline_output);
        if (status != BG_STATUS_OK) return status;

        std::array<bg_docking_fixed64_producer_row_v1, kCandidateCount>
            local_producer_rows{};
        std::vector<double> local_x(coordinate_count, 0.0);
        std::vector<double> local_y(coordinate_count, 0.0);
        std::vector<double> local_z(coordinate_count, 0.0);
        bg_docking_fixed64_producer_output_v1 local_producer{};
        status = bg_docking_fixed64_producer_output_v1_init(
            &local_producer, sizeof(local_producer), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_producer.row_capacity = kCandidateCount;
        local_producer.coordinate_capacity = coordinate_count;
        local_producer.rows = local_producer_rows.data();
        local_producer.x_angstrom = local_x.data();
        local_producer.y_angstrom = local_y.data();
        local_producer.z_angstrom = local_z.data();
        status = bg_docking_fixed64_producer_v1_run(
            context,
            pipeline->admission,
            input->producer_input,
            &local_producer);
        if (status != BG_STATUS_OK) return status;

        std::array<bg_docking_rigid_refinement_candidate_mode, kCandidateCount>
            effective_modes{};
        std::array<double, kCandidateCount> quaternion_x{};
        std::array<double, kCandidateCount> quaternion_y{};
        std::array<double, kCandidateCount> quaternion_z{};
        std::array<double, kCandidateCount> quaternion_w{};
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            const auto &row = local_producer.rows[slot];
            const bool admitted =
                row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED &&
                row.geometric_admission.decision ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED &&
                row.geometric_admission.rank_eligible == UINT8_C(1);
            effective_modes[slot] =
                admitted
                    ? input->candidate_mode[slot]
                    : BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE;
            quaternion_x[slot] = admitted ? row.placement_quaternion_x : 0.0;
            quaternion_y[slot] = admitted ? row.placement_quaternion_y : 0.0;
            quaternion_z[slot] = admitted ? row.placement_quaternion_z : 0.0;
            quaternion_w[slot] = admitted ? row.placement_quaternion_w : 1.0;
        }
        bg_docking_fixed64_refinement_input_v1 refinement_input{};
        status = bg_docking_fixed64_refinement_input_v1_init(
            &refinement_input, sizeof(refinement_input), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        refinement_input.ligand_atom_count = pipeline->ligand_atom_count;
        refinement_input.rmsd_threshold_angstrom =
            input->rmsd_threshold_angstrom;
        refinement_input.candidate_mode = effective_modes.data();
        refinement_input.rigid_max_steps = input->rigid_max_steps;
        refinement_input.proposal_is_torsion_eligible =
            input->proposal_is_torsion_eligible;
        refinement_input.torsion_max_steps = input->torsion_max_steps;
        refinement_input.source_x_angstrom = local_x.data();
        refinement_input.source_y_angstrom = local_y.data();
        refinement_input.source_z_angstrom = local_z.data();
        refinement_input.baseline_torsion_angles_radians =
            input->baseline_torsion_angles_radians;
        refinement_input.source_quaternion_x = quaternion_x.data();
        refinement_input.source_quaternion_y = quaternion_y.data();
        refinement_input.source_quaternion_z = quaternion_z.data();
        refinement_input.source_quaternion_w = quaternion_w.data();

        status = betelgeuze::native::docking::fixed64_producer::
            validate_for_composition(
                *context,
                *pipeline->admission,
                *input->producer_input,
                *producer_output);
        if (status != BG_STATUS_OK) return status;
        status = betelgeuze::native::docking::refinement_pipeline::
            validate_for_composition(
                *context,
                *pipeline->refinement,
                refinement_input,
                *rigid_output,
                *torsion_output,
                *scorer_output,
                *validity_output,
                *ranking_output,
                *cluster_output,
                *refinement_output);
        if (status != BG_STATUS_OK) return status;
        status = validate_bridge_overlap(
            *context,
            *pipeline,
            *input,
            coordinate_count,
            *producer_output,
            *rigid_output,
            *torsion_output,
            *scorer_output,
            *validity_output,
            *ranking_output,
            *cluster_output,
            *refinement_output,
            *pipeline_output);
        if (status != BG_STATUS_OK) return status;

        status = bg_docking_fixed64_refinement_pipeline_v1_run(
            context,
            pipeline->refinement,
            &refinement_input,
            rigid_output,
            torsion_output,
            scorer_output,
            validity_output,
            ranking_output,
            cluster_output,
            refinement_output);
        if (status != BG_STATUS_OK) return status;

        const auto policy =
            policy_receipt(*pipeline, *input, local_producer, coordinate_count);
        std::array<bg_docking_fixed64_pipeline_row_v1, kCandidateCount> rows{};
        CanonicalHash refinement_batch(kRefinementEvidenceSchema);
        CanonicalHash scorer_batch(kScorerEvidenceSchema);
        CanonicalHash validity_batch(kValidityEvidenceSchema);
        CanonicalHash ranking_batch(kRankingEvidenceSchema);
        CanonicalHash cluster_batch(kClusterEvidenceSchema);
        refinement_batch.digest(pipeline->refinement_context_receipt_sha256);
        scorer_batch.digest(pipeline->scorer_context_receipt_sha256);
        validity_batch.digest(pipeline->validity_context_receipt_sha256);
        ranking_batch.digest(pipeline->component_binding_receipt_sha256);
        cluster_batch.digest(pipeline->component_binding_receipt_sha256);
        uint64_t initial_admitted_count = 0;
        uint64_t refined_count = 0;
        uint64_t scored_count = 0;
        uint64_t valid_count = 0;
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            const auto &producer_row = local_producer.rows[slot];
            const auto &refinement_row = refinement_output->rows[slot];
            const auto &scorer_row = scorer_output->rows[slot];
            const auto &validity_row = validity_output->rows[slot];
            const auto &ranking_row = ranking_output->rows[slot];
            const auto &cluster_row = cluster_output->rows[slot];
            auto &row = rows[slot];
            row.slot_index = static_cast<uint32_t>(slot);
            row.producer_status = producer_row.status;
            row.producer_failure_code = producer_row.failure_code;
            row.initial_admission_decision =
                producer_row.geometric_admission.decision;
            row.requested_refinement_mode = input->candidate_mode[slot];
            row.effective_refinement_mode = effective_modes[slot];
            row.refinement_status = refinement_row.status;
            row.refinement_failure_stage = refinement_row.failure_stage;
            row.scorer_status = scorer_row.status;
            row.scorer_failure_code = scorer_row.failure_code;
            row.validity_status = validity_row.status;
            row.validity_failure_code = validity_row.failure_code;
            row.stable_rank = ranking_row.stable_rank;
            row.stable_valid_rank = ranking_row.stable_valid_rank;
            row.cluster_status = cluster_row.status;
            row.cluster_id = cluster_row.cluster_id;
            row.cluster_rank = cluster_row.cluster_rank;
            row.top_k_rank = cluster_row.top_k_rank;
            std::copy_n(
                producer_row.row_receipt_sha256,
                32,
                row.producer_row_receipt_sha256);
            std::copy_n(
                refinement_row.coordinate_sha256,
                32,
                row.final_coordinate_sha256);
            const auto refinement_digest = refinement_evidence(
                slot,
                static_cast<std::size_t>(pipeline->ligand_atom_count),
                *rigid_output,
                *torsion_output,
                *refinement_output);
            const auto scorer_digest = scorer_evidence(scorer_row);
            const auto validity_digest = validity_evidence(validity_row);
            const auto ranking_digest = ranking_evidence(ranking_row);
            const auto cluster_digest = cluster_evidence(cluster_row);
            copy_digest(refinement_digest, row.refinement_evidence_sha256);
            copy_digest(scorer_digest, row.scorer_evidence_sha256);
            copy_digest(validity_digest, row.validity_evidence_sha256);
            copy_digest(ranking_digest, row.ranking_evidence_sha256);
            copy_digest(cluster_digest, row.cluster_evidence_sha256);
            CanonicalHash row_hash(kRowSchema);
            row_hash.string(kProfileId);
            row_hash.digest(pipeline->component_binding_receipt_sha256);
            row_hash.digest(policy);
            row_hash.u32(row.slot_index);
            row_hash.i32(row.producer_status);
            row_hash.i32(row.producer_failure_code);
            row_hash.i32(row.initial_admission_decision);
            row_hash.i32(row.requested_refinement_mode);
            row_hash.i32(row.effective_refinement_mode);
            row_hash.i32(row.refinement_status);
            row_hash.i32(row.refinement_failure_stage);
            row_hash.i32(row.scorer_status);
            row_hash.i32(row.scorer_failure_code);
            row_hash.i32(row.validity_status);
            row_hash.i32(row.validity_failure_code);
            row_hash.u32(row.stable_rank);
            row_hash.u32(row.stable_valid_rank);
            row_hash.i32(row.cluster_status);
            row_hash.u32(row.cluster_id);
            row_hash.u32(row.cluster_rank);
            row_hash.u32(row.top_k_rank);
            row_hash.digest(row.producer_row_receipt_sha256);
            row_hash.digest(row.final_coordinate_sha256);
            row_hash.digest(refinement_digest);
            row_hash.digest(scorer_digest);
            row_hash.digest(validity_digest);
            row_hash.digest(ranking_digest);
            row_hash.digest(cluster_digest);
            copy_digest(row_hash.finish(), row.row_receipt_sha256);
            refinement_batch.digest(refinement_digest);
            scorer_batch.digest(scorer_digest);
            validity_batch.digest(validity_digest);
            ranking_batch.digest(ranking_digest);
            cluster_batch.digest(cluster_digest);
            if (row.initial_admission_decision ==
                BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED) {
                ++initial_admitted_count;
            }
            if (row.refinement_status ==
                BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY) {
                ++refined_count;
            }
            if (row.scorer_status == BG_DOCKING_SCORER_V1_ROW_SCORED) {
                ++scored_count;
            }
            if (row.validity_status == BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED &&
                validity_row.blocker_mask == UINT32_C(0)) {
                ++valid_count;
            }
        }
        ranking_batch.u64(ranking_output->primary_index_count);
        for (uint64_t index = 0; index < ranking_output->primary_index_count;
             ++index) {
            ranking_batch.u32(ranking_output->primary_slot_indices[index]);
        }
        ranking_batch.u64(ranking_output->valid_index_count);
        for (uint64_t index = 0; index < ranking_output->valid_index_count;
             ++index) {
            ranking_batch.u32(ranking_output->valid_slot_indices[index]);
        }
        ranking_batch.byte(
            ranking_output->existing_rank_auto_change_authorized);
        ranking_batch.byte(ranking_output->customer_pose_emission_authorized);
        ranking_batch.byte(ranking_output->production_claim_authorized);
        cluster_batch.u64(cluster_output->representative_index_count);
        for (uint64_t index = 0;
             index < cluster_output->representative_index_count;
             ++index) {
            cluster_batch.u32(
                cluster_output->representative_slot_indices[index]);
        }
        cluster_batch.u64(cluster_output->top_k_index_count);
        for (uint64_t index = 0; index < cluster_output->top_k_index_count;
             ++index) {
            cluster_batch.u32(cluster_output->top_k_slot_indices[index]);
        }
        cluster_batch.byte(
            cluster_output->existing_rank_auto_change_authorized);
        cluster_batch.byte(cluster_output->customer_pose_emission_authorized);
        cluster_batch.byte(cluster_output->production_claim_authorized);
        const auto refinement_batch_digest = refinement_batch.finish();
        const auto scorer_batch_digest = scorer_batch.finish();
        const auto validity_batch_digest = validity_batch.finish();
        const auto ranking_batch_digest = ranking_batch.finish();
        const auto cluster_batch_digest = cluster_batch.finish();
        CanonicalHash batch(kBatchSchema);
        batch.string(kProfileId);
        batch.i32(pipeline->backend);
        batch.i32(pipeline->unit_system);
        batch.size(kCandidateCount);
        batch.digest(local_producer.allocation_receipt_sha256);
        batch.digest(local_producer.source_bundle_receipt_sha256);
        batch.digest(pipeline->admission_context_receipt_sha256);
        batch.digest(pipeline->refinement_context_receipt_sha256);
        batch.digest(pipeline->scorer_context_receipt_sha256);
        batch.digest(pipeline->validity_context_receipt_sha256);
        batch.digest(pipeline->component_binding_receipt_sha256);
        batch.digest(local_producer.producer_batch_receipt_sha256);
        batch.digest(policy);
        batch.digest(refinement_batch_digest);
        batch.digest(scorer_batch_digest);
        batch.digest(validity_batch_digest);
        batch.digest(ranking_batch_digest);
        batch.digest(cluster_batch_digest);
        batch.u64(local_producer.generated_count);
        batch.u64(initial_admitted_count);
        batch.u64(refined_count);
        batch.u64(scored_count);
        batch.u64(valid_count);
        batch.u64(cluster_output->representative_index_count);
        for (const auto &row : rows) batch.digest(row.row_receipt_sha256);
        batch.byte(UINT8_C(0));
        batch.byte(UINT8_C(0));
        batch.byte(UINT8_C(1));
        for (std::size_t index = 0; index < 7; ++index) batch.byte(UINT8_C(0));
        const auto batch_digest = batch.finish();

        const std::size_t coordinate_bytes = coordinate_count * sizeof(double);
        std::copy(rows.begin(), rows.end(), pipeline_output->rows);
        std::copy(local_producer_rows.begin(), local_producer_rows.end(), producer_output->rows);
        std::memcpy(producer_output->x_angstrom, local_x.data(), coordinate_bytes);
        std::memcpy(producer_output->y_angstrom, local_y.data(), coordinate_bytes);
        std::memcpy(producer_output->z_angstrom, local_z.data(), coordinate_bytes);
        bg_docking_fixed64_producer_output_v1 committed_producer = local_producer;
        committed_producer.row_capacity = producer_output->row_capacity;
        committed_producer.coordinate_capacity = producer_output->coordinate_capacity;
        committed_producer.rows = producer_output->rows;
        committed_producer.x_angstrom = producer_output->x_angstrom;
        committed_producer.y_angstrom = producer_output->y_angstrom;
        committed_producer.z_angstrom = producer_output->z_angstrom;
        *producer_output = committed_producer;

        bg_docking_fixed64_pipeline_output_v1 committed{};
        committed.struct_size = pipeline_output->struct_size;
        committed.abi_version = pipeline_output->abi_version;
        committed.row_capacity = pipeline_output->row_capacity;
        committed.row_count = kCandidateCount;
        committed.unit_system = pipeline->unit_system;
        committed.backend = pipeline->backend;
        committed.rows = pipeline_output->rows;
        committed.generated_count = local_producer.generated_count;
        committed.initial_admitted_count = initial_admitted_count;
        committed.refined_count = refined_count;
        committed.scored_count = scored_count;
        committed.valid_count = valid_count;
        committed.cluster_count = cluster_output->representative_index_count;
        std::copy_n(
            local_producer.allocation_receipt_sha256,
            32,
            committed.allocation_receipt_sha256);
        std::copy_n(
            local_producer.source_bundle_receipt_sha256,
            32,
            committed.source_bundle_receipt_sha256);
        copy_digest(
            pipeline->admission_context_receipt_sha256,
            committed.admission_context_receipt_sha256);
        copy_digest(
            pipeline->refinement_context_receipt_sha256,
            committed.refinement_context_receipt_sha256);
        copy_digest(
            pipeline->scorer_context_receipt_sha256,
            committed.scorer_context_receipt_sha256);
        copy_digest(
            pipeline->validity_context_receipt_sha256,
            committed.validity_context_receipt_sha256);
        copy_digest(
            pipeline->component_binding_receipt_sha256,
            committed.component_binding_receipt_sha256);
        std::copy_n(
            local_producer.producer_batch_receipt_sha256,
            32,
            committed.producer_batch_receipt_sha256);
        copy_digest(policy, committed.refinement_policy_receipt_sha256);
        copy_digest(
            refinement_batch_digest,
            committed.refinement_batch_receipt_sha256);
        copy_digest(scorer_batch_digest, committed.scorer_batch_receipt_sha256);
        copy_digest(validity_batch_digest, committed.validity_batch_receipt_sha256);
        copy_digest(ranking_batch_digest, committed.ranking_batch_receipt_sha256);
        copy_digest(cluster_batch_digest, committed.cluster_batch_receipt_sha256);
        copy_digest(batch_digest, committed.pipeline_batch_receipt_sha256);
        committed.result_dependent_input_consumed = UINT8_C(0);
        committed.fallback_allowed = UINT8_C(0);
        committed.denominator_preserved = UINT8_C(1);
        committed.molecular_execution_authorized = UINT8_C(0);
        committed.reservation_authorized = UINT8_C(0);
        committed.benchmark_execution_authorized = UINT8_C(0);
        committed.existing_rank_auto_change_authorized = UINT8_C(0);
        committed.customer_pose_emission_authorized = UINT8_C(0);
        committed.production_claim_authorized = UINT8_C(0);
        committed.scientific_claim_authorized = UINT8_C(0);
        *pipeline_output = committed;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_pipeline_v2_run(
    const bg_context *context,
    const bg_docking_fixed64_pipeline_v2 *pipeline,
    const bg_docking_fixed64_pipeline_input_v2 *input,
    bg_docking_fixed64_producer_output_v1 *producer_output,
    bg_docking_rigid_refinement_output_v1 *rigid_output,
    bg_docking_torsion_v7_output_v1 *torsion_output,
    bg_docking_fixed64_refinement_output_v1 *refinement_output,
    bg_docking_geometric_admission_output_v1 *post_admission_output,
    bg_docking_scorer_v1_output_v1 *scorer_output,
    bg_docking_pose_validity_output_v1 *validity_output,
    bg_docking_stable_top_k_output_v1 *ranking_output,
    bg_docking_rmsd_cluster_output_v1 *cluster_output,
    bg_docking_fixed64_pipeline_output_v2 *pipeline_output) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_pipeline;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || pipeline == nullptr || input == nullptr ||
            producer_output == nullptr || rigid_output == nullptr ||
            torsion_output == nullptr || refinement_output == nullptr ||
            post_admission_output == nullptr || scorer_output == nullptr ||
            validity_output == nullptr || ranking_output == nullptr ||
            cluster_output == nullptr || pipeline_output == nullptr ||
            !pointer_is_aligned(context) || !pointer_is_aligned(pipeline) ||
            !pointer_is_aligned(input) ||
            !pointer_is_aligned(producer_output) ||
            !pointer_is_aligned(rigid_output) ||
            !pointer_is_aligned(torsion_output) ||
            !pointer_is_aligned(refinement_output) ||
            !pointer_is_aligned(post_admission_output) ||
            !pointer_is_aligned(scorer_output) ||
            !pointer_is_aligned(validity_output) ||
            !pointer_is_aligned(ranking_output) ||
            !pointer_is_aligned(cluster_output) ||
            !pointer_is_aligned(pipeline_output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline v2 run descriptors are null or misaligned");
        }
        const auto *components = pipeline->components;
        if (components == nullptr || components->admission == nullptr ||
            components->refinement == nullptr ||
            components->refinement->downstream == nullptr ||
            components->refinement->downstream->ranker == nullptr ||
            context->backend != components->backend ||
            context->unit_system != components->unit_system ||
            context->device_ordinal != components->device_ordinal) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 complete pipeline v2 context binding is invalid");
        }

        std::size_t coordinate_count = 0;
        bg_docking_fixed64_pipeline_input_v1 input_view{};
        bg_status status = validate_input_v2(
            *components,
            *input,
            &coordinate_count,
            &input_view);
        if (status != BG_STATUS_OK) return status;
        status = validate_output_v2(*components, *pipeline_output);
        if (status != BG_STATUS_OK) return status;
        status = validate_post_admission_output(
            *components, *post_admission_output);
        if (status != BG_STATUS_OK) return status;

        std::array<bg_docking_fixed64_producer_row_v1, kCandidateCount>
            local_producer_rows{};
        std::vector<double> producer_x(coordinate_count, 0.0);
        std::vector<double> producer_y(coordinate_count, 0.0);
        std::vector<double> producer_z(coordinate_count, 0.0);
        bg_docking_fixed64_producer_output_v1 local_producer{};
        status = bg_docking_fixed64_producer_output_v1_init(
            &local_producer, sizeof(local_producer), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_producer.row_capacity = kCandidateCount;
        local_producer.coordinate_capacity = coordinate_count;
        local_producer.rows = local_producer_rows.data();
        local_producer.x_angstrom = producer_x.data();
        local_producer.y_angstrom = producer_y.data();
        local_producer.z_angstrom = producer_z.data();
        status = bg_docking_fixed64_producer_v1_run(
            context,
            components->admission,
            input->producer_input,
            &local_producer);
        if (status != BG_STATUS_OK) return status;

        std::array<bg_docking_rigid_refinement_candidate_mode, kCandidateCount>
            effective_modes{};
        std::array<double, kCandidateCount> source_quaternion_x{};
        std::array<double, kCandidateCount> source_quaternion_y{};
        std::array<double, kCandidateCount> source_quaternion_z{};
        std::array<double, kCandidateCount> source_quaternion_w{};
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            const auto &row = local_producer_rows[slot];
            const bool admitted =
                row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED &&
                row.geometric_admission.decision ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED &&
                row.geometric_admission.rank_eligible == UINT8_C(1);
            effective_modes[slot] =
                admitted
                    ? input->candidate_mode[slot]
                    : BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE;
            source_quaternion_x[slot] =
                admitted ? row.placement_quaternion_x : 0.0;
            source_quaternion_y[slot] =
                admitted ? row.placement_quaternion_y : 0.0;
            source_quaternion_z[slot] =
                admitted ? row.placement_quaternion_z : 0.0;
            source_quaternion_w[slot] =
                admitted ? row.placement_quaternion_w : 1.0;
        }
        bg_docking_fixed64_refinement_input_v1 refinement_input{};
        status = bg_docking_fixed64_refinement_input_v1_init(
            &refinement_input, sizeof(refinement_input), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        refinement_input.ligand_atom_count = components->ligand_atom_count;
        refinement_input.rmsd_threshold_angstrom =
            input->rmsd_threshold_angstrom;
        refinement_input.candidate_mode = effective_modes.data();
        refinement_input.rigid_max_steps = input->rigid_max_steps;
        refinement_input.proposal_is_torsion_eligible =
            input->proposal_is_torsion_eligible;
        refinement_input.torsion_max_steps = input->torsion_max_steps;
        refinement_input.source_x_angstrom = producer_x.data();
        refinement_input.source_y_angstrom = producer_y.data();
        refinement_input.source_z_angstrom = producer_z.data();
        refinement_input.baseline_torsion_angles_radians =
            input->baseline_torsion_angles_radians;
        refinement_input.source_quaternion_x = source_quaternion_x.data();
        refinement_input.source_quaternion_y = source_quaternion_y.data();
        refinement_input.source_quaternion_z = source_quaternion_z.data();
        refinement_input.source_quaternion_w = source_quaternion_w.data();

        status = betelgeuze::native::docking::fixed64_producer::
            validate_for_composition(
                *context,
                *components->admission,
                *input->producer_input,
                *producer_output);
        if (status != BG_STATUS_OK) return status;
        status = betelgeuze::native::docking::refinement_pipeline::
            validate_for_composition(
                *context,
                *components->refinement,
                refinement_input,
                *rigid_output,
                *torsion_output,
                *scorer_output,
                *validity_output,
                *ranking_output,
                *cluster_output,
                *refinement_output);
        if (status != BG_STATUS_OK) return status;
        status = validate_v2_overlap(
            *context,
            *pipeline,
            *components,
            *input,
            coordinate_count,
            *producer_output,
            *rigid_output,
            *torsion_output,
            *scorer_output,
            *validity_output,
            *ranking_output,
            *cluster_output,
            *refinement_output,
            *post_admission_output,
            *pipeline_output);
        if (status != BG_STATUS_OK) return status;

        std::array<bg_docking_rigid_refinement_row_v1, kCandidateCount>
            rigid_rows{};
        std::array<std::vector<double>, 12> rigid_coordinates;
        for (auto &values : rigid_coordinates) values.resize(coordinate_count);
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

        std::array<bg_docking_torsion_v7_row_v1, kCandidateCount>
            torsion_rows{};
        std::array<
            bg_docking_torsion_v7_move_v1,
            kCandidateCount * kMovesPerCandidate>
            torsion_moves{};
        std::array<std::vector<double>, 8> torsion_coordinates;
        for (auto &values : torsion_coordinates) values.resize(coordinate_count);
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

        std::array<bg_docking_fixed64_refinement_row_v1, kCandidateCount>
            refinement_rows{};
        std::array<std::vector<double>, 3> final_coordinates;
        for (auto &values : final_coordinates) values.resize(coordinate_count);
        std::array<std::array<double, kCandidateCount>, 4> final_quaternions{};
        bg_docking_fixed64_refinement_output_v1 local_refinement{};
        status = bg_docking_fixed64_refinement_output_v1_init(
            &local_refinement, sizeof(local_refinement), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_refinement.row_capacity = kCandidateCount;
        local_refinement.coordinate_capacity = coordinate_count;
        local_refinement.quaternion_capacity = kCandidateCount;
        local_refinement.rows = refinement_rows.data();
        local_refinement.final_x_angstrom = final_coordinates[0].data();
        local_refinement.final_y_angstrom = final_coordinates[1].data();
        local_refinement.final_z_angstrom = final_coordinates[2].data();
        local_refinement.final_quaternion_x = final_quaternions[0].data();
        local_refinement.final_quaternion_y = final_quaternions[1].data();
        local_refinement.final_quaternion_z = final_quaternions[2].data();
        local_refinement.final_quaternion_w = final_quaternions[3].data();
        status = betelgeuze::native::docking::refinement_pipeline::
            run_stage_for_composition(
                *context,
                *components->refinement,
                refinement_input,
                local_rigid,
                local_torsion,
                local_refinement);
        if (status != BG_STATUS_OK) return status;

        std::array<bg_docking_geometric_admission_candidate_state,
                   kCandidateCount>
            post_states{};
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            if (refinement_rows[slot].status ==
                    BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY &&
                refinement_rows[slot].coordinate_available == UINT8_C(1)) {
                post_states[slot] =
                    BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
            }
        }
        bg_docking_geometric_admission_candidate_batch_soa_v1 post_batch{};
        status = bg_docking_geometric_admission_candidate_batch_soa_v1_init(
            &post_batch, sizeof(post_batch), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        post_batch.candidate_count = kCandidateCount;
        post_batch.ligand_atom_count = components->ligand_atom_count;
        post_batch.candidate_state = post_states.data();
        post_batch.x_angstrom = final_coordinates[0].data();
        post_batch.y_angstrom = final_coordinates[1].data();
        post_batch.z_angstrom = final_coordinates[2].data();
        std::array<bg_docking_geometric_admission_row_v1, kCandidateCount>
            post_rows{};
        bg_docking_geometric_admission_output_v1 local_post{};
        status = bg_docking_geometric_admission_output_v1_init(
            &local_post, sizeof(local_post), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_post.row_capacity = kCandidateCount;
        local_post.rows = post_rows.data();
        status = bg_docking_geometric_admission_v1_evaluate_fixed64(
            context, components->admission, &post_batch, &local_post);
        if (status != BG_STATUS_OK) return status;

        std::array<bg_docking_scorer_v1_candidate_state, kCandidateCount>
            downstream_states{};
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            const auto &post = post_rows[slot];
            const bool admitted =
                post.status == BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED &&
                post.failure_code ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE &&
                post.decision ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED &&
                post.rank_eligible == UINT8_C(1);
            downstream_states[slot] =
                admitted ? BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE
                         : BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE;
            refinement_rows[slot].downstream_candidate_state =
                downstream_states[slot];
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
        downstream_batch.ligand_atom_count = components->ligand_atom_count;
        downstream_batch.candidate_state = downstream_states.data();
        downstream_batch.x_angstrom = final_coordinates[0].data();
        downstream_batch.y_angstrom = final_coordinates[1].data();
        downstream_batch.z_angstrom = final_coordinates[2].data();
        status = bg_docking_fixed64_downstream_v1_run(
            context,
            components->refinement->downstream,
            &downstream_batch,
            final_quaternions[0].data(),
            final_quaternions[1].data(),
            final_quaternions[2].data(),
            final_quaternions[3].data(),
            &local_scorer,
            &local_validity,
            &local_ranking);
        if (status != BG_STATUS_OK) return status;

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
        cluster_input.ligand_atom_count = components->ligand_atom_count;
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
            components->refinement->downstream->ranker,
            &cluster_input,
            &local_cluster);
        if (status != BG_STATUS_OK) return status;

        const auto refinement_policy = policy_receipt_v2(
            *components, *input, local_producer, coordinate_count);
        const auto post_policy = post_admission_policy_receipt_v2(
            *components, *input, local_producer, refinement_policy);
        std::array<bg_docking_fixed64_pipeline_row_v2, kCandidateCount> rows{};
        CanonicalHash refinement_batch(kRefinementEvidenceSchema);
        CanonicalHash scorer_batch(kScorerEvidenceSchema);
        CanonicalHash validity_batch(kValidityEvidenceSchema);
        CanonicalHash ranking_batch(kRankingEvidenceSchema);
        CanonicalHash cluster_batch(kClusterEvidenceSchema);
        refinement_batch.digest(
            components->refinement_context_receipt_sha256);
        scorer_batch.digest(components->scorer_context_receipt_sha256);
        validity_batch.digest(components->validity_context_receipt_sha256);
        ranking_batch.digest(components->component_binding_receipt_sha256);
        cluster_batch.digest(components->component_binding_receipt_sha256);
        uint64_t initial_admitted_count = 0;
        uint64_t refined_count = 0;
        uint64_t post_admitted_count = 0;
        uint64_t post_rejected_count = 0;
        uint64_t scored_count = 0;
        uint64_t valid_count = 0;
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            const auto &producer_row = local_producer_rows[slot];
            const auto &refinement_row = refinement_rows[slot];
            const auto &post_row = post_rows[slot];
            const auto &scorer_row = scorer_rows[slot];
            const auto &validity_row = validity_rows[slot];
            const auto &ranking_row = ranking_rows[slot];
            const auto &cluster_row = cluster_rows[slot];
            auto &row = rows[slot];
            row.slot_index = static_cast<uint32_t>(slot);
            row.producer_status = producer_row.status;
            row.producer_failure_code = producer_row.failure_code;
            row.initial_admission_decision =
                producer_row.geometric_admission.decision;
            row.requested_refinement_mode = input->candidate_mode[slot];
            row.effective_refinement_mode = effective_modes[slot];
            row.refinement_status = refinement_row.status;
            row.refinement_failure_stage = refinement_row.failure_stage;
            row.post_admission_status = post_row.status;
            row.post_admission_failure_code = post_row.failure_code;
            row.post_admission_decision = post_row.decision;
            row.post_admission_rank_eligible = post_row.rank_eligible;
            row.scorer_status = scorer_row.status;
            row.scorer_failure_code = scorer_row.failure_code;
            row.validity_status = validity_row.status;
            row.validity_failure_code = validity_row.failure_code;
            row.stable_rank = ranking_row.stable_rank;
            row.stable_valid_rank = ranking_row.stable_valid_rank;
            row.cluster_status = cluster_row.status;
            row.cluster_id = cluster_row.cluster_id;
            row.cluster_rank = cluster_row.cluster_rank;
            row.top_k_rank = cluster_row.top_k_rank;
            std::copy_n(
                producer_row.row_receipt_sha256,
                32,
                row.producer_row_receipt_sha256);
            std::copy_n(
                refinement_row.coordinate_sha256,
                32,
                row.final_coordinate_sha256);
            std::copy_n(
                post_row.row_receipt_sha256,
                32,
                row.post_admission_row_receipt_sha256);
            const auto refinement_digest = refinement_evidence(
                slot,
                static_cast<std::size_t>(components->ligand_atom_count),
                local_rigid,
                local_torsion,
                local_refinement);
            const auto scorer_digest = scorer_evidence(scorer_row);
            const auto validity_digest = validity_evidence(validity_row);
            const auto ranking_digest = ranking_evidence(ranking_row);
            const auto cluster_digest = cluster_evidence(cluster_row);
            copy_digest(refinement_digest, row.refinement_evidence_sha256);
            copy_digest(scorer_digest, row.scorer_evidence_sha256);
            copy_digest(validity_digest, row.validity_evidence_sha256);
            copy_digest(ranking_digest, row.ranking_evidence_sha256);
            copy_digest(cluster_digest, row.cluster_evidence_sha256);
            CanonicalHash row_hash(kRowSchemaV2);
            row_hash.string(kProfileIdV2);
            row_hash.digest(components->component_binding_receipt_sha256);
            row_hash.digest(refinement_policy);
            row_hash.digest(post_policy);
            row_hash.u32(row.slot_index);
            row_hash.i32(row.producer_status);
            row_hash.i32(row.producer_failure_code);
            row_hash.i32(row.initial_admission_decision);
            row_hash.i32(row.requested_refinement_mode);
            row_hash.i32(row.effective_refinement_mode);
            row_hash.i32(row.refinement_status);
            row_hash.i32(row.refinement_failure_stage);
            row_hash.i32(row.post_admission_status);
            row_hash.i32(row.post_admission_failure_code);
            row_hash.i32(row.post_admission_decision);
            row_hash.byte(row.post_admission_rank_eligible);
            row_hash.i32(row.scorer_status);
            row_hash.i32(row.scorer_failure_code);
            row_hash.i32(row.validity_status);
            row_hash.i32(row.validity_failure_code);
            row_hash.u32(row.stable_rank);
            row_hash.u32(row.stable_valid_rank);
            row_hash.i32(row.cluster_status);
            row_hash.u32(row.cluster_id);
            row_hash.u32(row.cluster_rank);
            row_hash.u32(row.top_k_rank);
            row_hash.digest(row.producer_row_receipt_sha256);
            row_hash.digest(row.final_coordinate_sha256);
            row_hash.digest(refinement_digest);
            row_hash.digest(row.post_admission_row_receipt_sha256);
            row_hash.digest(scorer_digest);
            row_hash.digest(validity_digest);
            row_hash.digest(ranking_digest);
            row_hash.digest(cluster_digest);
            copy_digest(row_hash.finish(), row.row_receipt_sha256);
            refinement_batch.digest(refinement_digest);
            scorer_batch.digest(scorer_digest);
            validity_batch.digest(validity_digest);
            ranking_batch.digest(ranking_digest);
            cluster_batch.digest(cluster_digest);
            if (row.initial_admission_decision ==
                BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED) {
                ++initial_admitted_count;
            }
            const bool coordinate_ready =
                row.refinement_status ==
                BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
            if (coordinate_ready) ++refined_count;
            const bool post_admitted =
                row.post_admission_status ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED &&
                row.post_admission_decision ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED &&
                row.post_admission_rank_eligible == UINT8_C(1);
            if (post_admitted) {
                ++post_admitted_count;
            } else if (coordinate_ready) {
                ++post_rejected_count;
            }
            if (row.scorer_status == BG_DOCKING_SCORER_V1_ROW_SCORED) {
                ++scored_count;
            }
            if (row.validity_status ==
                    BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED &&
                validity_row.blocker_mask == UINT32_C(0)) {
                ++valid_count;
            }
        }
        ranking_batch.u64(local_ranking.primary_index_count);
        for (uint64_t index = 0; index < local_ranking.primary_index_count;
             ++index) {
            ranking_batch.u32(primary_indices[index]);
        }
        ranking_batch.u64(local_ranking.valid_index_count);
        for (uint64_t index = 0; index < local_ranking.valid_index_count;
             ++index) {
            ranking_batch.u32(valid_indices[index]);
        }
        ranking_batch.byte(
            local_ranking.existing_rank_auto_change_authorized);
        ranking_batch.byte(local_ranking.customer_pose_emission_authorized);
        ranking_batch.byte(local_ranking.production_claim_authorized);
        cluster_batch.u64(local_cluster.representative_index_count);
        for (uint64_t index = 0;
             index < local_cluster.representative_index_count;
             ++index) {
            cluster_batch.u32(representative_indices[index]);
        }
        cluster_batch.u64(local_cluster.top_k_index_count);
        for (uint64_t index = 0; index < local_cluster.top_k_index_count;
             ++index) {
            cluster_batch.u32(cluster_top_k_indices[index]);
        }
        cluster_batch.byte(
            local_cluster.existing_rank_auto_change_authorized);
        cluster_batch.byte(local_cluster.customer_pose_emission_authorized);
        cluster_batch.byte(local_cluster.production_claim_authorized);
        const auto refinement_batch_digest = refinement_batch.finish();
        const auto scorer_batch_digest = scorer_batch.finish();
        const auto validity_batch_digest = validity_batch.finish();
        const auto ranking_batch_digest = ranking_batch.finish();
        const auto cluster_batch_digest = cluster_batch.finish();
        CanonicalHash batch(kBatchSchemaV2);
        batch.string(kProfileIdV2);
        batch.i32(components->backend);
        batch.i32(components->unit_system);
        batch.size(kCandidateCount);
        batch.digest(local_producer.allocation_receipt_sha256);
        batch.digest(local_producer.source_bundle_receipt_sha256);
        batch.digest(components->admission_context_receipt_sha256);
        batch.digest(components->refinement_context_receipt_sha256);
        batch.digest(components->scorer_context_receipt_sha256);
        batch.digest(components->validity_context_receipt_sha256);
        batch.digest(components->component_binding_receipt_sha256);
        batch.digest(local_producer.producer_batch_receipt_sha256);
        batch.digest(refinement_policy);
        batch.digest(refinement_batch_digest);
        batch.digest(post_policy);
        batch.digest(local_post.batch_receipt_sha256);
        batch.digest(scorer_batch_digest);
        batch.digest(validity_batch_digest);
        batch.digest(ranking_batch_digest);
        batch.digest(cluster_batch_digest);
        batch.u64(local_producer.generated_count);
        batch.u64(initial_admitted_count);
        batch.u64(refined_count);
        batch.u64(post_admitted_count);
        batch.u64(post_rejected_count);
        batch.u64(scored_count);
        batch.u64(valid_count);
        batch.u64(local_cluster.representative_index_count);
        for (const auto &row : rows) batch.digest(row.row_receipt_sha256);
        batch.byte(UINT8_C(0));
        batch.byte(UINT8_C(0));
        batch.byte(UINT8_C(1));
        for (std::size_t index = 0; index < 7; ++index) {
            batch.byte(UINT8_C(0));
        }
        const auto batch_digest = batch.finish();

        const std::size_t coordinate_bytes = coordinate_count * sizeof(double);
        std::copy(
            local_producer_rows.begin(),
            local_producer_rows.end(),
            producer_output->rows);
        std::memcpy(
            producer_output->x_angstrom,
            producer_x.data(),
            coordinate_bytes);
        std::memcpy(
            producer_output->y_angstrom,
            producer_y.data(),
            coordinate_bytes);
        std::memcpy(
            producer_output->z_angstrom,
            producer_z.data(),
            coordinate_bytes);
        bg_docking_fixed64_producer_output_v1 committed_producer =
            local_producer;
        committed_producer.row_capacity = producer_output->row_capacity;
        committed_producer.coordinate_capacity =
            producer_output->coordinate_capacity;
        committed_producer.rows = producer_output->rows;
        committed_producer.x_angstrom = producer_output->x_angstrom;
        committed_producer.y_angstrom = producer_output->y_angstrom;
        committed_producer.z_angstrom = producer_output->z_angstrom;
        *producer_output = committed_producer;

        std::copy(rigid_rows.begin(), rigid_rows.end(), rigid_output->rows);
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
            std::copy_n(
                rigid_coordinates[index].data(),
                coordinate_count,
                rigid_destinations[index]);
        }
        bg_docking_rigid_refinement_output_v1 committed_rigid = local_rigid;
        committed_rigid.row_capacity = rigid_output->row_capacity;
        committed_rigid.coordinate_capacity =
            rigid_output->coordinate_capacity;
        committed_rigid.rows = rigid_output->rows;
        committed_rigid.selected_x_angstrom =
            rigid_output->selected_x_angstrom;
        committed_rigid.selected_y_angstrom =
            rigid_output->selected_y_angstrom;
        committed_rigid.selected_z_angstrom =
            rigid_output->selected_z_angstrom;
        committed_rigid.comparison_v2_x_angstrom =
            rigid_output->comparison_v2_x_angstrom;
        committed_rigid.comparison_v2_y_angstrom =
            rigid_output->comparison_v2_y_angstrom;
        committed_rigid.comparison_v2_z_angstrom =
            rigid_output->comparison_v2_z_angstrom;
        committed_rigid.baseline_v3_x_angstrom =
            rigid_output->baseline_v3_x_angstrom;
        committed_rigid.baseline_v3_y_angstrom =
            rigid_output->baseline_v3_y_angstrom;
        committed_rigid.baseline_v3_z_angstrom =
            rigid_output->baseline_v3_z_angstrom;
        committed_rigid.clearance_v4_x_angstrom =
            rigid_output->clearance_v4_x_angstrom;
        committed_rigid.clearance_v4_y_angstrom =
            rigid_output->clearance_v4_y_angstrom;
        committed_rigid.clearance_v4_z_angstrom =
            rigid_output->clearance_v4_z_angstrom;
        *rigid_output = committed_rigid;

        std::copy(torsion_rows.begin(), torsion_rows.end(), torsion_output->rows);
        std::copy(
            torsion_moves.begin(),
            torsion_moves.end(),
            torsion_output->moves);
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
        for (std::size_t index = 0; index < torsion_destinations.size();
             ++index) {
            std::copy_n(
                torsion_coordinates[index].data(),
                coordinate_count,
                torsion_destinations[index]);
        }
        bg_docking_torsion_v7_output_v1 committed_torsion = local_torsion;
        committed_torsion.row_capacity = torsion_output->row_capacity;
        committed_torsion.move_capacity = torsion_output->move_capacity;
        committed_torsion.coordinate_capacity =
            torsion_output->coordinate_capacity;
        committed_torsion.rows = torsion_output->rows;
        committed_torsion.moves = torsion_output->moves;
        committed_torsion.optimized_x_angstrom =
            torsion_output->optimized_x_angstrom;
        committed_torsion.optimized_y_angstrom =
            torsion_output->optimized_y_angstrom;
        committed_torsion.optimized_z_angstrom =
            torsion_output->optimized_z_angstrom;
        committed_torsion.optimized_torsion_angles_radians =
            torsion_output->optimized_torsion_angles_radians;
        committed_torsion.final_x_angstrom = torsion_output->final_x_angstrom;
        committed_torsion.final_y_angstrom = torsion_output->final_y_angstrom;
        committed_torsion.final_z_angstrom = torsion_output->final_z_angstrom;
        committed_torsion.final_torsion_angles_radians =
            torsion_output->final_torsion_angles_radians;
        *torsion_output = committed_torsion;

        std::copy(
            refinement_rows.begin(),
            refinement_rows.end(),
            refinement_output->rows);
        std::copy_n(
            final_coordinates[0].data(),
            coordinate_count,
            refinement_output->final_x_angstrom);
        std::copy_n(
            final_coordinates[1].data(),
            coordinate_count,
            refinement_output->final_y_angstrom);
        std::copy_n(
            final_coordinates[2].data(),
            coordinate_count,
            refinement_output->final_z_angstrom);
        std::copy_n(
            final_quaternions[0].data(),
            kCandidateCount,
            refinement_output->final_quaternion_x);
        std::copy_n(
            final_quaternions[1].data(),
            kCandidateCount,
            refinement_output->final_quaternion_y);
        std::copy_n(
            final_quaternions[2].data(),
            kCandidateCount,
            refinement_output->final_quaternion_z);
        std::copy_n(
            final_quaternions[3].data(),
            kCandidateCount,
            refinement_output->final_quaternion_w);
        bg_docking_fixed64_refinement_output_v1 committed_refinement =
            local_refinement;
        committed_refinement.row_capacity = refinement_output->row_capacity;
        committed_refinement.coordinate_capacity =
            refinement_output->coordinate_capacity;
        committed_refinement.quaternion_capacity =
            refinement_output->quaternion_capacity;
        committed_refinement.rows = refinement_output->rows;
        committed_refinement.final_x_angstrom =
            refinement_output->final_x_angstrom;
        committed_refinement.final_y_angstrom =
            refinement_output->final_y_angstrom;
        committed_refinement.final_z_angstrom =
            refinement_output->final_z_angstrom;
        committed_refinement.final_quaternion_x =
            refinement_output->final_quaternion_x;
        committed_refinement.final_quaternion_y =
            refinement_output->final_quaternion_y;
        committed_refinement.final_quaternion_z =
            refinement_output->final_quaternion_z;
        committed_refinement.final_quaternion_w =
            refinement_output->final_quaternion_w;
        *refinement_output = committed_refinement;

        std::copy(post_rows.begin(), post_rows.end(), post_admission_output->rows);
        bg_docking_geometric_admission_output_v1 committed_post = local_post;
        committed_post.row_capacity = post_admission_output->row_capacity;
        committed_post.rows = post_admission_output->rows;
        *post_admission_output = committed_post;

        std::copy(scorer_rows.begin(), scorer_rows.end(), scorer_output->rows);
        bg_docking_scorer_v1_output_v1 committed_scorer = local_scorer;
        committed_scorer.row_capacity = scorer_output->row_capacity;
        committed_scorer.rows = scorer_output->rows;
        *scorer_output = committed_scorer;
        std::copy(
            validity_rows.begin(), validity_rows.end(), validity_output->rows);
        bg_docking_pose_validity_output_v1 committed_validity =
            local_validity;
        committed_validity.row_capacity = validity_output->row_capacity;
        committed_validity.rows = validity_output->rows;
        *validity_output = committed_validity;
        std::copy(ranking_rows.begin(), ranking_rows.end(), ranking_output->rows);
        std::copy(
            primary_indices.begin(),
            primary_indices.end(),
            ranking_output->primary_slot_indices);
        std::copy(
            valid_indices.begin(),
            valid_indices.end(),
            ranking_output->valid_slot_indices);
        bg_docking_stable_top_k_output_v1 committed_ranking = local_ranking;
        committed_ranking.row_capacity = ranking_output->row_capacity;
        committed_ranking.primary_index_capacity =
            ranking_output->primary_index_capacity;
        committed_ranking.valid_index_capacity =
            ranking_output->valid_index_capacity;
        committed_ranking.rows = ranking_output->rows;
        committed_ranking.primary_slot_indices =
            ranking_output->primary_slot_indices;
        committed_ranking.valid_slot_indices =
            ranking_output->valid_slot_indices;
        *ranking_output = committed_ranking;
        std::copy(cluster_rows.begin(), cluster_rows.end(), cluster_output->rows);
        std::copy(
            representative_indices.begin(),
            representative_indices.end(),
            cluster_output->representative_slot_indices);
        std::copy(
            cluster_top_k_indices.begin(),
            cluster_top_k_indices.end(),
            cluster_output->top_k_slot_indices);
        bg_docking_rmsd_cluster_output_v1 committed_cluster = local_cluster;
        committed_cluster.row_capacity = cluster_output->row_capacity;
        committed_cluster.representative_index_capacity =
            cluster_output->representative_index_capacity;
        committed_cluster.top_k_index_capacity =
            cluster_output->top_k_index_capacity;
        committed_cluster.rows = cluster_output->rows;
        committed_cluster.representative_slot_indices =
            cluster_output->representative_slot_indices;
        committed_cluster.top_k_slot_indices =
            cluster_output->top_k_slot_indices;
        *cluster_output = committed_cluster;

        std::copy(rows.begin(), rows.end(), pipeline_output->rows);
        bg_docking_fixed64_pipeline_output_v2 committed{};
        committed.struct_size = pipeline_output->struct_size;
        committed.abi_version = pipeline_output->abi_version;
        committed.row_capacity = pipeline_output->row_capacity;
        committed.row_count = kCandidateCount;
        committed.unit_system = components->unit_system;
        committed.backend = components->backend;
        committed.rows = pipeline_output->rows;
        committed.generated_count = local_producer.generated_count;
        committed.initial_admitted_count = initial_admitted_count;
        committed.refined_count = refined_count;
        committed.post_admitted_count = post_admitted_count;
        committed.post_rejected_count = post_rejected_count;
        committed.scored_count = scored_count;
        committed.valid_count = valid_count;
        committed.cluster_count = local_cluster.representative_index_count;
        std::copy_n(
            local_producer.allocation_receipt_sha256,
            32,
            committed.allocation_receipt_sha256);
        std::copy_n(
            local_producer.source_bundle_receipt_sha256,
            32,
            committed.source_bundle_receipt_sha256);
        copy_digest(
            components->admission_context_receipt_sha256,
            committed.admission_context_receipt_sha256);
        copy_digest(
            components->refinement_context_receipt_sha256,
            committed.refinement_context_receipt_sha256);
        copy_digest(
            components->scorer_context_receipt_sha256,
            committed.scorer_context_receipt_sha256);
        copy_digest(
            components->validity_context_receipt_sha256,
            committed.validity_context_receipt_sha256);
        copy_digest(
            components->component_binding_receipt_sha256,
            committed.component_binding_receipt_sha256);
        std::copy_n(
            local_producer.producer_batch_receipt_sha256,
            32,
            committed.producer_batch_receipt_sha256);
        copy_digest(
            refinement_policy,
            committed.refinement_policy_receipt_sha256);
        copy_digest(
            refinement_batch_digest,
            committed.refinement_batch_receipt_sha256);
        copy_digest(
            post_policy,
            committed.post_admission_policy_receipt_sha256);
        std::copy_n(
            local_post.batch_receipt_sha256,
            32,
            committed.post_admission_batch_receipt_sha256);
        copy_digest(
            scorer_batch_digest, committed.scorer_batch_receipt_sha256);
        copy_digest(
            validity_batch_digest, committed.validity_batch_receipt_sha256);
        copy_digest(
            ranking_batch_digest, committed.ranking_batch_receipt_sha256);
        copy_digest(
            cluster_batch_digest, committed.cluster_batch_receipt_sha256);
        copy_digest(batch_digest, committed.pipeline_batch_receipt_sha256);
        committed.result_dependent_input_consumed = UINT8_C(0);
        committed.fallback_allowed = UINT8_C(0);
        committed.denominator_preserved = UINT8_C(1);
        committed.molecular_execution_authorized = UINT8_C(0);
        committed.reservation_authorized = UINT8_C(0);
        committed.benchmark_execution_authorized = UINT8_C(0);
        committed.existing_rank_auto_change_authorized = UINT8_C(0);
        committed.customer_pose_emission_authorized = UINT8_C(0);
        committed.production_claim_authorized = UINT8_C(0);
        committed.scientific_claim_authorized = UINT8_C(0);
        *pipeline_output = committed;
        return BG_STATUS_OK;
    });
}
