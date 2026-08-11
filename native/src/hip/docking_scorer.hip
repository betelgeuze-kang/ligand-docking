#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <memory>
#include <new>

namespace {

constexpr size_t kScorerCandidateCount = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr size_t kScorerTermCount = BG_DOCKING_SCORER_V1_TERM_COUNT;
constexpr size_t kScorerMaxLigandAtoms = 512;
constexpr size_t kScorerMaxReceptorAtoms = 4096;
constexpr double kScorerMaxCoordinate = 100000.0;
constexpr size_t kScorerNoDonor = static_cast<size_t>(-1);

struct ScorerDeviceContext final {
    size_t receptor_atom_count;
    size_t ligand_atom_count;
    const double *receptor_x;
    const double *receptor_y;
    const double *receptor_z;
    const double *receptor_charge;
    const double *receptor_radius;
    const double *receptor_epsilon;
    const uint8_t *receptor_hydrophobic;
    const uint8_t *receptor_acceptor;
    const size_t *receptor_donor_by_hydrogen;
    const double *ligand_charge;
    const double *ligand_radius;
    const double *ligand_epsilon;
    const uint8_t *ligand_hydrophobic;
    const uint8_t *ligand_acceptor;
    const size_t *ligand_donor_by_hydrogen;
    const uint8_t *ligand_donor_heavy_mask;
    size_t exclusion_count;
    const uint64_t *exclusion_i;
    const uint64_t *exclusion_j;
    size_t rotor_count;
    const uint64_t *rotor_i;
    const uint64_t *rotor_j;
    const uint64_t *rotor_k;
    const uint64_t *rotor_l;
    const double *reference_dihedrals;
    double reference_internal_vdw;
    double pocket_center[3];
    double pocket_radius;
    double weights[kScorerTermCount];
    double dielectric;
    double pair_cutoff;
    double hbond_cutoff;
    double polar_burial_distance;
    size_t max_receptor_candidate_pairs;
    size_t max_ligand_pair_checks;
};

struct HipSafeScorerState final {
    int32_t device_ordinal = 0;
    ScorerDeviceContext context{};
    DeviceBuffer<double> receptor_x;
    DeviceBuffer<double> receptor_y;
    DeviceBuffer<double> receptor_z;
    DeviceBuffer<double> receptor_charge;
    DeviceBuffer<double> receptor_radius;
    DeviceBuffer<double> receptor_epsilon;
    DeviceBuffer<uint8_t> receptor_hydrophobic;
    DeviceBuffer<uint8_t> receptor_acceptor;
    DeviceBuffer<size_t> receptor_donor_by_hydrogen;
    DeviceBuffer<double> ligand_charge;
    DeviceBuffer<double> ligand_radius;
    DeviceBuffer<double> ligand_epsilon;
    DeviceBuffer<uint8_t> ligand_hydrophobic;
    DeviceBuffer<uint8_t> ligand_acceptor;
    DeviceBuffer<size_t> ligand_donor_by_hydrogen;
    DeviceBuffer<uint8_t> ligand_donor_heavy_mask;
    DeviceBuffer<uint64_t> exclusion_i;
    DeviceBuffer<uint64_t> exclusion_j;
    DeviceBuffer<uint64_t> rotor_i;
    DeviceBuffer<uint64_t> rotor_j;
    DeviceBuffer<uint64_t> rotor_k;
    DeviceBuffer<uint64_t> rotor_l;
    DeviceBuffer<double> reference_dihedrals;
};

template <typename Value>
bool scorer_pointer_valid(const Value *pointer, size_t count) noexcept {
    return count == 0 || pointer != nullptr;
}

__device__ Vector3 scorer_coordinate(
    const double *x,
    const double *y,
    const double *z,
    size_t index) {
    return {x[index], y[index], z[index]};
}

__device__ double scorer_norm(Vector3 value) {
    return sqrt(dot(value, value));
}

__device__ bool scorer_coordinate_is_valid(Vector3 value) {
    return finite_vector(value) && fabs(value.x) <= kScorerMaxCoordinate &&
           fabs(value.y) <= kScorerMaxCoordinate &&
           fabs(value.z) <= kScorerMaxCoordinate;
}

__device__ double scorer_typed_lj(
    double first_epsilon,
    double second_epsilon,
    double sigma,
    double distance) {
    if (distance <= 1.0e-8) {
        return 1.0e6;
    }
    const double ratio = fmin(sigma / distance, 2.0);
    const double squared = ratio * ratio;
    const double sixth = squared * squared * squared;
    return sqrt(first_epsilon * second_epsilon) *
           (sixth * sixth - 2.0 * sixth);
}

__device__ double scorer_hbond_reward(
    Vector3 donor,
    Vector3 hydrogen,
    Vector3 acceptor,
    double cutoff) {
    const double distance = scorer_norm(minus(hydrogen, acceptor));
    if (distance > cutoff || distance <= 1.0e-8) {
        return 0.0;
    }
    const Vector3 first = minus(donor, hydrogen);
    const Vector3 second = minus(acceptor, hydrogen);
    const double denominator = scorer_norm(first) * scorer_norm(second);
    if (denominator <= 1.0e-12) {
        return 0.0;
    }
    const double cosine = dot(first, second) / denominator;
    const double angular = fmin(fmax((-cosine - 0.5) / 0.5, 0.0), 1.0);
    const double radial = fmax(1.0 - distance / cutoff, 0.0);
    return angular * radial;
}

__device__ bool scorer_pair_is_excluded(
    const ScorerDeviceContext &context,
    size_t first,
    size_t second) {
    size_t begin = 0;
    size_t end = context.exclusion_count;
    while (begin < end) {
        const size_t middle = begin + (end - begin) / 2;
        const uint64_t observed_i = context.exclusion_i[middle];
        const uint64_t observed_j = context.exclusion_j[middle];
        if (observed_i < first ||
            (observed_i == first && observed_j < second)) {
            begin = middle + 1;
        } else {
            end = middle;
        }
    }
    return begin < context.exclusion_count &&
           context.exclusion_i[begin] == first &&
           context.exclusion_j[begin] == second;
}

__device__ bool scorer_dihedral(
    const double *x,
    const double *y,
    const double *z,
    size_t offset,
    uint64_t atom_i,
    uint64_t atom_j,
    uint64_t atom_k,
    uint64_t atom_l,
    double *out_value) {
    const Vector3 first = scorer_coordinate(x, y, z, offset + atom_i);
    const Vector3 second = scorer_coordinate(x, y, z, offset + atom_j);
    const Vector3 third = scorer_coordinate(x, y, z, offset + atom_k);
    const Vector3 fourth = scorer_coordinate(x, y, z, offset + atom_l);
    const Vector3 middle = minus(third, second);
    const double middle_norm = scorer_norm(middle);
    if (middle_norm <= 1.0e-12) {
        return false;
    }
    const Vector3 axis = scaled(middle, 1.0 / middle_norm);
    Vector3 left = minus(first, second);
    Vector3 right = minus(fourth, third);
    left = minus(left, scaled(axis, dot(left, axis)));
    right = minus(right, scaled(axis, dot(right, axis)));
    const double left_norm = scorer_norm(left);
    const double right_norm = scorer_norm(right);
    if (fmin(left_norm, right_norm) <= 1.0e-12) {
        return false;
    }
    left = scaled(left, 1.0 / left_norm);
    right = scaled(right, 1.0 / right_norm);
    *out_value = atan2(dot(cross(left, right), axis), dot(left, right));
    return true;
}

__device__ bg_docking_scorer_v1_row_v1 scorer_failure_row(
    size_t slot,
    int32_t failure,
    size_t receptor_pairs,
    size_t ligand_pairs) {
    bg_docking_scorer_v1_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE;
    row.failure_code = failure;
    row.receptor_candidate_pair_count = receptor_pairs;
    row.ligand_pair_count = ligand_pairs;
    return row;
}

__global__ void scorer_fixed64_kernel(
    ScorerDeviceContext context,
    const int32_t *candidate_state,
    const double *candidate_x,
    const double *candidate_y,
    const double *candidate_z,
    bg_docking_scorer_v1_row_v1 *out_rows) {
    const size_t slot = blockIdx.x;
    if (slot >= kScorerCandidateCount || threadIdx.x != 0) {
        return;
    }
    if (candidate_state[slot] == BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE) {
        out_rows[slot] = scorer_failure_row(
            slot,
            BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED,
            0,
            0);
        return;
    }
    const size_t offset = slot * context.ligand_atom_count;
    for (size_t atom = 0; atom < context.ligand_atom_count; ++atom) {
        if (!scorer_coordinate_is_valid(scorer_coordinate(
                candidate_x, candidate_y, candidate_z, offset + atom))) {
            out_rows[slot] = scorer_failure_row(
                slot,
                BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES,
                0,
                0);
            return;
        }
    }

    uint8_t polar_buried[kScorerMaxLigandAtoms]{};
    uint8_t polar_satisfied[kScorerMaxLigandAtoms]{};
    double typed_vdw_raw = 0.0;
    double electro_raw = 0.0;
    double hbond_raw = 0.0;
    double hydrophobic_raw = 0.0;
    size_t hbond_count = 0;
    size_t hydrophobic_count = 0;
    size_t receptor_pair_count = 0;
    for (size_t ligand_index = 0; ligand_index < context.ligand_atom_count;
         ++ligand_index) {
        const Vector3 coordinate = scorer_coordinate(
            candidate_x, candidate_y, candidate_z, offset + ligand_index);
        const int64_t center_x =
            static_cast<int64_t>(floor(coordinate.x / context.pair_cutoff));
        const int64_t center_y =
            static_cast<int64_t>(floor(coordinate.y / context.pair_cutoff));
        const int64_t center_z =
            static_cast<int64_t>(floor(coordinate.z / context.pair_cutoff));
        for (int64_t cell_x = center_x - 1; cell_x <= center_x + 1; ++cell_x) {
            for (int64_t cell_y = center_y - 1; cell_y <= center_y + 1;
                 ++cell_y) {
                for (int64_t cell_z = center_z - 1; cell_z <= center_z + 1;
                     ++cell_z) {
                    for (size_t receptor_index = 0;
                         receptor_index < context.receptor_atom_count;
                         ++receptor_index) {
                        const int64_t receptor_cell_x = static_cast<int64_t>(
                            floor(context.receptor_x[receptor_index] /
                                  context.pair_cutoff));
                        const int64_t receptor_cell_y = static_cast<int64_t>(
                            floor(context.receptor_y[receptor_index] /
                                  context.pair_cutoff));
                        const int64_t receptor_cell_z = static_cast<int64_t>(
                            floor(context.receptor_z[receptor_index] /
                                  context.pair_cutoff));
                        if (receptor_cell_x != cell_x ||
                            receptor_cell_y != cell_y ||
                            receptor_cell_z != cell_z) {
                            continue;
                        }
                        ++receptor_pair_count;
                        if (receptor_pair_count >
                            context.max_receptor_candidate_pairs) {
                            out_rows[slot] = scorer_failure_row(
                                slot,
                                BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY,
                                receptor_pair_count,
                                0);
                            return;
                        }
                        const Vector3 receptor{
                            context.receptor_x[receptor_index],
                            context.receptor_y[receptor_index],
                            context.receptor_z[receptor_index],
                        };
                        const double distance =
                            scorer_norm(minus(coordinate, receptor));
                        if (distance > context.pair_cutoff) {
                            continue;
                        }
                        const double sigma = context.ligand_radius[ligand_index] +
                                             context.receptor_radius[receptor_index];
                        typed_vdw_raw += scorer_typed_lj(
                            context.ligand_epsilon[ligand_index],
                            context.receptor_epsilon[receptor_index],
                            sigma,
                            distance);
                        electro_raw +=
                            context.ligand_charge[ligand_index] *
                            context.receptor_charge[receptor_index] /
                            (context.dielectric * fmax(distance, 0.5));
                        if (context.ligand_hydrophobic[ligand_index] != 0 &&
                            context.receptor_hydrophobic[receptor_index] != 0 &&
                            distance <= 1.25 * sigma) {
                            ++hydrophobic_count;
                            hydrophobic_raw +=
                                fmax(1.0 - distance / (1.25 * sigma), 0.0);
                        }
                        if ((context.ligand_acceptor[ligand_index] != 0 ||
                             context.ligand_donor_heavy_mask[ligand_index] != 0) &&
                            distance <= context.polar_burial_distance) {
                            polar_buried[ligand_index] = UINT8_C(1);
                        }
                        const size_t ligand_donor =
                            context.ligand_donor_by_hydrogen[ligand_index];
                        if (ligand_donor != kScorerNoDonor &&
                            context.receptor_acceptor[receptor_index] != 0) {
                            const double reward = scorer_hbond_reward(
                                scorer_coordinate(
                                    candidate_x,
                                    candidate_y,
                                    candidate_z,
                                    offset + ligand_donor),
                                coordinate,
                                receptor,
                                context.hbond_cutoff);
                            if (reward > 0.0) {
                                hbond_raw += reward;
                                ++hbond_count;
                                polar_satisfied[ligand_donor] = UINT8_C(1);
                            }
                        }
                        const size_t receptor_donor =
                            context.receptor_donor_by_hydrogen[receptor_index];
                        if (receptor_donor != kScorerNoDonor &&
                            context.ligand_acceptor[ligand_index] != 0) {
                            const Vector3 donor{
                                context.receptor_x[receptor_donor],
                                context.receptor_y[receptor_donor],
                                context.receptor_z[receptor_donor],
                            };
                            const double reward = scorer_hbond_reward(
                                donor, receptor, coordinate, context.hbond_cutoff);
                            if (reward > 0.0) {
                                hbond_raw += reward;
                                ++hbond_count;
                                polar_satisfied[ligand_index] = UINT8_C(1);
                            }
                        }
                    }
                }
            }
        }
    }

    double current_internal_vdw = 0.0;
    size_t ligand_pair_count = 0;
    for (size_t first = 0; first < context.ligand_atom_count; ++first) {
        for (size_t second = first + 1; second < context.ligand_atom_count;
             ++second) {
            if (scorer_pair_is_excluded(context, first, second)) {
                continue;
            }
            ++ligand_pair_count;
            if (ligand_pair_count > context.max_ligand_pair_checks) {
                out_rows[slot] = scorer_failure_row(
                    slot,
                    BG_DOCKING_SCORER_V1_FAILURE_LIGAND_PAIR_CAPACITY,
                    receptor_pair_count,
                    ligand_pair_count);
                return;
            }
            const Vector3 first_coordinate = scorer_coordinate(
                candidate_x, candidate_y, candidate_z, offset + first);
            const Vector3 second_coordinate = scorer_coordinate(
                candidate_x, candidate_y, candidate_z, offset + second);
            current_internal_vdw += scorer_typed_lj(
                context.ligand_epsilon[first],
                context.ligand_epsilon[second],
                context.ligand_radius[first] + context.ligand_radius[second],
                scorer_norm(minus(first_coordinate, second_coordinate)));
        }
    }
    const double ligand_strain_raw =
        fmax(current_internal_vdw - context.reference_internal_vdw, 0.0);
    double torsion_raw = 0.0;
    for (size_t rotor = 0; rotor < context.rotor_count; ++rotor) {
        double observed = 0.0;
        if (!scorer_dihedral(
                candidate_x,
                candidate_y,
                candidate_z,
                offset,
                context.rotor_i[rotor],
                context.rotor_j[rotor],
                context.rotor_k[rotor],
                context.rotor_l[rotor],
                &observed)) {
            out_rows[slot] = scorer_failure_row(
                slot,
                BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR,
                receptor_pair_count,
                ligand_pair_count);
            return;
        }
        const double difference = observed - context.reference_dihedrals[rotor];
        const double delta = atan2(sin(difference), cos(difference));
        torsion_raw += 0.5 * (1.0 - cos(3.0 * delta));
    }

    Vector3 centroid{0.0, 0.0, 0.0};
    for (size_t atom = 0; atom < context.ligand_atom_count; ++atom) {
        centroid = plus(
            centroid,
            scorer_coordinate(candidate_x, candidate_y, candidate_z, offset + atom));
    }
    centroid = scaled(
        centroid, 1.0 / static_cast<double>(context.ligand_atom_count));
    const Vector3 pocket_center{
        context.pocket_center[0],
        context.pocket_center[1],
        context.pocket_center[2],
    };
    const double pocket_ratio =
        scorer_norm(minus(centroid, pocket_center)) / context.pocket_radius;
    const double pocket_raw = pocket_ratio * pocket_ratio;
    size_t buried_polar_count = 0;
    size_t unsatisfied_buried_count = 0;
    for (size_t atom = 0; atom < context.ligand_atom_count; ++atom) {
        if (polar_buried[atom] != 0) {
            ++buried_polar_count;
            if (polar_satisfied[atom] == 0) {
                ++unsatisfied_buried_count;
            }
        }
    }
    const double raw[kScorerTermCount] = {
        typed_vdw_raw,
        electro_raw,
        -hbond_raw,
        -hydrophobic_raw,
        static_cast<double>(unsatisfied_buried_count),
        torsion_raw,
        ligand_strain_raw,
        pocket_raw,
    };
    bg_docking_scorer_v1_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_SCORER_V1_ROW_SCORED;
    row.failure_code = BG_DOCKING_SCORER_V1_FAILURE_NONE;
    for (size_t term = 0; term < kScorerTermCount; ++term) {
        row.weighted_terms[term] = raw[term] * context.weights[term];
        row.total_score += row.weighted_terms[term];
    }
    row.receptor_candidate_pair_count = receptor_pair_count;
    row.ligand_pair_count = ligand_pair_count;
    row.hbond_count = hbond_count;
    row.hydrophobic_contact_count = hydrophobic_count;
    row.buried_polar_count = buried_polar_count;
    bool finite = isfinite(row.total_score);
    for (size_t term = 0; term < kScorerTermCount; ++term) {
        finite = finite && isfinite(row.weighted_terms[term]);
    }
    if (!finite) {
        out_rows[slot] = scorer_failure_row(
            slot,
            BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE,
            receptor_pair_count,
            ligand_pair_count);
        return;
    }
    out_rows[slot] = row;
}

int32_t validate_scorer_create(
    const bg_docking_scorer_v1_context_soa_v1 *descriptor,
    const bg_hip_safe_docking_scorer_derived_v1 *derived,
    void **out_state,
    char *error_message,
    size_t error_capacity) noexcept {
    if (descriptor == nullptr || derived == nullptr || out_state == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 create pointer is null");
    }
    *out_state = nullptr;
    if (descriptor->struct_size != sizeof(*descriptor) ||
        descriptor->abi_version != BG_ABI_VERSION ||
        !valid_header(*derived)) {
        return fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 descriptor ABI mismatch");
    }
    if (descriptor->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        descriptor->reserved0 != 0 || !reserved_is_zero(descriptor->reserved) ||
        !reserved_is_zero(derived->reserved) ||
        descriptor->receptor_atom_count == 0 ||
        descriptor->receptor_atom_count > kScorerMaxReceptorAtoms ||
        descriptor->ligand_atom_count == 0 ||
        descriptor->ligand_atom_count > kScorerMaxLigandAtoms ||
        descriptor->rotor_count > descriptor->ligand_atom_count) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 descriptor identity is invalid");
    }
    const size_t receptor_count = descriptor->receptor_atom_count;
    const size_t ligand_count = descriptor->ligand_atom_count;
    const size_t rotor_count = descriptor->rotor_count;
    const size_t exclusion_count = descriptor->ligand_exclusion_count;
    const bool channels_valid =
        scorer_pointer_valid(descriptor->receptor_x_angstrom, receptor_count) &&
        scorer_pointer_valid(descriptor->receptor_y_angstrom, receptor_count) &&
        scorer_pointer_valid(descriptor->receptor_z_angstrom, receptor_count) &&
        scorer_pointer_valid(
            descriptor->receptor_charge_elementary, receptor_count) &&
        scorer_pointer_valid(
            descriptor->receptor_vdw_radius_angstrom, receptor_count) &&
        scorer_pointer_valid(
            descriptor->receptor_epsilon_kcal_per_mol, receptor_count) &&
        scorer_pointer_valid(descriptor->receptor_hydrophobic, receptor_count) &&
        scorer_pointer_valid(descriptor->receptor_acceptor, receptor_count) &&
        scorer_pointer_valid(descriptor->ligand_charge_elementary, ligand_count) &&
        scorer_pointer_valid(
            descriptor->ligand_vdw_radius_angstrom, ligand_count) &&
        scorer_pointer_valid(
            descriptor->ligand_epsilon_kcal_per_mol, ligand_count) &&
        scorer_pointer_valid(descriptor->ligand_hydrophobic, ligand_count) &&
        scorer_pointer_valid(descriptor->ligand_acceptor, ligand_count) &&
        scorer_pointer_valid(
            descriptor->ligand_exclusion_atom_i, exclusion_count) &&
        scorer_pointer_valid(
            descriptor->ligand_exclusion_atom_j, exclusion_count) &&
        scorer_pointer_valid(descriptor->rotor_atom_i, rotor_count) &&
        scorer_pointer_valid(descriptor->rotor_atom_j, rotor_count) &&
        scorer_pointer_valid(descriptor->rotor_atom_k, rotor_count) &&
        scorer_pointer_valid(descriptor->rotor_atom_l, rotor_count) &&
        scorer_pointer_valid(derived->reference_dihedrals_radians, rotor_count) &&
        scorer_pointer_valid(derived->receptor_donor_by_hydrogen, receptor_count) &&
        scorer_pointer_valid(derived->ligand_donor_by_hydrogen, ligand_count) &&
        scorer_pointer_valid(derived->ligand_donor_heavy_mask, ligand_count);
    if (!channels_valid || !std::isfinite(derived->reference_internal_vdw)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 channel identity is invalid");
    }
    return BG_STATUS_OK;
}

bool scorer_host_row_is_valid(
    const bg_docking_scorer_v1_row_v1 &row,
    size_t slot) noexcept {
    if (row.slot_index != slot || row.reserved0 != 0 ||
        !reserved_is_zero(row.reserved)) {
        return false;
    }
    if (row.status == BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE) {
        return row.failure_code >=
                   BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED &&
               row.failure_code <= BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE;
    }
    if (row.status != BG_DOCKING_SCORER_V1_ROW_SCORED ||
        row.failure_code != BG_DOCKING_SCORER_V1_FAILURE_NONE ||
        !std::isfinite(row.total_score)) {
        return false;
    }
    return std::all_of(
        std::begin(row.weighted_terms),
        std::end(row.weighted_terms),
        [](double value) { return std::isfinite(value); });
}

}  // namespace

extern "C" int32_t bg_hip_safe_docking_scorer_v1_create(
    int32_t device_ordinal,
    const bg_docking_scorer_v1_context_soa_v1 *descriptor,
    const bg_hip_safe_docking_scorer_derived_v1 *derived,
    void **out_state,
    char *error_message,
    size_t error_capacity) {
    clear_error(error_message, error_capacity);
    const int32_t validation_status = validate_scorer_create(
        descriptor, derived, out_state, error_message, error_capacity);
    if (validation_status != BG_STATUS_OK) {
        return validation_status;
    }
    uint8_t available = UINT8_C(0);
    const int32_t availability_status = bg_hip_safe_provider_is_available_v1(
        device_ordinal, &available, error_message, error_capacity);
    if (availability_status != BG_STATUS_OK) {
        return availability_status;
    }
    if (available == UINT8_C(0)) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 device ordinal is unavailable");
    }
    DeviceGuard device_guard;
    const hipError_t set_status = hipSetDevice(device_ordinal);
    if (set_status != hipSuccess) {
        return fail_hip(
            set_status, error_message, error_capacity, "ScorerV1 device selection");
    }
    std::unique_ptr<HipSafeScorerState> state(
        new (std::nothrow) HipSafeScorerState());
    if (state == nullptr) {
        return fail(
            BG_STATUS_OUT_OF_MEMORY,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 host context allocation failed");
    }
    state->device_ordinal = device_ordinal;
    const size_t receptor_count = descriptor->receptor_atom_count;
    const size_t ligand_count = descriptor->ligand_atom_count;
    const size_t exclusion_count = descriptor->ligand_exclusion_count;
    const size_t rotor_count = descriptor->rotor_count;

#define BG_HIP_SCORER_COPY(buffer, source, count, operation)               \
    do {                                                                   \
        const hipError_t copy_status = (buffer).copy_from((source), (count)); \
        if (copy_status != hipSuccess) {                                   \
            return fail_hip(                                               \
                copy_status, error_message, error_capacity, (operation));  \
        }                                                                  \
    } while (false)

    BG_HIP_SCORER_COPY(
        state->receptor_x,
        descriptor->receptor_x_angstrom,
        receptor_count,
        "ScorerV1 receptor x copy");
    BG_HIP_SCORER_COPY(
        state->receptor_y,
        descriptor->receptor_y_angstrom,
        receptor_count,
        "ScorerV1 receptor y copy");
    BG_HIP_SCORER_COPY(
        state->receptor_z,
        descriptor->receptor_z_angstrom,
        receptor_count,
        "ScorerV1 receptor z copy");
    BG_HIP_SCORER_COPY(
        state->receptor_charge,
        descriptor->receptor_charge_elementary,
        receptor_count,
        "ScorerV1 receptor charge copy");
    BG_HIP_SCORER_COPY(
        state->receptor_radius,
        descriptor->receptor_vdw_radius_angstrom,
        receptor_count,
        "ScorerV1 receptor radius copy");
    BG_HIP_SCORER_COPY(
        state->receptor_epsilon,
        descriptor->receptor_epsilon_kcal_per_mol,
        receptor_count,
        "ScorerV1 receptor epsilon copy");
    BG_HIP_SCORER_COPY(
        state->receptor_hydrophobic,
        descriptor->receptor_hydrophobic,
        receptor_count,
        "ScorerV1 receptor hydrophobic copy");
    BG_HIP_SCORER_COPY(
        state->receptor_acceptor,
        descriptor->receptor_acceptor,
        receptor_count,
        "ScorerV1 receptor acceptor copy");
    BG_HIP_SCORER_COPY(
        state->receptor_donor_by_hydrogen,
        derived->receptor_donor_by_hydrogen,
        receptor_count,
        "ScorerV1 receptor donor map copy");
    BG_HIP_SCORER_COPY(
        state->ligand_charge,
        descriptor->ligand_charge_elementary,
        ligand_count,
        "ScorerV1 ligand charge copy");
    BG_HIP_SCORER_COPY(
        state->ligand_radius,
        descriptor->ligand_vdw_radius_angstrom,
        ligand_count,
        "ScorerV1 ligand radius copy");
    BG_HIP_SCORER_COPY(
        state->ligand_epsilon,
        descriptor->ligand_epsilon_kcal_per_mol,
        ligand_count,
        "ScorerV1 ligand epsilon copy");
    BG_HIP_SCORER_COPY(
        state->ligand_hydrophobic,
        descriptor->ligand_hydrophobic,
        ligand_count,
        "ScorerV1 ligand hydrophobic copy");
    BG_HIP_SCORER_COPY(
        state->ligand_acceptor,
        descriptor->ligand_acceptor,
        ligand_count,
        "ScorerV1 ligand acceptor copy");
    BG_HIP_SCORER_COPY(
        state->ligand_donor_by_hydrogen,
        derived->ligand_donor_by_hydrogen,
        ligand_count,
        "ScorerV1 ligand donor map copy");
    BG_HIP_SCORER_COPY(
        state->ligand_donor_heavy_mask,
        derived->ligand_donor_heavy_mask,
        ligand_count,
        "ScorerV1 ligand donor mask copy");
    BG_HIP_SCORER_COPY(
        state->exclusion_i,
        descriptor->ligand_exclusion_atom_i,
        exclusion_count,
        "ScorerV1 exclusion i copy");
    BG_HIP_SCORER_COPY(
        state->exclusion_j,
        descriptor->ligand_exclusion_atom_j,
        exclusion_count,
        "ScorerV1 exclusion j copy");
    BG_HIP_SCORER_COPY(
        state->rotor_i,
        descriptor->rotor_atom_i,
        rotor_count,
        "ScorerV1 rotor i copy");
    BG_HIP_SCORER_COPY(
        state->rotor_j,
        descriptor->rotor_atom_j,
        rotor_count,
        "ScorerV1 rotor j copy");
    BG_HIP_SCORER_COPY(
        state->rotor_k,
        descriptor->rotor_atom_k,
        rotor_count,
        "ScorerV1 rotor k copy");
    BG_HIP_SCORER_COPY(
        state->rotor_l,
        descriptor->rotor_atom_l,
        rotor_count,
        "ScorerV1 rotor l copy");
    BG_HIP_SCORER_COPY(
        state->reference_dihedrals,
        derived->reference_dihedrals_radians,
        rotor_count,
        "ScorerV1 reference dihedral copy");

    ScorerDeviceContext &context = state->context;
    context.receptor_atom_count = receptor_count;
    context.ligand_atom_count = ligand_count;
    context.receptor_x = state->receptor_x.get();
    context.receptor_y = state->receptor_y.get();
    context.receptor_z = state->receptor_z.get();
    context.receptor_charge = state->receptor_charge.get();
    context.receptor_radius = state->receptor_radius.get();
    context.receptor_epsilon = state->receptor_epsilon.get();
    context.receptor_hydrophobic = state->receptor_hydrophobic.get();
    context.receptor_acceptor = state->receptor_acceptor.get();
    context.receptor_donor_by_hydrogen =
        state->receptor_donor_by_hydrogen.get();
    context.ligand_charge = state->ligand_charge.get();
    context.ligand_radius = state->ligand_radius.get();
    context.ligand_epsilon = state->ligand_epsilon.get();
    context.ligand_hydrophobic = state->ligand_hydrophobic.get();
    context.ligand_acceptor = state->ligand_acceptor.get();
    context.ligand_donor_by_hydrogen = state->ligand_donor_by_hydrogen.get();
    context.ligand_donor_heavy_mask = state->ligand_donor_heavy_mask.get();
    context.exclusion_count = exclusion_count;
    context.exclusion_i = state->exclusion_i.get();
    context.exclusion_j = state->exclusion_j.get();
    context.rotor_count = rotor_count;
    context.rotor_i = state->rotor_i.get();
    context.rotor_j = state->rotor_j.get();
    context.rotor_k = state->rotor_k.get();
    context.rotor_l = state->rotor_l.get();
    context.reference_dihedrals = state->reference_dihedrals.get();
    context.reference_internal_vdw = derived->reference_internal_vdw;
    std::copy(
        std::begin(descriptor->pocket_center_angstrom),
        std::end(descriptor->pocket_center_angstrom),
        std::begin(context.pocket_center));
    context.pocket_radius = descriptor->pocket_radius_angstrom;
    std::copy(
        std::begin(descriptor->weights),
        std::end(descriptor->weights),
        std::begin(context.weights));
    context.dielectric = descriptor->electrostatic_dielectric;
    context.pair_cutoff = descriptor->pair_cutoff_angstrom;
    context.hbond_cutoff = descriptor->hbond_distance_max_angstrom;
    context.polar_burial_distance = descriptor->polar_burial_distance_angstrom;
    context.max_receptor_candidate_pairs =
        descriptor->max_receptor_candidate_pairs;
    context.max_ligand_pair_checks = descriptor->max_ligand_pair_checks;
    *out_state = state.release();
    return BG_STATUS_OK;

#undef BG_HIP_SCORER_COPY
}

extern "C" void bg_hip_safe_docking_scorer_v1_destroy(void *state) {
    auto *typed = static_cast<HipSafeScorerState *>(state);
    if (typed == nullptr) {
        return;
    }
    DeviceGuard device_guard;
    static_cast<void>(hipSetDevice(typed->device_ordinal));
    delete typed;
}

extern "C" int32_t bg_hip_safe_docking_scorer_v1_score_fixed64(
    const void *state,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 *candidates,
    bg_docking_scorer_v1_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity) {
    clear_error(error_message, error_capacity);
    const auto *typed = static_cast<const HipSafeScorerState *>(state);
    if (typed == nullptr || candidates == nullptr || out_rows == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 score pointer is null");
    }
    if (candidates->struct_size != sizeof(*candidates) ||
        candidates->abi_version != BG_ABI_VERSION) {
        return fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 candidate batch ABI mismatch");
    }
    if (candidates->candidate_count != kScorerCandidateCount ||
        candidates->ligand_atom_count != typed->context.ligand_atom_count ||
        candidates->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        candidates->reserved0 != 0 || !reserved_is_zero(candidates->reserved) ||
        candidates->candidate_state == nullptr ||
        candidates->x_angstrom == nullptr || candidates->y_angstrom == nullptr ||
        candidates->z_angstrom == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe ScorerV1 candidate batch identity is invalid");
    }
    for (size_t slot = 0; slot < kScorerCandidateCount; ++slot) {
        if (candidates->candidate_state[slot] !=
                BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE &&
            candidates->candidate_state[slot] !=
                BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                "hip_safe ScorerV1 candidate state is invalid");
        }
    }
    DeviceGuard device_guard;
    const hipError_t set_status = hipSetDevice(typed->device_ordinal);
    if (set_status != hipSuccess) {
        return fail_hip(
            set_status, error_message, error_capacity, "ScorerV1 device selection");
    }
    const size_t coordinate_count =
        kScorerCandidateCount * typed->context.ligand_atom_count;
    DeviceBuffer<int32_t> device_states;
    DeviceBuffer<double> device_x;
    DeviceBuffer<double> device_y;
    DeviceBuffer<double> device_z;
    DeviceBuffer<bg_docking_scorer_v1_row_v1> device_rows;

#define BG_HIP_SCORER_BATCH_COPY(buffer, source, count, operation)         \
    do {                                                                   \
        const hipError_t copy_status = (buffer).copy_from((source), (count)); \
        if (copy_status != hipSuccess) {                                   \
            return fail_hip(                                               \
                copy_status, error_message, error_capacity, (operation));  \
        }                                                                  \
    } while (false)

    BG_HIP_SCORER_BATCH_COPY(
        device_states,
        candidates->candidate_state,
        kScorerCandidateCount,
        "ScorerV1 candidate state copy");
    BG_HIP_SCORER_BATCH_COPY(
        device_x,
        candidates->x_angstrom,
        coordinate_count,
        "ScorerV1 candidate x copy");
    BG_HIP_SCORER_BATCH_COPY(
        device_y,
        candidates->y_angstrom,
        coordinate_count,
        "ScorerV1 candidate y copy");
    BG_HIP_SCORER_BATCH_COPY(
        device_z,
        candidates->z_angstrom,
        coordinate_count,
        "ScorerV1 candidate z copy");
    const hipError_t allocation_status = device_rows.allocate(kScorerCandidateCount);
    if (allocation_status != hipSuccess) {
        return fail_hip(
            allocation_status,
            error_message,
            error_capacity,
            "ScorerV1 output allocation");
    }
    hipLaunchKernelGGL(
        scorer_fixed64_kernel,
        dim3(static_cast<uint32_t>(kScorerCandidateCount)),
        dim3(1),
        0,
        0,
        typed->context,
        device_states.get(),
        device_x.get(),
        device_y.get(),
        device_z.get(),
        device_rows.get());
    hipError_t execution_status = hipGetLastError();
    if (execution_status == hipSuccess) {
        execution_status = hipDeviceSynchronize();
    }
    if (execution_status != hipSuccess) {
        return fail_hip(
            execution_status,
            error_message,
            error_capacity,
            "ScorerV1 kernel execution");
    }
    std::array<bg_docking_scorer_v1_row_v1, kScorerCandidateCount> host_rows{};
    const hipError_t copy_status =
        device_rows.copy_to(host_rows.data(), host_rows.size());
    if (copy_status != hipSuccess) {
        return fail_hip(
            copy_status,
            error_message,
            error_capacity,
            "ScorerV1 result copy");
    }
    for (size_t slot = 0; slot < host_rows.size(); ++slot) {
        if (!scorer_host_row_is_valid(host_rows[slot], slot)) {
            return fail(
                BG_STATUS_BACKEND_ERROR,
                error_message,
                error_capacity,
                "hip_safe ScorerV1 returned an invalid device row");
        }
    }
    std::memcpy(out_rows, host_rows.data(), sizeof(host_rows));
    return BG_STATUS_OK;

#undef BG_HIP_SCORER_BATCH_COPY
}
