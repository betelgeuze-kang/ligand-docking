#include <hip/hip_runtime.h>

#include <array>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <new>
#include <set>
#include <tuple>

#if !defined(BG_DOCKING_VALIDITY_CREATE) || \
    !defined(BG_DOCKING_VALIDITY_DESTROY) || \
    !defined(BG_DOCKING_VALIDITY_EVALUATE_FIXED64) || \
    !defined(BG_DOCKING_VALIDITY_LANE)
#  error "native HIP pose-validity provider identity is not configured"
#endif

namespace {

constexpr size_t kValidityCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr size_t kValidityMaxLigandAtoms = 512;
constexpr size_t kValidityMaxReceptorAtoms = 4096;
constexpr double kValidityMaxCoordinate = 100000.0;
constexpr double kValidityMinimumSentinel = 999.0;

void validity_clear_error(char *message, size_t capacity) noexcept {
    if (message != nullptr && capacity > 0) {
        message[0] = '\0';
    }
}

int32_t validity_fail(
    int32_t status,
    char *message,
    size_t capacity,
    const char *detail) noexcept {
    if (message != nullptr && capacity > 0) {
        std::snprintf(message, capacity, "%s", detail == nullptr ? "" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

int32_t validity_fail_hip(
    hipError_t error,
    char *message,
    size_t capacity,
    const char *operation) noexcept {
    const int32_t status = error == hipErrorOutOfMemory
                               ? BG_STATUS_OUT_OF_MEMORY
                               : BG_STATUS_BACKEND_ERROR;
    if (message != nullptr && capacity > 0) {
        const char *const detail = hipGetErrorString(error);
        std::snprintf(
            message,
            capacity,
            "%s %s failed: %s",
            BG_DOCKING_VALIDITY_LANE,
            operation,
            detail == nullptr ? "unknown HIP runtime error" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

template <size_t Count>
bool validity_reserved_is_zero(const uint64_t (&values)[Count]) noexcept {
    for (const uint64_t value : values) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

template <typename Value>
bool validity_counted_pointer_is_valid(
    const Value *pointer,
    size_t count) noexcept {
    return count == 0 || pointer != nullptr;
}

template <typename Value>
class ValidityDeviceBuffer final {
public:
    ValidityDeviceBuffer() = default;
    ValidityDeviceBuffer(const ValidityDeviceBuffer &) = delete;
    ValidityDeviceBuffer &operator=(const ValidityDeviceBuffer &) = delete;

    ~ValidityDeviceBuffer() {
        if (pointer_ != nullptr) {
            static_cast<void>(hipFree(pointer_));
        }
    }

    hipError_t copy_from(const Value *source, size_t count) noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (source == nullptr ||
            count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        const size_t bytes = count * sizeof(Value);
        hipError_t status =
            hipMalloc(reinterpret_cast<void **>(&pointer_), bytes);
        if (status != hipSuccess) {
            return status;
        }
        return hipMemcpy(pointer_, source, bytes, hipMemcpyHostToDevice);
    }

    hipError_t allocate(size_t count) noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        return hipMalloc(
            reinterpret_cast<void **>(&pointer_), count * sizeof(Value));
    }

    hipError_t copy_to(Value *destination, size_t count) const noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (destination == nullptr || pointer_ == nullptr ||
            count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        return hipMemcpy(
            destination,
            pointer_,
            count * sizeof(Value),
            hipMemcpyDeviceToHost);
    }

    Value *get() noexcept { return pointer_; }
    const Value *get() const noexcept { return pointer_; }

private:
    Value *pointer_ = nullptr;
};

class ValidityDeviceGuard final {
public:
    ValidityDeviceGuard() noexcept {
        if (hipGetDevice(&previous_) == hipSuccess) {
            has_previous_ = true;
        }
    }

    ValidityDeviceGuard(const ValidityDeviceGuard &) = delete;
    ValidityDeviceGuard &operator=(const ValidityDeviceGuard &) = delete;

    ~ValidityDeviceGuard() {
        if (has_previous_) {
            static_cast<void>(hipSetDevice(previous_));
        }
    }

private:
    int previous_ = 0;
    bool has_previous_ = false;
};

struct ValidityVector3 final {
    double x;
    double y;
    double z;
};

struct ValidityDeviceContext final {
    size_t receptor_atom_count;
    size_t ligand_atom_count;
    const double *receptor_x;
    const double *receptor_y;
    const double *receptor_z;
    const double *receptor_radius;
    const double *ligand_reference_x;
    const double *ligand_reference_y;
    const double *ligand_reference_z;
    const double *ligand_radius;
    size_t bond_count;
    const uint64_t *bond_i;
    const uint64_t *bond_j;
    size_t exclusion_count;
    const uint64_t *exclusion_i;
    const uint64_t *exclusion_j;
    size_t chirality_count;
    const uint64_t *chirality_center;
    const uint64_t *chirality_i;
    const uint64_t *chirality_j;
    const uint64_t *chirality_k;
    double pocket_center[3];
    double pocket_radius;
    double bond_length_tolerance;
    double ligand_self_clash;
    double receptor_ligand_clash;
    double rotation_tolerance;
    double chirality_volume_tolerance;
    double severe_overlap_scale;
    double contact_cell_size;
    size_t max_pair_checks;
    size_t max_cross_checks;
    size_t max_element_ligand_pair_checks;
    size_t max_element_receptor_candidate_pairs;
    size_t receptor_cell_count;
};

struct ValidityState final {
    int32_t device_ordinal = 0;
    ValidityDeviceContext context{};
    ValidityDeviceBuffer<double> receptor_x;
    ValidityDeviceBuffer<double> receptor_y;
    ValidityDeviceBuffer<double> receptor_z;
    ValidityDeviceBuffer<double> receptor_radius;
    ValidityDeviceBuffer<double> ligand_reference_x;
    ValidityDeviceBuffer<double> ligand_reference_y;
    ValidityDeviceBuffer<double> ligand_reference_z;
    ValidityDeviceBuffer<double> ligand_radius;
    ValidityDeviceBuffer<uint64_t> bond_i;
    ValidityDeviceBuffer<uint64_t> bond_j;
    ValidityDeviceBuffer<uint64_t> exclusion_i;
    ValidityDeviceBuffer<uint64_t> exclusion_j;
    ValidityDeviceBuffer<uint64_t> chirality_center;
    ValidityDeviceBuffer<uint64_t> chirality_i;
    ValidityDeviceBuffer<uint64_t> chirality_j;
    ValidityDeviceBuffer<uint64_t> chirality_k;
};

__device__ ValidityVector3 validity_minus(
    ValidityVector3 left,
    ValidityVector3 right) {
    return {left.x - right.x, left.y - right.y, left.z - right.z};
}

__device__ double validity_dot(
    ValidityVector3 left,
    ValidityVector3 right) {
    return left.x * right.x + left.y * right.y + left.z * right.z;
}

__device__ ValidityVector3 validity_cross(
    ValidityVector3 left,
    ValidityVector3 right) {
    return {
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    };
}

__device__ double validity_distance(
    ValidityVector3 left,
    ValidityVector3 right) {
    const ValidityVector3 delta = validity_minus(left, right);
    return sqrt(validity_dot(delta, delta));
}

__device__ bool validity_finite_coordinate(ValidityVector3 value) {
    return isfinite(value.x) && isfinite(value.y) && isfinite(value.z) &&
           fabs(value.x) <= kValidityMaxCoordinate &&
           fabs(value.y) <= kValidityMaxCoordinate &&
           fabs(value.z) <= kValidityMaxCoordinate;
}

__device__ double validity_minimum_or_sentinel(double value) {
    return isfinite(value) ? value : kValidityMinimumSentinel;
}

__device__ ValidityVector3 validity_ligand_coordinate(
    const double *x,
    const double *y,
    const double *z,
    size_t offset,
    size_t atom) {
    return {x[offset + atom], y[offset + atom], z[offset + atom]};
}

__device__ ValidityVector3 validity_reference_coordinate(
    const ValidityDeviceContext &context,
    size_t atom) {
    return {
        context.ligand_reference_x[atom],
        context.ligand_reference_y[atom],
        context.ligand_reference_z[atom],
    };
}

__device__ ValidityVector3 validity_receptor_coordinate(
    const ValidityDeviceContext &context,
    size_t atom) {
    return {
        context.receptor_x[atom],
        context.receptor_y[atom],
        context.receptor_z[atom],
    };
}

__device__ bool validity_is_excluded(
    const ValidityDeviceContext &context,
    size_t first,
    size_t second) {
    for (size_t row = 0; row < context.exclusion_count; ++row) {
        const size_t observed_first =
            static_cast<size_t>(context.exclusion_i[row]);
        const size_t observed_second =
            static_cast<size_t>(context.exclusion_j[row]);
        if (observed_first == first && observed_second == second) {
            return true;
        }
        if (observed_first > first ||
            (observed_first == first && observed_second > second)) {
            return false;
        }
    }
    return false;
}

__device__ int64_t validity_cell_coordinate(double value, double size) {
    return static_cast<int64_t>(floor(value / size));
}

__device__ bool validity_neighbor_cells(
    ValidityVector3 ligand,
    ValidityVector3 receptor,
    double size) {
    const int64_t ligand_x = validity_cell_coordinate(ligand.x, size);
    const int64_t ligand_y = validity_cell_coordinate(ligand.y, size);
    const int64_t ligand_z = validity_cell_coordinate(ligand.z, size);
    const int64_t receptor_x = validity_cell_coordinate(receptor.x, size);
    const int64_t receptor_y = validity_cell_coordinate(receptor.y, size);
    const int64_t receptor_z = validity_cell_coordinate(receptor.z, size);
    const int64_t delta_x = ligand_x - receptor_x;
    const int64_t delta_y = ligand_y - receptor_y;
    const int64_t delta_z = ligand_z - receptor_z;
    return delta_x >= -1 && delta_x <= 1 && delta_y >= -1 &&
           delta_y <= 1 && delta_z >= -1 && delta_z <= 1;
}

__device__ double validity_signed_volume(
    ValidityVector3 center,
    ValidityVector3 first,
    ValidityVector3 second,
    ValidityVector3 third) {
    return validity_dot(
        validity_cross(
            validity_minus(first, center),
            validity_minus(second, center)),
        validity_minus(third, center));
}

__device__ void validity_rotation_measurements(
    double x,
    double y,
    double z,
    double w,
    double *orthogonality_error,
    double *determinant) {
    double matrix[3][3] = {
        {
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y - z * w),
            2.0 * (x * z + y * w),
        },
        {
            2.0 * (x * y + z * w),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z - x * w),
        },
        {
            2.0 * (x * z - y * w),
            2.0 * (y * z + x * w),
            1.0 - 2.0 * (x * x + y * y),
        },
    };
    double maximum = 0.0;
    for (size_t row = 0; row < 3; ++row) {
        for (size_t column = 0; column < 3; ++column) {
            double value = 0.0;
            for (size_t index = 0; index < 3; ++index) {
                value += matrix[index][row] * matrix[index][column];
            }
            maximum = fmax(
                maximum,
                fabs(value - (row == column ? 1.0 : 0.0)));
        }
    }
    *orthogonality_error = maximum;
    *determinant =
        matrix[0][0] *
            (matrix[1][1] * matrix[2][2] -
             matrix[1][2] * matrix[2][1]) -
        matrix[0][1] *
            (matrix[1][0] * matrix[2][2] -
             matrix[1][2] * matrix[2][0]) +
        matrix[0][2] *
            (matrix[1][0] * matrix[2][1] -
             matrix[1][1] * matrix[2][0]);
}

__device__ bg_docking_pose_validity_row_v1 validity_failure_row(
    size_t slot,
    bg_docking_pose_validity_row_status status,
    bg_docking_pose_validity_failure failure,
    bg_docking_scorer_v1_failure upstream,
    size_t observed_count) {
    bg_docking_pose_validity_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = status;
    row.failure_code = failure;
    row.upstream_scorer_failure_code = upstream;
    row.observed_count = static_cast<uint64_t>(observed_count);
    return row;
}

__device__ bool validity_measurements_finite(
    const bg_docking_pose_validity_row_v1 &row) {
    return isfinite(row.rotation_orthogonality_max_error) &&
           isfinite(row.rotation_determinant) &&
           isfinite(row.max_bond_length_delta_angstrom) &&
           isfinite(row.minimum_ligand_nonbonded_distance_angstrom) &&
           isfinite(row.minimum_receptor_ligand_distance_angstrom) &&
           isfinite(row.minimum_declared_chiral_volume) &&
           isfinite(row.maximum_pocket_center_distance_angstrom) &&
           isfinite(row.element_vdw_ligand_minimum_distance_angstrom) &&
           isfinite(row.element_vdw_ligand_minimum_ratio) &&
           isfinite(row.element_vdw_receptor_minimum_distance_angstrom) &&
           isfinite(row.element_vdw_receptor_minimum_ratio) &&
           isfinite(static_cast<double>(row.atom_count));
}

__global__ void validity_fixed64_kernel(
    ValidityDeviceContext context,
    const bg_docking_pose_validity_candidate_state *candidate_state,
    const bg_docking_scorer_v1_failure *upstream_failure,
    const double *quaternion_x,
    const double *quaternion_y,
    const double *quaternion_z,
    const double *quaternion_w,
    const double *candidate_x,
    const double *candidate_y,
    const double *candidate_z,
    bg_docking_pose_validity_row_v1 *out_rows) {
    const size_t slot = static_cast<size_t>(blockIdx.x);
    if (threadIdx.x != 0 || slot >= kValidityCandidateCount) {
        return;
    }
    if (candidate_state[slot] ==
        BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE) {
        out_rows[slot] = validity_failure_row(
            slot,
            BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE,
            BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER,
            upstream_failure[slot],
            0);
        return;
    }

    const size_t offset = slot * context.ligand_atom_count;
    for (size_t atom = 0; atom < context.ligand_atom_count; ++atom) {
        if (!validity_finite_coordinate(validity_ligand_coordinate(
                candidate_x, candidate_y, candidate_z, offset, atom))) {
            out_rows[slot] = validity_failure_row(
                slot,
                BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE,
                BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES,
                BG_DOCKING_SCORER_V1_FAILURE_NONE,
                context.ligand_atom_count);
            return;
        }
    }

    bg_docking_pose_validity_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
    row.failure_code = BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;

    validity_rotation_measurements(
        quaternion_x[slot],
        quaternion_y[slot],
        quaternion_z[slot],
        quaternion_w[slot],
        &row.rotation_orthogonality_max_error,
        &row.rotation_determinant);
    if (row.rotation_orthogonality_max_error <=
            context.rotation_tolerance &&
        fabs(row.rotation_determinant - 1.0) <=
            context.rotation_tolerance) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_PROPER_ROTATION;
    }

    double maximum_bond_delta = 0.0;
    for (size_t bond = 0; bond < context.bond_count; ++bond) {
        const size_t first = static_cast<size_t>(context.bond_i[bond]);
        const size_t second = static_cast<size_t>(context.bond_j[bond]);
        const double reference = validity_distance(
            validity_reference_coordinate(context, first),
            validity_reference_coordinate(context, second));
        const double observed = validity_distance(
            validity_ligand_coordinate(
                candidate_x, candidate_y, candidate_z, offset, first),
            validity_ligand_coordinate(
                candidate_x, candidate_y, candidate_z, offset, second));
        maximum_bond_delta =
            fmax(maximum_bond_delta, fabs(reference - observed));
    }
    row.max_bond_length_delta_angstrom = maximum_bond_delta;
    if (maximum_bond_delta <= context.bond_length_tolerance) {
        row.passed_check_mask |= BG_DOCKING_POSE_VALIDITY_CHECK_BOND_LENGTHS;
    }

    const size_t ligand_pair_count =
        context.ligand_atom_count * (context.ligand_atom_count - 1) / 2;
    if (ligand_pair_count > context.max_pair_checks) {
        out_rows[slot] = validity_failure_row(
            slot,
            BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE,
            BG_DOCKING_POSE_VALIDITY_FAILURE_LIGAND_PAIR_CAPACITY,
            BG_DOCKING_SCORER_V1_FAILURE_NONE,
            ligand_pair_count);
        return;
    }
    double minimum_ligand_distance = INFINITY;
    double minimum_ligand_ratio = INFINITY;
    size_t evaluated_ligand_pairs = 0;
    size_t ligand_severe_overlap_count = 0;
    for (size_t first = 0; first < context.ligand_atom_count; ++first) {
        for (size_t second = first + 1; second < context.ligand_atom_count;
             ++second) {
            if (validity_is_excluded(context, first, second)) {
                continue;
            }
            ++evaluated_ligand_pairs;
            if (evaluated_ligand_pairs >
                context.max_element_ligand_pair_checks) {
                out_rows[slot] = validity_failure_row(
                    slot,
                    BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE,
                    BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_LIGAND_PAIR_CAPACITY,
                    BG_DOCKING_SCORER_V1_FAILURE_NONE,
                    evaluated_ligand_pairs);
                return;
            }
            const double observed = validity_distance(
                validity_ligand_coordinate(
                    candidate_x, candidate_y, candidate_z, offset, first),
                validity_ligand_coordinate(
                    candidate_x, candidate_y, candidate_z, offset, second));
            minimum_ligand_distance = fmin(minimum_ligand_distance, observed);
            const double ratio =
                observed /
                (context.ligand_radius[first] +
                 context.ligand_radius[second]);
            minimum_ligand_ratio = fmin(minimum_ligand_ratio, ratio);
            if (ratio < context.severe_overlap_scale) {
                ++ligand_severe_overlap_count;
            }
        }
    }
    row.minimum_ligand_nonbonded_distance_angstrom =
        validity_minimum_or_sentinel(minimum_ligand_distance);
    row.evaluated_ligand_nonbonded_pair_count =
        static_cast<uint64_t>(evaluated_ligand_pairs);
    row.excluded_ligand_pair_count =
        static_cast<uint64_t>(context.exclusion_count);
    row.element_vdw_ligand_pair_count =
        static_cast<uint64_t>(evaluated_ligand_pairs);
    row.element_vdw_ligand_severe_overlap_count =
        static_cast<uint64_t>(ligand_severe_overlap_count);
    row.element_vdw_ligand_minimum_distance_angstrom =
        validity_minimum_or_sentinel(minimum_ligand_distance);
    row.element_vdw_ligand_minimum_ratio =
        validity_minimum_or_sentinel(minimum_ligand_ratio);
    if (row.minimum_ligand_nonbonded_distance_angstrom >=
        context.ligand_self_clash) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_LIGAND_SELF_CLASH;
    }
    if (ligand_severe_overlap_count == 0) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_LIGAND_VDW;
    }

    const size_t cross_count =
        context.ligand_atom_count * context.receptor_atom_count;
    if (cross_count > context.max_cross_checks) {
        out_rows[slot] = validity_failure_row(
            slot,
            BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE,
            BG_DOCKING_POSE_VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY,
            BG_DOCKING_SCORER_V1_FAILURE_NONE,
            cross_count);
        return;
    }
    double minimum_receptor_distance = INFINITY;
    for (size_t ligand = 0; ligand < context.ligand_atom_count; ++ligand) {
        const ValidityVector3 coordinate = validity_ligand_coordinate(
            candidate_x, candidate_y, candidate_z, offset, ligand);
        for (size_t receptor = 0; receptor < context.receptor_atom_count;
             ++receptor) {
            minimum_receptor_distance = fmin(
                minimum_receptor_distance,
                validity_distance(
                    coordinate,
                    validity_receptor_coordinate(context, receptor)));
        }
    }
    row.minimum_receptor_ligand_distance_angstrom =
        minimum_receptor_distance;
    row.evaluated_receptor_ligand_pair_count =
        static_cast<uint64_t>(cross_count);
    if (minimum_receptor_distance >= context.receptor_ligand_clash) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH;
    }

    double minimum_chiral_volume = INFINITY;
    bool chirality_preserved = true;
    for (size_t chirality = 0; chirality < context.chirality_count;
         ++chirality) {
        const size_t center =
            static_cast<size_t>(context.chirality_center[chirality]);
        const size_t first =
            static_cast<size_t>(context.chirality_i[chirality]);
        const size_t second =
            static_cast<size_t>(context.chirality_j[chirality]);
        const size_t third =
            static_cast<size_t>(context.chirality_k[chirality]);
        const double reference = validity_signed_volume(
            validity_reference_coordinate(context, center),
            validity_reference_coordinate(context, first),
            validity_reference_coordinate(context, second),
            validity_reference_coordinate(context, third));
        const double observed = validity_signed_volume(
            validity_ligand_coordinate(
                candidate_x, candidate_y, candidate_z, offset, center),
            validity_ligand_coordinate(
                candidate_x, candidate_y, candidate_z, offset, first),
            validity_ligand_coordinate(
                candidate_x, candidate_y, candidate_z, offset, second),
            validity_ligand_coordinate(
                candidate_x, candidate_y, candidate_z, offset, third));
        minimum_chiral_volume = fmin(
            minimum_chiral_volume,
            fmin(fabs(reference), fabs(observed)));
        if (fabs(reference) <= context.chirality_volume_tolerance ||
            fabs(observed) <= context.chirality_volume_tolerance ||
            reference * observed < 0.0) {
            chirality_preserved = false;
        }
    }
    row.minimum_declared_chiral_volume =
        isfinite(minimum_chiral_volume) ? minimum_chiral_volume : 0.0;
    row.declared_chirality_center_count =
        static_cast<uint64_t>(context.chirality_count);
    if (chirality_preserved) {
        row.passed_check_mask |= BG_DOCKING_POSE_VALIDITY_CHECK_CHIRALITY;
    }

    const ValidityVector3 pocket_center = {
        context.pocket_center[0],
        context.pocket_center[1],
        context.pocket_center[2],
    };
    double maximum_pocket_distance = 0.0;
    for (size_t ligand = 0; ligand < context.ligand_atom_count; ++ligand) {
        maximum_pocket_distance = fmax(
            maximum_pocket_distance,
            validity_distance(
                validity_ligand_coordinate(
                    candidate_x, candidate_y, candidate_z, offset, ligand),
                pocket_center));
    }
    row.maximum_pocket_center_distance_angstrom = maximum_pocket_distance;
    if (maximum_pocket_distance <= context.pocket_radius) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_DECLARED_POCKET;
    }

    size_t receptor_candidate_pair_count = 0;
    size_t receptor_severe_overlap_count = 0;
    double minimum_receptor_element_distance = INFINITY;
    double minimum_receptor_ratio = INFINITY;
    for (size_t ligand = 0; ligand < context.ligand_atom_count; ++ligand) {
        const ValidityVector3 coordinate = validity_ligand_coordinate(
            candidate_x, candidate_y, candidate_z, offset, ligand);
        for (size_t receptor = 0; receptor < context.receptor_atom_count;
             ++receptor) {
            const ValidityVector3 receptor_coordinate =
                validity_receptor_coordinate(context, receptor);
            if (!validity_neighbor_cells(
                    coordinate,
                    receptor_coordinate,
                    context.contact_cell_size)) {
                continue;
            }
            ++receptor_candidate_pair_count;
            if (receptor_candidate_pair_count >
                context.max_element_receptor_candidate_pairs) {
                out_rows[slot] = validity_failure_row(
                    slot,
                    BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE,
                    BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_RECEPTOR_CANDIDATE_CAPACITY,
                    BG_DOCKING_SCORER_V1_FAILURE_NONE,
                    receptor_candidate_pair_count);
                return;
            }
            const double observed =
                validity_distance(coordinate, receptor_coordinate);
            minimum_receptor_element_distance =
                fmin(minimum_receptor_element_distance, observed);
            const double ratio =
                observed /
                (context.ligand_radius[ligand] +
                 context.receptor_radius[receptor]);
            minimum_receptor_ratio = fmin(minimum_receptor_ratio, ratio);
            if (ratio < context.severe_overlap_scale) {
                ++receptor_severe_overlap_count;
            }
        }
    }
    row.element_vdw_receptor_candidate_pair_count =
        static_cast<uint64_t>(receptor_candidate_pair_count);
    row.element_vdw_receptor_full_cartesian_pair_count =
        static_cast<uint64_t>(cross_count);
    row.element_vdw_receptor_cell_count =
        static_cast<uint64_t>(context.receptor_cell_count);
    row.element_vdw_receptor_severe_overlap_count =
        static_cast<uint64_t>(receptor_severe_overlap_count);
    row.element_vdw_receptor_minimum_distance_angstrom =
        validity_minimum_or_sentinel(minimum_receptor_element_distance);
    row.element_vdw_receptor_minimum_ratio =
        validity_minimum_or_sentinel(minimum_receptor_ratio);
    if (receptor_severe_overlap_count == 0) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW;
    }
    row.atom_count = static_cast<uint64_t>(context.ligand_atom_count);
    row.blocker_mask =
        BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ row.passed_check_mask;
    if (!validity_measurements_finite(row)) {
        out_rows[slot] = validity_failure_row(
            slot,
            BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE,
            BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT,
            BG_DOCKING_SCORER_V1_FAILURE_NONE,
            0);
        return;
    }
    out_rows[slot] = row;
}

bool validity_host_row_is_valid(
    const bg_docking_pose_validity_row_v1 &row,
    size_t slot) noexcept {
    if (row.slot_index != slot ||
        !validity_reserved_is_zero(row.reserved)) {
        return false;
    }
    if (row.status == BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED) {
        return row.failure_code == BG_DOCKING_POSE_VALIDITY_FAILURE_NONE &&
               row.upstream_scorer_failure_code ==
                   BG_DOCKING_SCORER_V1_FAILURE_NONE &&
               (row.passed_check_mask &
                static_cast<bg_docking_pose_validity_check_mask>(
                    ~static_cast<bg_docking_pose_validity_check_mask>(
                        BG_DOCKING_POSE_VALIDITY_CHECK_ALL))) == 0 &&
               row.blocker_mask ==
                   (BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^
                    row.passed_check_mask);
    }
    if (row.status ==
        BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE) {
        return row.failure_code ==
                   BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER &&
               row.upstream_scorer_failure_code >=
                   BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED &&
               row.upstream_scorer_failure_code <=
                   BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE;
    }
    return row.status == BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE &&
           row.failure_code >=
               BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES &&
           row.failure_code <=
               BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT &&
           row.upstream_scorer_failure_code ==
               BG_DOCKING_SCORER_V1_FAILURE_NONE;
}

}  // namespace

extern "C" int32_t BG_DOCKING_VALIDITY_CREATE(
    int32_t device_ordinal,
    const bg_docking_pose_validity_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity) {
    validity_clear_error(error_message, error_capacity);
    if (out_state != nullptr) {
        *out_state = nullptr;
    }
    if (device_ordinal < 0 || descriptor == nullptr || out_state == nullptr) {
        return validity_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_VALIDITY_LANE
            " pose-validity create arguments are invalid");
    }
    if (descriptor->struct_size != sizeof(*descriptor) ||
        descriptor->abi_version != BG_ABI_VERSION ||
        descriptor->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        descriptor->reserved0 != 0 ||
        !validity_reserved_is_zero(descriptor->reserved) ||
        descriptor->receptor_atom_count == 0 ||
        descriptor->receptor_atom_count > kValidityMaxReceptorAtoms ||
        descriptor->ligand_atom_count == 0 ||
        descriptor->ligand_atom_count > kValidityMaxLigandAtoms ||
        descriptor->bond_count >
            descriptor->ligand_atom_count *
                (descriptor->ligand_atom_count - UINT64_C(1)) /
                UINT64_C(2) ||
        descriptor->ligand_exclusion_count >
            descriptor->ligand_atom_count *
                (descriptor->ligand_atom_count - UINT64_C(1)) /
                UINT64_C(2) ||
        descriptor->chirality_center_count >
            descriptor->ligand_atom_count ||
        !std::isfinite(descriptor->contact_cell_size_angstrom) ||
        descriptor->contact_cell_size_angstrom <= 0.0) {
        return validity_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_VALIDITY_LANE
            " pose-validity descriptor is outside ABI bounds");
    }
    const size_t receptor_count =
        static_cast<size_t>(descriptor->receptor_atom_count);
    const size_t ligand_count =
        static_cast<size_t>(descriptor->ligand_atom_count);
    const size_t bond_count = static_cast<size_t>(descriptor->bond_count);
    const size_t exclusion_count =
        static_cast<size_t>(descriptor->ligand_exclusion_count);
    const size_t chirality_count =
        static_cast<size_t>(descriptor->chirality_center_count);
    const bool channels_valid =
        validity_counted_pointer_is_valid(
            descriptor->receptor_x_angstrom, receptor_count) &&
        validity_counted_pointer_is_valid(
            descriptor->receptor_y_angstrom, receptor_count) &&
        validity_counted_pointer_is_valid(
            descriptor->receptor_z_angstrom, receptor_count) &&
        validity_counted_pointer_is_valid(
            descriptor->receptor_vdw_radius_angstrom, receptor_count) &&
        validity_counted_pointer_is_valid(
            descriptor->ligand_reference_x_angstrom, ligand_count) &&
        validity_counted_pointer_is_valid(
            descriptor->ligand_reference_y_angstrom, ligand_count) &&
        validity_counted_pointer_is_valid(
            descriptor->ligand_reference_z_angstrom, ligand_count) &&
        validity_counted_pointer_is_valid(
            descriptor->ligand_vdw_radius_angstrom, ligand_count) &&
        validity_counted_pointer_is_valid(descriptor->bond_atom_i, bond_count) &&
        validity_counted_pointer_is_valid(descriptor->bond_atom_j, bond_count) &&
        validity_counted_pointer_is_valid(
            descriptor->ligand_exclusion_atom_i, exclusion_count) &&
        validity_counted_pointer_is_valid(
            descriptor->ligand_exclusion_atom_j, exclusion_count) &&
        validity_counted_pointer_is_valid(
            descriptor->chirality_center_atom, chirality_count) &&
        validity_counted_pointer_is_valid(
            descriptor->chirality_atom_i, chirality_count) &&
        validity_counted_pointer_is_valid(
            descriptor->chirality_atom_j, chirality_count) &&
        validity_counted_pointer_is_valid(
            descriptor->chirality_atom_k, chirality_count);
    if (!channels_valid) {
        return validity_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_VALIDITY_LANE
            " pose-validity descriptor channel is null");
    }

    ValidityDeviceGuard device_guard;
    hipError_t status = hipSetDevice(device_ordinal);
    if (status != hipSuccess) {
        return validity_fail_hip(
            status,
            error_message,
            error_capacity,
            "pose-validity device selection");
    }
    std::unique_ptr<ValidityState> state(
        new (std::nothrow) ValidityState{});
    if (state == nullptr) {
        return validity_fail(
            BG_STATUS_OUT_OF_MEMORY,
            error_message,
            error_capacity,
            BG_DOCKING_VALIDITY_LANE
            " pose-validity state allocation failed");
    }
    state->device_ordinal = device_ordinal;

#define BG_HIP_VALIDITY_CONTEXT_COPY(member, source, count, operation)       \
    do {                                                                     \
        status = state->member.copy_from((source), (count));                 \
        if (status != hipSuccess) {                                          \
            return validity_fail_hip(                                        \
                status, error_message, error_capacity, (operation));         \
        }                                                                    \
    } while (false)

    BG_HIP_VALIDITY_CONTEXT_COPY(
        receptor_x,
        descriptor->receptor_x_angstrom,
        receptor_count,
        "pose-validity receptor x copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        receptor_y,
        descriptor->receptor_y_angstrom,
        receptor_count,
        "pose-validity receptor y copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        receptor_z,
        descriptor->receptor_z_angstrom,
        receptor_count,
        "pose-validity receptor z copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        receptor_radius,
        descriptor->receptor_vdw_radius_angstrom,
        receptor_count,
        "pose-validity receptor radius copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        ligand_reference_x,
        descriptor->ligand_reference_x_angstrom,
        ligand_count,
        "pose-validity ligand reference x copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        ligand_reference_y,
        descriptor->ligand_reference_y_angstrom,
        ligand_count,
        "pose-validity ligand reference y copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        ligand_reference_z,
        descriptor->ligand_reference_z_angstrom,
        ligand_count,
        "pose-validity ligand reference z copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        ligand_radius,
        descriptor->ligand_vdw_radius_angstrom,
        ligand_count,
        "pose-validity ligand radius copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        bond_i,
        descriptor->bond_atom_i,
        bond_count,
        "pose-validity bond i copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        bond_j,
        descriptor->bond_atom_j,
        bond_count,
        "pose-validity bond j copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        exclusion_i,
        descriptor->ligand_exclusion_atom_i,
        exclusion_count,
        "pose-validity exclusion i copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        exclusion_j,
        descriptor->ligand_exclusion_atom_j,
        exclusion_count,
        "pose-validity exclusion j copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        chirality_center,
        descriptor->chirality_center_atom,
        chirality_count,
        "pose-validity chirality center copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        chirality_i,
        descriptor->chirality_atom_i,
        chirality_count,
        "pose-validity chirality i copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        chirality_j,
        descriptor->chirality_atom_j,
        chirality_count,
        "pose-validity chirality j copy");
    BG_HIP_VALIDITY_CONTEXT_COPY(
        chirality_k,
        descriptor->chirality_atom_k,
        chirality_count,
        "pose-validity chirality k copy");

#undef BG_HIP_VALIDITY_CONTEXT_COPY

    using HostCell = std::tuple<int64_t, int64_t, int64_t>;
    std::set<HostCell> receptor_cells;
    for (size_t atom = 0; atom < receptor_count; ++atom) {
        receptor_cells.emplace(
            static_cast<int64_t>(std::floor(
                descriptor->receptor_x_angstrom[atom] /
                descriptor->contact_cell_size_angstrom)),
            static_cast<int64_t>(std::floor(
                descriptor->receptor_y_angstrom[atom] /
                descriptor->contact_cell_size_angstrom)),
            static_cast<int64_t>(std::floor(
                descriptor->receptor_z_angstrom[atom] /
                descriptor->contact_cell_size_angstrom)));
    }

    state->context = {
        receptor_count,
        ligand_count,
        state->receptor_x.get(),
        state->receptor_y.get(),
        state->receptor_z.get(),
        state->receptor_radius.get(),
        state->ligand_reference_x.get(),
        state->ligand_reference_y.get(),
        state->ligand_reference_z.get(),
        state->ligand_radius.get(),
        bond_count,
        state->bond_i.get(),
        state->bond_j.get(),
        exclusion_count,
        state->exclusion_i.get(),
        state->exclusion_j.get(),
        chirality_count,
        state->chirality_center.get(),
        state->chirality_i.get(),
        state->chirality_j.get(),
        state->chirality_k.get(),
        {
            descriptor->pocket_center_angstrom[0],
            descriptor->pocket_center_angstrom[1],
            descriptor->pocket_center_angstrom[2],
        },
        descriptor->pocket_radius_angstrom,
        descriptor->bond_length_tolerance_angstrom,
        descriptor->ligand_self_clash_angstrom,
        descriptor->receptor_ligand_clash_angstrom,
        descriptor->rotation_tolerance,
        descriptor->chirality_volume_tolerance,
        descriptor->severe_overlap_scale,
        descriptor->contact_cell_size_angstrom,
        static_cast<size_t>(descriptor->max_pair_checks),
        static_cast<size_t>(descriptor->max_cross_checks),
        static_cast<size_t>(descriptor->max_element_ligand_pair_checks),
        static_cast<size_t>(
            descriptor->max_element_receptor_candidate_pairs),
        receptor_cells.size(),
    };
    *out_state = state.release();
    return BG_STATUS_OK;
}

extern "C" void BG_DOCKING_VALIDITY_DESTROY(void *state) {
    if (state == nullptr) {
        return;
    }
    auto *typed = static_cast<ValidityState *>(state);
    ValidityDeviceGuard device_guard;
    if (hipSetDevice(typed->device_ordinal) == hipSuccess) {
        static_cast<void>(hipDeviceSynchronize());
    }
    delete typed;
}

extern "C" int32_t BG_DOCKING_VALIDITY_EVALUATE_FIXED64(
    const void *state,
    const bg_docking_pose_validity_candidate_batch_soa_v1 *candidates,
    bg_docking_pose_validity_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity) {
    validity_clear_error(error_message, error_capacity);
    if (state == nullptr || candidates == nullptr || out_rows == nullptr) {
        return validity_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_VALIDITY_LANE
            " pose-validity batch arguments are invalid");
    }
    const auto *typed = static_cast<const ValidityState *>(state);
    if (candidates->struct_size != sizeof(*candidates) ||
        candidates->abi_version != BG_ABI_VERSION ||
        candidates->candidate_count != kValidityCandidateCount ||
        candidates->ligand_atom_count != typed->context.ligand_atom_count ||
        candidates->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        candidates->reserved0 != 0 ||
        !validity_reserved_is_zero(candidates->reserved) ||
        candidates->candidate_state == nullptr ||
        candidates->upstream_scorer_failure_code == nullptr ||
        candidates->quaternion_x == nullptr ||
        candidates->quaternion_y == nullptr ||
        candidates->quaternion_z == nullptr ||
        candidates->quaternion_w == nullptr ||
        candidates->x_angstrom == nullptr ||
        candidates->y_angstrom == nullptr ||
        candidates->z_angstrom == nullptr) {
        return validity_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_VALIDITY_LANE
            " pose-validity fixed64 descriptor is invalid");
    }
    for (size_t slot = 0; slot < kValidityCandidateCount; ++slot) {
        const auto candidate = candidates->candidate_state[slot];
        const auto upstream = candidates->upstream_scorer_failure_code[slot];
        if ((candidate ==
                 BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE &&
             (upstream < BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED ||
              upstream > BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE)) ||
            (candidate == BG_DOCKING_POSE_VALIDITY_CANDIDATE_EVALUATE &&
             upstream != BG_DOCKING_SCORER_V1_FAILURE_NONE) ||
            (candidate !=
                 BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE &&
             candidate != BG_DOCKING_POSE_VALIDITY_CANDIDATE_EVALUATE)) {
            return validity_fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                BG_DOCKING_VALIDITY_LANE
                " pose-validity state/failure binding is invalid");
        }
    }
    if (typed->context.ligand_atom_count >
        std::numeric_limits<size_t>::max() / kValidityCandidateCount) {
        return validity_fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            error_message,
            error_capacity,
            BG_DOCKING_VALIDITY_LANE
            " pose-validity coordinate denominator overflows");
    }
    const size_t coordinate_count =
        kValidityCandidateCount * typed->context.ligand_atom_count;
    ValidityDeviceGuard device_guard;
    hipError_t status = hipSetDevice(typed->device_ordinal);
    if (status != hipSuccess) {
        return validity_fail_hip(
            status,
            error_message,
            error_capacity,
            "pose-validity device selection");
    }

    ValidityDeviceBuffer<bg_docking_pose_validity_candidate_state>
        device_candidate_state;
    ValidityDeviceBuffer<bg_docking_scorer_v1_failure>
        device_upstream_failure;
    ValidityDeviceBuffer<double> device_quaternion_x;
    ValidityDeviceBuffer<double> device_quaternion_y;
    ValidityDeviceBuffer<double> device_quaternion_z;
    ValidityDeviceBuffer<double> device_quaternion_w;
    ValidityDeviceBuffer<double> device_x;
    ValidityDeviceBuffer<double> device_y;
    ValidityDeviceBuffer<double> device_z;
    ValidityDeviceBuffer<bg_docking_pose_validity_row_v1> device_rows;

#define BG_HIP_VALIDITY_BATCH_COPY(member, source, count, operation)         \
    do {                                                                     \
        status = member.copy_from((source), (count));                        \
        if (status != hipSuccess) {                                          \
            return validity_fail_hip(                                        \
                status, error_message, error_capacity, (operation));         \
        }                                                                    \
    } while (false)

    BG_HIP_VALIDITY_BATCH_COPY(
        device_candidate_state,
        candidates->candidate_state,
        kValidityCandidateCount,
        "pose-validity candidate state copy");
    BG_HIP_VALIDITY_BATCH_COPY(
        device_upstream_failure,
        candidates->upstream_scorer_failure_code,
        kValidityCandidateCount,
        "pose-validity upstream failure copy");
    BG_HIP_VALIDITY_BATCH_COPY(
        device_quaternion_x,
        candidates->quaternion_x,
        kValidityCandidateCount,
        "pose-validity quaternion x copy");
    BG_HIP_VALIDITY_BATCH_COPY(
        device_quaternion_y,
        candidates->quaternion_y,
        kValidityCandidateCount,
        "pose-validity quaternion y copy");
    BG_HIP_VALIDITY_BATCH_COPY(
        device_quaternion_z,
        candidates->quaternion_z,
        kValidityCandidateCount,
        "pose-validity quaternion z copy");
    BG_HIP_VALIDITY_BATCH_COPY(
        device_quaternion_w,
        candidates->quaternion_w,
        kValidityCandidateCount,
        "pose-validity quaternion w copy");
    BG_HIP_VALIDITY_BATCH_COPY(
        device_x,
        candidates->x_angstrom,
        coordinate_count,
        "pose-validity candidate x copy");
    BG_HIP_VALIDITY_BATCH_COPY(
        device_y,
        candidates->y_angstrom,
        coordinate_count,
        "pose-validity candidate y copy");
    BG_HIP_VALIDITY_BATCH_COPY(
        device_z,
        candidates->z_angstrom,
        coordinate_count,
        "pose-validity candidate z copy");

#undef BG_HIP_VALIDITY_BATCH_COPY

    status = device_rows.allocate(kValidityCandidateCount);
    if (status != hipSuccess) {
        return validity_fail_hip(
            status,
            error_message,
            error_capacity,
            "pose-validity output allocation");
    }
    hipLaunchKernelGGL(
        validity_fixed64_kernel,
        dim3(static_cast<uint32_t>(kValidityCandidateCount)),
        dim3(1),
        0,
        0,
        typed->context,
        device_candidate_state.get(),
        device_upstream_failure.get(),
        device_quaternion_x.get(),
        device_quaternion_y.get(),
        device_quaternion_z.get(),
        device_quaternion_w.get(),
        device_x.get(),
        device_y.get(),
        device_z.get(),
        device_rows.get());
    hipError_t execution_status = hipGetLastError();
    if (execution_status == hipSuccess) {
        execution_status = hipDeviceSynchronize();
    }
    if (execution_status != hipSuccess) {
        return validity_fail_hip(
            execution_status,
            error_message,
            error_capacity,
            "pose-validity kernel execution");
    }
    std::array<bg_docking_pose_validity_row_v1, kValidityCandidateCount>
        host_rows{};
    const hipError_t copy_status =
        device_rows.copy_to(host_rows.data(), host_rows.size());
    if (copy_status != hipSuccess) {
        return validity_fail_hip(
            copy_status,
            error_message,
            error_capacity,
            "pose-validity result copy");
    }
    for (size_t slot = 0; slot < host_rows.size(); ++slot) {
        if (!validity_host_row_is_valid(host_rows[slot], slot)) {
            return validity_fail(
                BG_STATUS_BACKEND_ERROR,
                error_message,
                error_capacity,
                BG_DOCKING_VALIDITY_LANE
                " pose-validity returned an invalid device row");
        }
    }
    std::memcpy(out_rows, host_rows.data(), sizeof(host_rows));
    return BG_STATUS_OK;
}
