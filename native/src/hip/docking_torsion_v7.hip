#include <hip/hip_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <memory>
#include <new>

#if !defined(BG_DOCKING_TORSION_V7_CREATE) || \
    !defined(BG_DOCKING_TORSION_V7_DESTROY) || \
    !defined(BG_DOCKING_TORSION_V7_REFINE_FIXED64) || \
    !defined(BG_DOCKING_TORSION_V7_LANE)
#  error "native HIP torsion V7 provider identity is not configured"
#endif

namespace {

constexpr size_t kTorsionCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr size_t kTorsionMaxMoves = BG_DOCKING_TORSION_V7_MAX_MOVES;
constexpr size_t kTorsionMaxLigandAtoms = 512;
constexpr size_t kTorsionMaxReceptorAtoms = 65'536;
constexpr size_t kTorsionMaxAuthorityRotors = kTorsionMaxLigandAtoms;
constexpr size_t kTorsionMaxEvaluatedRotors = 32;
constexpr uint64_t kTorsionMaxCallerSteps = UINT64_C(10'000);
constexpr double kTorsionPi =
    3.141592653589793238462643383279502884;

void torsion_clear_error(char *message, size_t capacity) noexcept {
    if (message != nullptr && capacity > 0) {
        message[0] = '\0';
    }
}

int32_t torsion_fail(
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

int32_t torsion_fail_hip(
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
            BG_DOCKING_TORSION_V7_LANE,
            operation,
            detail == nullptr ? "unknown HIP runtime error" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

template <size_t Count>
bool torsion_reserved_is_zero(const uint64_t (&values)[Count]) noexcept {
    for (const uint64_t value : values) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

template <typename Value>
bool torsion_pointer_valid(const Value *pointer, size_t count) noexcept {
    return count == 0 ||
           (pointer != nullptr &&
            reinterpret_cast<uintptr_t>(pointer) % alignof(Value) == 0);
}

template <typename Value>
class TorsionDeviceBuffer final {
public:
    TorsionDeviceBuffer() = default;
    TorsionDeviceBuffer(const TorsionDeviceBuffer &) = delete;
    TorsionDeviceBuffer &operator=(const TorsionDeviceBuffer &) = delete;

    ~TorsionDeviceBuffer() {
        if (pointer_ != nullptr) {
            static_cast<void>(hipFree(pointer_));
        }
    }

    hipError_t allocate(size_t count) noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (pointer_ != nullptr ||
            count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        return hipMalloc(
            reinterpret_cast<void **>(&pointer_), count * sizeof(Value));
    }

    hipError_t copy_from(const Value *source, size_t count) noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (source == nullptr) {
            return hipErrorInvalidValue;
        }
        hipError_t status = allocate(count);
        if (status != hipSuccess) {
            return status;
        }
        return hipMemcpy(
            pointer_, source, count * sizeof(Value), hipMemcpyHostToDevice);
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

class TorsionDeviceGuard final {
public:
    TorsionDeviceGuard() noexcept {
        if (hipGetDevice(&previous_) == hipSuccess) {
            has_previous_ = true;
        }
    }
    TorsionDeviceGuard(const TorsionDeviceGuard &) = delete;
    TorsionDeviceGuard &operator=(const TorsionDeviceGuard &) = delete;
    ~TorsionDeviceGuard() {
        if (has_previous_) {
            static_cast<void>(hipSetDevice(previous_));
        }
    }

private:
    int previous_ = 0;
    bool has_previous_ = false;
};

struct TorsionConfig final {
    double receptor_overlap_scale;
    double internal_overlap_scale;
    double internal_overlap_weight;
    size_t maximum_baseline_v6_steps;
    size_t maximum_torsions_evaluated;
    size_t maximum_torsion_steps;
    size_t maximum_backtracking_evaluations;
    double maximum_torsion_step_radians;
    double minimum_torsion_step_radians;
    double maximum_total_torsion_path_radians;
    double maximum_centroid_offset_angstrom;
    double minimum_selected_final_receptor_penalty;
    double maximum_selected_final_receptor_penalty;
    double penalty_tolerance;
    double epsilon_angstrom;
};

struct TorsionDeviceContext final {
    size_t receptor_count;
    size_t ligand_count;
    size_t rotor_count;
    size_t internal_pair_count;
    const double *receptor_x;
    const double *receptor_y;
    const double *receptor_z;
    const double *receptor_radii;
    const double *ligand_radii;
    double pocket_center[3];
    const int32_t *parents;
    const uint64_t *rotors;
    const uint64_t *internal_i;
    const uint64_t *internal_j;
    TorsionConfig config;
};

struct TorsionState final {
    int32_t device_ordinal = 0;
    size_t receptor_count = 0;
    size_t ligand_count = 0;
    size_t rotor_count = 0;
    size_t internal_pair_count = 0;
    double pocket_center[3]{};
    TorsionConfig config{};
    TorsionDeviceBuffer<double> receptor_x;
    TorsionDeviceBuffer<double> receptor_y;
    TorsionDeviceBuffer<double> receptor_z;
    TorsionDeviceBuffer<double> receptor_radii;
    TorsionDeviceBuffer<double> ligand_radii;
    TorsionDeviceBuffer<int32_t> parents;
    TorsionDeviceBuffer<uint64_t> rotors;
    TorsionDeviceBuffer<uint64_t> internal_i;
    TorsionDeviceBuffer<uint64_t> internal_j;

    TorsionDeviceContext device_context() const noexcept {
        TorsionDeviceContext context{};
        context.receptor_count = receptor_count;
        context.ligand_count = ligand_count;
        context.rotor_count = rotor_count;
        context.internal_pair_count = internal_pair_count;
        context.receptor_x = receptor_x.get();
        context.receptor_y = receptor_y.get();
        context.receptor_z = receptor_z.get();
        context.receptor_radii = receptor_radii.get();
        context.ligand_radii = ligand_radii.get();
        context.pocket_center[0] = pocket_center[0];
        context.pocket_center[1] = pocket_center[1];
        context.pocket_center[2] = pocket_center[2];
        context.parents = parents.get();
        context.rotors = rotors.get();
        context.internal_i = internal_i.get();
        context.internal_j = internal_j.get();
        context.config = config;
        return context;
    }
};

struct TorsionDeviceBatch final {
    const int32_t *candidate_state;
    const uint8_t *eligible;
    const uint64_t *max_steps;
    const uint64_t *baseline_steps;
    const double *source_x;
    const double *source_y;
    const double *source_z;
    const double *baseline_x;
    const double *baseline_y;
    const double *baseline_z;
    const double *baseline_angles;
};

struct TorsionDeviceOutputs final {
    bg_docking_torsion_v7_row_v1 *rows;
    bg_docking_torsion_v7_move_v1 *moves;
    double *optimized_x;
    double *optimized_y;
    double *optimized_z;
    double *optimized_angles;
    double *final_x;
    double *final_y;
    double *final_z;
    double *final_angles;
};

struct TorsionScratch final {
    double *current_x;
    double *current_y;
    double *current_z;
    double *current_angles;
    double *trial_x;
    double *trial_y;
    double *trial_z;
    double *best_x;
    double *best_y;
    double *best_z;
    double *current_receptor;
    double *trial_receptor;
    double *best_receptor;
    double *current_internal;
    double *trial_internal;
    double *best_internal;
};

struct TorsionObjective final {
    double receptor;
    double internal;
    double combined;
};

struct TorsionVector3 final {
    double x;
    double y;
    double z;
};

__device__ double torsion_canonical_zero(double value) {
    return value == 0.0 ? 0.0 : value;
}

__device__ TorsionVector3 torsion_minus(
    TorsionVector3 left,
    TorsionVector3 right) {
    return {left.x - right.x, left.y - right.y, left.z - right.z};
}

__device__ TorsionVector3 torsion_plus(
    TorsionVector3 left,
    TorsionVector3 right) {
    return {left.x + right.x, left.y + right.y, left.z + right.z};
}

__device__ TorsionVector3 torsion_scale(
    TorsionVector3 value,
    double factor) {
    return {value.x * factor, value.y * factor, value.z * factor};
}

__device__ double torsion_dot(
    TorsionVector3 left,
    TorsionVector3 right) {
    return left.x * right.x + left.y * right.y + left.z * right.z;
}

__device__ TorsionVector3 torsion_cross(
    TorsionVector3 left,
    TorsionVector3 right) {
    return {
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    };
}

__device__ double torsion_norm(TorsionVector3 value) {
    return sqrt(torsion_dot(value, value));
}

__device__ bool torsion_finite(TorsionVector3 value) {
    return isfinite(value.x) && isfinite(value.y) && isfinite(value.z);
}

__device__ bool torsion_is_descendant(
    size_t candidate,
    size_t rotor,
    const TorsionDeviceContext &context) {
    size_t current = candidate;
    for (size_t depth = 0; depth <= context.ligand_count; ++depth) {
        if (current == rotor) {
            return true;
        }
        const int32_t parent = context.parents[current];
        if (parent < 0) {
            return false;
        }
        current = static_cast<size_t>(parent);
    }
    return false;
}

__device__ double torsion_internal_penalty(
    const TorsionDeviceContext &context,
    const double *x,
    const double *y,
    const double *z,
    size_t first,
    size_t second) {
    const TorsionVector3 difference = {
        x[first] - x[second],
        y[first] - y[second],
        z[first] - z[second],
    };
    const double raw_distance = torsion_norm(difference);
    if (!isfinite(raw_distance)) {
        return std::numeric_limits<double>::quiet_NaN();
    }
    const double distance = raw_distance > context.config.epsilon_angstrom
                                ? raw_distance
                                : context.config.epsilon_angstrom;
    const double cutoff = context.config.internal_overlap_scale *
                          (context.ligand_radii[first] +
                           context.ligand_radii[second]);
    const double overlap = cutoff > distance ? cutoff - distance : 0.0;
    const double squared = overlap * overlap;
    return torsion_canonical_zero(squared * squared);
}

__device__ bool torsion_objective(
    const TorsionDeviceContext &context,
    const double *x,
    const double *y,
    const double *z,
    double *receptor_by_atom,
    double *internal_by_pair,
    TorsionObjective *output) {
    double receptor_total = 0.0;
    for (size_t ligand = 0; ligand < context.ligand_count; ++ligand) {
        double atom_penalty = 0.0;
        for (size_t receptor = 0; receptor < context.receptor_count;
             ++receptor) {
            const TorsionVector3 difference = {
                x[ligand] - context.receptor_x[receptor],
                y[ligand] - context.receptor_y[receptor],
                z[ligand] - context.receptor_z[receptor],
            };
            const double raw_distance = torsion_norm(difference);
            if (!isfinite(raw_distance)) {
                return false;
            }
            const double distance = raw_distance > context.config.epsilon_angstrom
                                        ? raw_distance
                                        : context.config.epsilon_angstrom;
            const double cutoff = context.config.receptor_overlap_scale *
                                  (context.ligand_radii[ligand] +
                                   context.receptor_radii[receptor]);
            const double overlap = cutoff > distance ? cutoff - distance : 0.0;
            const double squared = overlap * overlap;
            atom_penalty += squared * squared;
        }
        if (!isfinite(atom_penalty)) {
            return false;
        }
        atom_penalty = torsion_canonical_zero(atom_penalty);
        if (receptor_by_atom != nullptr) {
            receptor_by_atom[ligand] = atom_penalty;
        }
        receptor_total += atom_penalty;
    }
    double internal_total = 0.0;
    for (size_t pair = 0; pair < context.internal_pair_count; ++pair) {
        const size_t first = static_cast<size_t>(context.internal_i[pair]);
        const size_t second = static_cast<size_t>(context.internal_j[pair]);
        const double penalty =
            torsion_internal_penalty(context, x, y, z, first, second);
        if (!isfinite(penalty)) {
            return false;
        }
        if (internal_by_pair != nullptr) {
            internal_by_pair[pair] = penalty;
        }
        internal_total += penalty;
    }
    const double combined = receptor_total +
                            context.config.internal_overlap_weight *
                                internal_total;
    if (!isfinite(receptor_total) || !isfinite(internal_total) ||
        !isfinite(combined)) {
        return false;
    }
    output->receptor = torsion_canonical_zero(receptor_total);
    output->internal = torsion_canonical_zero(internal_total);
    output->combined = torsion_canonical_zero(combined);
    return true;
}

__device__ bg_docking_torsion_v7_row_v1 torsion_failure_row(
    size_t slot,
    int32_t failure) {
    bg_docking_torsion_v7_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE;
    row.failure_code = failure;
    return row;
}

__device__ bool torsion_trial_less(
    const TorsionObjective &candidate,
    size_t candidate_rotor,
    size_t candidate_sign,
    const TorsionObjective &best,
    size_t best_rotor,
    size_t best_sign) {
    if (candidate.combined != best.combined) {
        return candidate.combined < best.combined;
    }
    if (candidate.receptor != best.receptor) {
        return candidate.receptor < best.receptor;
    }
    if (candidate.internal != best.internal) {
        return candidate.internal < best.internal;
    }
    if (candidate_rotor != best_rotor) {
        return candidate_rotor < best_rotor;
    }
    return candidate_sign < best_sign;
}

__device__ void torsion_process_candidate(
    size_t slot,
    const TorsionDeviceContext &context,
    const TorsionDeviceBatch &batch,
    const TorsionDeviceOutputs &outputs,
    const TorsionScratch &scratch) {
    const size_t start = slot * context.ligand_count;
    outputs.rows[slot] = torsion_failure_row(
        slot, BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE);
    for (size_t move = 0; move < kTorsionMaxMoves; ++move) {
        bg_docking_torsion_v7_move_v1 movement{};
        movement.slot_index = static_cast<uint32_t>(slot);
        movement.move_index = static_cast<uint32_t>(move);
        outputs.moves[slot * kTorsionMaxMoves + move] = movement;
    }
    for (size_t atom = 0; atom < context.ligand_count; ++atom) {
        const size_t index = start + atom;
        outputs.optimized_x[index] = 0.0;
        outputs.optimized_y[index] = 0.0;
        outputs.optimized_z[index] = 0.0;
        outputs.optimized_angles[index] = 0.0;
        outputs.final_x[index] = 0.0;
        outputs.final_y[index] = 0.0;
        outputs.final_z[index] = 0.0;
        outputs.final_angles[index] = 0.0;
    }
    if (batch.candidate_state[slot] ==
        BG_DOCKING_TORSION_V7_CANDIDATE_INACTIVE) {
        return;
    }
    if (batch.eligible[slot] > UINT8_C(1) ||
        batch.max_steps[slot] > kTorsionMaxCallerSteps ||
        batch.baseline_steps[slot] > batch.max_steps[slot] ||
        batch.baseline_steps[slot] >
            context.config.maximum_baseline_v6_steps) {
        outputs.rows[slot] = torsion_failure_row(
            slot, BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT);
        return;
    }
    for (size_t atom = 0; atom < context.ligand_count; ++atom) {
        const size_t index = start + atom;
        if (!isfinite(batch.source_x[index]) ||
            !isfinite(batch.source_y[index]) ||
            !isfinite(batch.source_z[index]) ||
            !isfinite(batch.baseline_x[index]) ||
            !isfinite(batch.baseline_y[index]) ||
            !isfinite(batch.baseline_z[index]) ||
            !isfinite(batch.baseline_angles[index])) {
            outputs.rows[slot] = torsion_failure_row(
                slot, BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT);
            return;
        }
        scratch.current_x[index] = batch.baseline_x[index];
        scratch.current_y[index] = batch.baseline_y[index];
        scratch.current_z[index] = batch.baseline_z[index];
        scratch.current_angles[index] = batch.baseline_angles[index];
    }

    TorsionObjective source_objective{};
    TorsionObjective baseline_objective{};
    TorsionObjective current_objective{};
    double *const current_internal =
        context.internal_pair_count == 0
            ? nullptr
            : scratch.current_internal + slot * context.internal_pair_count;
    if (!torsion_objective(
            context,
            batch.source_x + start,
            batch.source_y + start,
            batch.source_z + start,
            nullptr,
            nullptr,
            &source_objective) ||
        !torsion_objective(
            context,
            batch.baseline_x + start,
            batch.baseline_y + start,
            batch.baseline_z + start,
            scratch.current_receptor + start,
            current_internal,
            &baseline_objective)) {
        outputs.rows[slot] = torsion_failure_row(
            slot,
            BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE);
        return;
    }
    current_objective = baseline_objective;

    const size_t remaining_steps =
        static_cast<size_t>(batch.max_steps[slot] - batch.baseline_steps[slot]);
    const size_t torsion_step_budget =
        remaining_steps < context.config.maximum_torsion_steps
            ? remaining_steps
            : context.config.maximum_torsion_steps;
    const double reachable_bound =
        baseline_objective.receptor +
        static_cast<double>(torsion_step_budget) *
            context.config.penalty_tolerance;
    if (!isfinite(reachable_bound)) {
        outputs.rows[slot] = torsion_failure_row(
            slot,
            BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE);
        return;
    }
    const bool selection_window_reachable =
        reachable_bound >=
        context.config.minimum_selected_final_receptor_penalty;
    int32_t skip_reason = BG_DOCKING_TORSION_V7_SKIP_NONE;
    if (batch.eligible[slot] == UINT8_C(0)) {
        skip_reason = BG_DOCKING_TORSION_V7_SKIP_NOT_ELIGIBLE;
    } else if (context.rotor_count == 0) {
        skip_reason = BG_DOCKING_TORSION_V7_SKIP_NO_AUTHORITY_ROTOR;
    } else if (torsion_step_budget == 0) {
        skip_reason = BG_DOCKING_TORSION_V7_SKIP_NO_REMAINING_STEP_BUDGET;
    } else if (current_objective.combined <=
               context.config.penalty_tolerance) {
        skip_reason =
            BG_DOCKING_TORSION_V7_SKIP_OBJECTIVE_AT_OR_BELOW_TOLERANCE;
    } else if (!selection_window_reachable) {
        skip_reason =
            BG_DOCKING_TORSION_V7_SKIP_SELECTION_WINDOW_UNREACHABLE;
    }
    const bool torsion_evaluated =
        skip_reason == BG_DOCKING_TORSION_V7_SKIP_NONE;
    bool stopped_after_window_unreachable = false;
    size_t evaluated_move_count = 0;
    size_t trial_evaluation_count = 0;
    double total_path = 0.0;

    for (size_t iteration = 0;
         torsion_evaluated && iteration < torsion_step_budget;
         ++iteration) {
        double priorities[kTorsionMaxAuthorityRotors]{};
        size_t positions[kTorsionMaxAuthorityRotors]{};
        const size_t priority_count =
            context.rotor_count < context.config.maximum_torsions_evaluated
                ? context.rotor_count
                : context.config.maximum_torsions_evaluated;
        for (size_t position = 0; position < context.rotor_count; ++position) {
            const size_t rotor = static_cast<size_t>(context.rotors[position]);
            double receptor = 0.0;
            for (size_t atom = 0; atom < context.ligand_count; ++atom) {
                if (torsion_is_descendant(atom, rotor, context)) {
                    receptor += scratch.current_receptor[start + atom];
                }
            }
            double internal = 0.0;
            for (size_t pair = 0; pair < context.internal_pair_count; ++pair) {
                const size_t first =
                    static_cast<size_t>(context.internal_i[pair]);
                const size_t second =
                    static_cast<size_t>(context.internal_j[pair]);
                if (torsion_is_descendant(first, rotor, context) !=
                    torsion_is_descendant(second, rotor, context)) {
                    internal += scratch.current_internal[
                        slot * context.internal_pair_count + pair];
                }
            }
            priorities[position] = torsion_canonical_zero(
                receptor + context.config.internal_overlap_weight * internal);
            positions[position] = position;
        }
        for (size_t left = 0; left < context.rotor_count; ++left) {
            for (size_t right = left + 1; right < context.rotor_count;
                 ++right) {
                const size_t left_atom =
                    static_cast<size_t>(context.rotors[positions[left]]);
                const size_t right_atom =
                    static_cast<size_t>(context.rotors[positions[right]]);
                if (priorities[positions[right]] > priorities[positions[left]] ||
                    (priorities[positions[right]] ==
                         priorities[positions[left]] &&
                     right_atom < left_atom)) {
                    const size_t temporary = positions[left];
                    positions[left] = positions[right];
                    positions[right] = temporary;
                }
            }
        }

        bool have_best = false;
        TorsionObjective best_objective{};
        size_t best_rotor_atom = 0;
        size_t best_sign = 0;
        double best_delta = 0.0;
        double step = context.config.maximum_torsion_step_radians;
        for (size_t backtrack = 0;
             backtrack < context.config.maximum_backtracking_evaluations;
             ++backtrack) {
            if (step + context.config.penalty_tolerance <
                context.config.minimum_torsion_step_radians) {
                break;
            }
            if (total_path + step >
                context.config.maximum_total_torsion_path_radians +
                    context.config.penalty_tolerance) {
                step *= 0.5;
                continue;
            }
            for (size_t priority = 0; priority < priority_count; ++priority) {
                const size_t rotor_position = positions[priority];
                const size_t rotor_atom =
                    static_cast<size_t>(context.rotors[rotor_position]);
                const int32_t parent_value = context.parents[rotor_atom];
                if (parent_value < 0) {
                    outputs.rows[slot] = torsion_failure_row(
                        slot, BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT);
                    return;
                }
                const size_t parent = static_cast<size_t>(parent_value);
                const TorsionVector3 origin = {
                    scratch.current_x[start + parent],
                    scratch.current_y[start + parent],
                    scratch.current_z[start + parent],
                };
                const TorsionVector3 axis_vector = {
                    scratch.current_x[start + rotor_atom] - origin.x,
                    scratch.current_y[start + rotor_atom] - origin.y,
                    scratch.current_z[start + rotor_atom] - origin.z,
                };
                const double axis_norm = torsion_norm(axis_vector);
                if (!isfinite(axis_norm) ||
                    axis_norm <= context.config.epsilon_angstrom) {
                    outputs.rows[slot] = torsion_failure_row(
                        slot,
                        BG_DOCKING_TORSION_V7_FAILURE_DEGENERATE_ROTOR);
                    return;
                }
                const TorsionVector3 axis =
                    torsion_scale(axis_vector, 1.0 / axis_norm);
                for (size_t sign_order = 0; sign_order < 2; ++sign_order) {
                    const double delta =
                        (sign_order == 0 ? -1.0 : 1.0) * step;
                    const double cosine = cos(delta);
                    const double sine = sin(delta);
                    TorsionVector3 centroid{};
                    for (size_t atom = 0; atom < context.ligand_count;
                         ++atom) {
                        TorsionVector3 coordinate = {
                            scratch.current_x[start + atom],
                            scratch.current_y[start + atom],
                            scratch.current_z[start + atom],
                        };
                        if (torsion_is_descendant(atom, rotor_atom, context)) {
                            const TorsionVector3 vector =
                                torsion_minus(coordinate, origin);
                            coordinate = torsion_plus(
                                torsion_plus(
                                    torsion_scale(vector, cosine),
                                    torsion_scale(
                                        torsion_cross(axis, vector), sine)),
                                torsion_plus(
                                    torsion_scale(
                                        axis,
                                        torsion_dot(axis, vector) *
                                            (1.0 - cosine)),
                                    origin));
                            if (!torsion_finite(coordinate)) {
                                outputs.rows[slot] = torsion_failure_row(
                                    slot,
                                    BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE);
                                return;
                            }
                            coordinate.x =
                                torsion_canonical_zero(coordinate.x);
                            coordinate.y =
                                torsion_canonical_zero(coordinate.y);
                            coordinate.z =
                                torsion_canonical_zero(coordinate.z);
                        }
                        scratch.trial_x[start + atom] = coordinate.x;
                        scratch.trial_y[start + atom] = coordinate.y;
                        scratch.trial_z[start + atom] = coordinate.z;
                        centroid = torsion_plus(centroid, coordinate);
                    }
                    centroid = torsion_scale(
                        centroid, 1.0 / static_cast<double>(context.ligand_count));
                    centroid.x = torsion_canonical_zero(centroid.x);
                    centroid.y = torsion_canonical_zero(centroid.y);
                    centroid.z = torsion_canonical_zero(centroid.z);
                    const TorsionVector3 pocket = {
                        context.pocket_center[0],
                        context.pocket_center[1],
                        context.pocket_center[2],
                    };
                    const double centroid_offset =
                        torsion_norm(torsion_minus(centroid, pocket));
                    if (!isfinite(centroid_offset)) {
                        outputs.rows[slot] = torsion_failure_row(
                            slot,
                            BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE);
                        return;
                    }
                    if (centroid_offset >
                        context.config.maximum_centroid_offset_angstrom +
                            context.config.penalty_tolerance) {
                        continue;
                    }
                    TorsionObjective trial_objective{};
                    double *const trial_internal =
                        context.internal_pair_count == 0
                            ? nullptr
                            : scratch.trial_internal +
                                  slot * context.internal_pair_count;
                    if (!torsion_objective(
                            context,
                            scratch.trial_x + start,
                            scratch.trial_y + start,
                            scratch.trial_z + start,
                            scratch.trial_receptor + start,
                            trial_internal,
                            &trial_objective)) {
                        outputs.rows[slot] = torsion_failure_row(
                            slot,
                            BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE);
                        return;
                    }
                    ++trial_evaluation_count;
                    if (trial_objective.receptor >
                            current_objective.receptor +
                                context.config.penalty_tolerance ||
                        trial_objective.combined >=
                            current_objective.combined -
                                context.config.penalty_tolerance) {
                        continue;
                    }
                    if (!have_best ||
                        torsion_trial_less(
                            trial_objective,
                            rotor_atom,
                            sign_order,
                            best_objective,
                            best_rotor_atom,
                            best_sign)) {
                        have_best = true;
                        best_objective = trial_objective;
                        best_rotor_atom = rotor_atom;
                        best_sign = sign_order;
                        best_delta = delta;
                        for (size_t atom = 0; atom < context.ligand_count;
                             ++atom) {
                            scratch.best_x[start + atom] =
                                scratch.trial_x[start + atom];
                            scratch.best_y[start + atom] =
                                scratch.trial_y[start + atom];
                            scratch.best_z[start + atom] =
                                scratch.trial_z[start + atom];
                            scratch.best_receptor[start + atom] =
                                scratch.trial_receptor[start + atom];
                        }
                        for (size_t pair = 0;
                             pair < context.internal_pair_count;
                             ++pair) {
                            const size_t pair_index =
                                slot * context.internal_pair_count + pair;
                            scratch.best_internal[pair_index] =
                                scratch.trial_internal[pair_index];
                        }
                    }
                }
            }
            if (have_best) {
                break;
            }
            step *= 0.5;
        }
        if (!have_best) {
            break;
        }
        total_path += fabs(best_delta);
        if (!isfinite(total_path)) {
            outputs.rows[slot] = torsion_failure_row(
                slot,
                BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE);
            return;
        }
        bg_docking_torsion_v7_move_v1 movement{};
        movement.slot_index = static_cast<uint32_t>(slot);
        movement.move_index = static_cast<uint32_t>(evaluated_move_count);
        movement.evaluated = UINT8_C(1);
        movement.rotatable_child_atom_index = best_rotor_atom;
        movement.delta_radians = torsion_canonical_zero(best_delta);
        movement.receptor_penalty = best_objective.receptor;
        movement.internal_penalty = best_objective.internal;
        movement.combined_penalty = best_objective.combined;
        outputs.moves[slot * kTorsionMaxMoves + evaluated_move_count] =
            movement;
        ++evaluated_move_count;
        for (size_t atom = 0; atom < context.ligand_count; ++atom) {
            scratch.current_x[start + atom] = scratch.best_x[start + atom];
            scratch.current_y[start + atom] = scratch.best_y[start + atom];
            scratch.current_z[start + atom] = scratch.best_z[start + atom];
            scratch.current_receptor[start + atom] =
                scratch.best_receptor[start + atom];
        }
        for (size_t pair = 0; pair < context.internal_pair_count; ++pair) {
            const size_t pair_index =
                slot * context.internal_pair_count + pair;
            scratch.current_internal[pair_index] =
                scratch.best_internal[pair_index];
        }
        scratch.current_angles[start + best_rotor_atom] =
            torsion_canonical_zero(atan2(
                sin(scratch.current_angles[start + best_rotor_atom] + best_delta),
                cos(scratch.current_angles[start + best_rotor_atom] + best_delta)));
        current_objective = best_objective;
        const size_t remaining_torsion_steps =
            torsion_step_budget - evaluated_move_count;
        const double remaining_reachable_bound =
            current_objective.receptor +
            static_cast<double>(remaining_torsion_steps) *
                context.config.penalty_tolerance;
        if (!isfinite(remaining_reachable_bound)) {
            outputs.rows[slot] = torsion_failure_row(
                slot,
                BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE);
            return;
        }
        if (remaining_reachable_bound <
            context.config.minimum_selected_final_receptor_penalty) {
            stopped_after_window_unreachable = true;
            break;
        }
    }

    const bool variant_available = evaluated_move_count != 0;
    const bool selected =
        variant_available &&
        context.config.minimum_selected_final_receptor_penalty <=
            current_objective.receptor &&
        current_objective.receptor <
            context.config.maximum_selected_final_receptor_penalty;
    for (size_t move = 0; move < evaluated_move_count; ++move) {
        outputs.moves[slot * kTorsionMaxMoves + move].selected =
            static_cast<uint8_t>(selected);
    }
    for (size_t atom = 0; atom < context.ligand_count; ++atom) {
        const size_t index = start + atom;
        outputs.optimized_x[index] = scratch.current_x[index];
        outputs.optimized_y[index] = scratch.current_y[index];
        outputs.optimized_z[index] = scratch.current_z[index];
        outputs.optimized_angles[index] = scratch.current_angles[index];
        outputs.final_x[index] =
            selected ? scratch.current_x[index] : batch.baseline_x[index];
        outputs.final_y[index] =
            selected ? scratch.current_y[index] : batch.baseline_y[index];
        outputs.final_z[index] =
            selected ? scratch.current_z[index] : batch.baseline_z[index];
        outputs.final_angles[index] = selected
                                            ? scratch.current_angles[index]
                                            : batch.baseline_angles[index];
    }

    bg_docking_torsion_v7_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_TORSION_V7_ROW_REFINED;
    row.failure_code = BG_DOCKING_TORSION_V7_FAILURE_NONE;
    row.skip_reason = skip_reason;
    row.selection_reason =
        selected
            ? BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW
            : (variant_available
                   ? BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_OUTSIDE_WINDOW
                   : BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_NO_REDUCTION);
    row.selection_window_reachable =
        static_cast<uint8_t>(selection_window_reachable);
    row.evaluation_stopped_after_selection_window_became_unreachable =
        static_cast<uint8_t>(stopped_after_window_unreachable);
    row.torsion_evaluated = static_cast<uint8_t>(torsion_evaluated);
    row.torsion_variant_available = static_cast<uint8_t>(variant_available);
    row.torsion_selected = static_cast<uint8_t>(selected);
    row.torsion_step_budget = torsion_step_budget;
    row.fixed_objective_evaluation_count = UINT64_C(2);
    row.torsion_trial_objective_evaluation_count = trial_evaluation_count;
    row.evaluated_torsion_steps = evaluated_move_count;
    row.accepted_torsion_steps = selected ? evaluated_move_count : 0;
    row.baseline_v6_accepted_steps = batch.baseline_steps[slot];
    row.source_receptor_penalty = source_objective.receptor;
    row.source_internal_penalty = source_objective.internal;
    row.source_combined_penalty = source_objective.combined;
    row.baseline_receptor_penalty = baseline_objective.receptor;
    row.baseline_internal_penalty = baseline_objective.internal;
    row.baseline_combined_penalty = baseline_objective.combined;
    row.optimized_receptor_penalty = current_objective.receptor;
    row.optimized_internal_penalty = current_objective.internal;
    row.optimized_combined_penalty = current_objective.combined;
    row.final_receptor_penalty =
        selected ? current_objective.receptor : baseline_objective.receptor;
    row.final_internal_penalty =
        selected ? current_objective.internal : baseline_objective.internal;
    row.final_combined_penalty =
        selected ? current_objective.combined : baseline_objective.combined;
    row.evaluated_total_torsion_path_radians =
        torsion_canonical_zero(total_path);
    row.accepted_total_torsion_path_radians =
        selected ? torsion_canonical_zero(total_path) : 0.0;
    outputs.rows[slot] = row;
}

__global__ void torsion_fixed64_kernel(
    TorsionDeviceContext context,
    TorsionDeviceBatch batch,
    TorsionDeviceOutputs outputs,
    TorsionScratch scratch) {
    const size_t slot = static_cast<size_t>(blockIdx.x) * blockDim.x +
                        threadIdx.x;
    if (slot < kTorsionCandidateCount) {
        torsion_process_candidate(slot, context, batch, outputs, scratch);
    }
}

bool torsion_valid_config(const bg_docking_torsion_v7_context_soa_v1 &value) {
    const double positive[] = {
        value.receptor_overlap_scale,
        value.internal_overlap_scale,
        value.internal_overlap_weight,
        value.maximum_torsion_step_radians,
        value.minimum_torsion_step_radians,
        value.maximum_total_torsion_path_radians,
        value.maximum_centroid_offset_angstrom,
        value.penalty_tolerance,
        value.epsilon_angstrom,
    };
    for (const double number : positive) {
        if (!std::isfinite(number) || number <= 0.0) {
            return false;
        }
    }
    return value.receptor_overlap_scale >= 0.55 &&
           value.receptor_overlap_scale <= 1.0 &&
           value.internal_overlap_scale >= 0.55 &&
           value.internal_overlap_scale <= 1.0 &&
           value.minimum_torsion_step_radians <=
               value.maximum_torsion_step_radians &&
           value.maximum_torsion_step_radians <=
               value.maximum_total_torsion_path_radians &&
           value.maximum_total_torsion_path_radians <= kTorsionPi &&
           value.maximum_baseline_v6_steps >= 1 &&
           value.maximum_baseline_v6_steps <= 64 &&
           value.maximum_torsions_evaluated >= 1 &&
           value.maximum_torsions_evaluated <= kTorsionMaxEvaluatedRotors &&
           value.maximum_torsion_steps >= 1 &&
           value.maximum_torsion_steps <= kTorsionMaxMoves &&
           value.maximum_backtracking_evaluations >= 1 &&
           value.maximum_backtracking_evaluations <= 8 &&
           value.maximum_centroid_offset_angstrom >= 0.5 &&
           value.maximum_centroid_offset_angstrom <= 8.0 &&
           std::isfinite(value.minimum_selected_final_receptor_penalty) &&
           std::isfinite(value.maximum_selected_final_receptor_penalty) &&
           value.minimum_selected_final_receptor_penalty >= 0.0 &&
           value.minimum_selected_final_receptor_penalty <
               value.maximum_selected_final_receptor_penalty;
}

int32_t torsion_backend_is_available(
    int32_t device_ordinal,
    uint8_t *available,
    char *error_message,
    size_t error_capacity) noexcept {
    if (available == nullptr || device_ordinal < 0) {
        return torsion_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 availability arguments are invalid");
    }
    *available = UINT8_C(0);
    int device_count = 0;
    const hipError_t count_status = hipGetDeviceCount(&device_count);
    if (count_status == hipErrorNoDevice) {
        static_cast<void>(hipGetLastError());
        return BG_STATUS_OK;
    }
    if (count_status != hipSuccess) {
        return torsion_fail_hip(
            count_status,
            error_message,
            error_capacity,
            "torsion V7 device count query");
    }
    if (device_ordinal >= device_count) {
        return BG_STATUS_OK;
    }
    hipDeviceProp_t properties{};
    const hipError_t property_status =
        hipGetDeviceProperties(&properties, device_ordinal);
    if (property_status != hipSuccess) {
        return torsion_fail_hip(
            property_status,
            error_message,
            error_capacity,
            "torsion V7 device property query");
    }
    if (properties.arch.hasDoubles == 0U) {
        return BG_STATUS_OK;
    }
    TorsionDeviceGuard guard;
    const hipError_t set_status = hipSetDevice(device_ordinal);
    if (set_status != hipSuccess) {
        return torsion_fail_hip(
            set_status,
            error_message,
            error_capacity,
            "torsion V7 availability device selection");
    }
    hipFuncAttributes attributes{};
    const hipError_t probe_status = hipFuncGetAttributes(
        &attributes,
        reinterpret_cast<const void *>(torsion_fixed64_kernel));
    const bool incompatible = probe_status == hipErrorNoBinaryForGpu ||
                              probe_status == hipErrorInvalidDeviceFunction ||
                              probe_status == hipErrorInvalidKernelFile;
    if (incompatible) {
        static_cast<void>(hipGetLastError());
        return BG_STATUS_OK;
    }
    if (probe_status != hipSuccess) {
        return torsion_fail_hip(
            probe_status,
            error_message,
            error_capacity,
            "torsion V7 code-object probe");
    }
    *available = UINT8_C(1);
    return BG_STATUS_OK;
}

int32_t torsion_validate_create(
    int32_t device_ordinal,
    const bg_docking_torsion_v7_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity) noexcept {
    if (descriptor == nullptr || out_state == nullptr || device_ordinal < 0) {
        return torsion_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 create arguments are invalid");
    }
    *out_state = nullptr;
    if (descriptor->struct_size != sizeof(*descriptor) ||
        descriptor->abi_version != BG_ABI_VERSION) {
        return torsion_fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 descriptor ABI mismatch");
    }
    if (descriptor->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        descriptor->reserved0 != 0 ||
        !torsion_reserved_is_zero(descriptor->reserved) ||
        descriptor->receptor_atom_count == 0 ||
        descriptor->receptor_atom_count > kTorsionMaxReceptorAtoms ||
        descriptor->ligand_atom_count == 0 ||
        descriptor->ligand_atom_count > kTorsionMaxLigandAtoms ||
        descriptor->rotor_count > descriptor->ligand_atom_count ||
        !torsion_valid_config(*descriptor)) {
        return torsion_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 descriptor identity is invalid");
    }
    const size_t receptor_count =
        static_cast<size_t>(descriptor->receptor_atom_count);
    const size_t ligand_count =
        static_cast<size_t>(descriptor->ligand_atom_count);
    const size_t rotor_count = static_cast<size_t>(descriptor->rotor_count);
    const size_t pair_count =
        static_cast<size_t>(descriptor->internal_pair_count);
    const size_t maximum_internal_pairs =
        ligand_count * (ligand_count - 1) / 2;
    if (pair_count > maximum_internal_pairs) {
        return torsion_fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 pair denominator exceeds canonical maximum");
    }
    if (!torsion_pointer_valid(
            descriptor->receptor_x_angstrom, receptor_count) ||
        !torsion_pointer_valid(
            descriptor->receptor_y_angstrom, receptor_count) ||
        !torsion_pointer_valid(
            descriptor->receptor_z_angstrom, receptor_count) ||
        !torsion_pointer_valid(
            descriptor->receptor_vdw_radius_angstrom, receptor_count) ||
        !torsion_pointer_valid(
            descriptor->ligand_vdw_radius_angstrom, ligand_count) ||
        !torsion_pointer_valid(descriptor->parent_atom_index, ligand_count) ||
        !torsion_pointer_valid(
            descriptor->rotatable_child_atom_index, rotor_count) ||
        !torsion_pointer_valid(
            descriptor->internal_pair_atom_i, pair_count) ||
        !torsion_pointer_valid(
            descriptor->internal_pair_atom_j, pair_count)) {
        return torsion_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 descriptor channels are invalid");
    }
    return BG_STATUS_OK;
}

}  // namespace

extern "C" int32_t BG_DOCKING_TORSION_V7_CREATE(
    int32_t device_ordinal,
    const bg_docking_torsion_v7_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity) {
    torsion_clear_error(error_message, error_capacity);
    const int32_t validation_status = torsion_validate_create(
        device_ordinal,
        descriptor,
        out_state,
        error_message,
        error_capacity);
    if (validation_status != BG_STATUS_OK) {
        return validation_status;
    }
    uint8_t available = UINT8_C(0);
    const int32_t availability_status = torsion_backend_is_available(
        device_ordinal, &available, error_message, error_capacity);
    if (availability_status != BG_STATUS_OK) {
        return availability_status;
    }
    if (available == UINT8_C(0)) {
        return torsion_fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 device ordinal is unavailable");
    }
    TorsionDeviceGuard guard;
    const hipError_t set_status = hipSetDevice(device_ordinal);
    if (set_status != hipSuccess) {
        return torsion_fail_hip(
            set_status,
            error_message,
            error_capacity,
            "torsion V7 device selection");
    }
    std::unique_ptr<TorsionState> state(new (std::nothrow) TorsionState());
    if (state == nullptr) {
        return torsion_fail(
            BG_STATUS_OUT_OF_MEMORY,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 host state allocation failed");
    }
    state->device_ordinal = device_ordinal;
    state->receptor_count =
        static_cast<size_t>(descriptor->receptor_atom_count);
    state->ligand_count = static_cast<size_t>(descriptor->ligand_atom_count);
    state->rotor_count = static_cast<size_t>(descriptor->rotor_count);
    state->internal_pair_count =
        static_cast<size_t>(descriptor->internal_pair_count);
    std::copy(
        std::begin(descriptor->pocket_center_angstrom),
        std::end(descriptor->pocket_center_angstrom),
        std::begin(state->pocket_center));
    state->config = {
        descriptor->receptor_overlap_scale,
        descriptor->internal_overlap_scale,
        descriptor->internal_overlap_weight,
        static_cast<size_t>(descriptor->maximum_baseline_v6_steps),
        static_cast<size_t>(descriptor->maximum_torsions_evaluated),
        static_cast<size_t>(descriptor->maximum_torsion_steps),
        static_cast<size_t>(descriptor->maximum_backtracking_evaluations),
        descriptor->maximum_torsion_step_radians,
        descriptor->minimum_torsion_step_radians,
        descriptor->maximum_total_torsion_path_radians,
        descriptor->maximum_centroid_offset_angstrom,
        descriptor->minimum_selected_final_receptor_penalty,
        descriptor->maximum_selected_final_receptor_penalty,
        descriptor->penalty_tolerance,
        descriptor->epsilon_angstrom,
    };

#define BG_HIP_TORSION_CONTEXT_COPY(buffer, source, count, operation)       \
    do {                                                                   \
        const hipError_t copy_status = (buffer).copy_from((source), (count)); \
        if (copy_status != hipSuccess) {                                   \
            return torsion_fail_hip(                                       \
                copy_status, error_message, error_capacity, (operation));  \
        }                                                                  \
    } while (false)
    BG_HIP_TORSION_CONTEXT_COPY(
        state->receptor_x,
        descriptor->receptor_x_angstrom,
        state->receptor_count,
        "torsion V7 receptor x copy");
    BG_HIP_TORSION_CONTEXT_COPY(
        state->receptor_y,
        descriptor->receptor_y_angstrom,
        state->receptor_count,
        "torsion V7 receptor y copy");
    BG_HIP_TORSION_CONTEXT_COPY(
        state->receptor_z,
        descriptor->receptor_z_angstrom,
        state->receptor_count,
        "torsion V7 receptor z copy");
    BG_HIP_TORSION_CONTEXT_COPY(
        state->receptor_radii,
        descriptor->receptor_vdw_radius_angstrom,
        state->receptor_count,
        "torsion V7 receptor radii copy");
    BG_HIP_TORSION_CONTEXT_COPY(
        state->ligand_radii,
        descriptor->ligand_vdw_radius_angstrom,
        state->ligand_count,
        "torsion V7 ligand radii copy");
    BG_HIP_TORSION_CONTEXT_COPY(
        state->parents,
        descriptor->parent_atom_index,
        state->ligand_count,
        "torsion V7 parent copy");
    BG_HIP_TORSION_CONTEXT_COPY(
        state->rotors,
        descriptor->rotatable_child_atom_index,
        state->rotor_count,
        "torsion V7 rotor copy");
    BG_HIP_TORSION_CONTEXT_COPY(
        state->internal_i,
        descriptor->internal_pair_atom_i,
        state->internal_pair_count,
        "torsion V7 pair-i copy");
    BG_HIP_TORSION_CONTEXT_COPY(
        state->internal_j,
        descriptor->internal_pair_atom_j,
        state->internal_pair_count,
        "torsion V7 pair-j copy");
#undef BG_HIP_TORSION_CONTEXT_COPY

    *out_state = state.release();
    return BG_STATUS_OK;
}

extern "C" void BG_DOCKING_TORSION_V7_DESTROY(void *raw_state) {
    auto *state = static_cast<TorsionState *>(raw_state);
    if (state == nullptr) {
        return;
    }
    TorsionDeviceGuard guard;
    static_cast<void>(hipSetDevice(state->device_ordinal));
    delete state;
}

extern "C" int32_t BG_DOCKING_TORSION_V7_REFINE_FIXED64(
    const void *raw_state,
    const bg_docking_torsion_v7_candidate_batch_soa_v1 *candidates,
    bg_docking_torsion_v7_row_v1 *out_rows,
    bg_docking_torsion_v7_move_v1 *out_moves,
    double *out_optimized_x_angstrom,
    double *out_optimized_y_angstrom,
    double *out_optimized_z_angstrom,
    double *out_optimized_torsion_angles_radians,
    double *out_final_x_angstrom,
    double *out_final_y_angstrom,
    double *out_final_z_angstrom,
    double *out_final_torsion_angles_radians,
    char *error_message,
    size_t error_capacity) {
    torsion_clear_error(error_message, error_capacity);
    const auto *state = static_cast<const TorsionState *>(raw_state);
    if (state == nullptr || candidates == nullptr || out_rows == nullptr ||
        out_moves == nullptr || out_optimized_x_angstrom == nullptr ||
        out_optimized_y_angstrom == nullptr ||
        out_optimized_z_angstrom == nullptr ||
        out_optimized_torsion_angles_radians == nullptr ||
        out_final_x_angstrom == nullptr || out_final_y_angstrom == nullptr ||
        out_final_z_angstrom == nullptr ||
        out_final_torsion_angles_radians == nullptr) {
        return torsion_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 refine pointer is null");
    }
    if (candidates->struct_size != sizeof(*candidates) ||
        candidates->abi_version != BG_ABI_VERSION) {
        return torsion_fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE " torsion V7 batch ABI mismatch");
    }
    if (candidates->candidate_count != kTorsionCandidateCount ||
        candidates->ligand_atom_count != state->ligand_count ||
        candidates->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        candidates->reserved0 != 0 ||
        !torsion_reserved_is_zero(candidates->reserved)) {
        return torsion_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 batch identity is invalid");
    }
    const size_t coordinate_count =
        kTorsionCandidateCount * state->ligand_count;
    const bool channels_valid =
        torsion_pointer_valid(
            candidates->candidate_state, kTorsionCandidateCount) &&
        torsion_pointer_valid(
            candidates->proposal_is_torsion_eligible,
            kTorsionCandidateCount) &&
        torsion_pointer_valid(candidates->max_steps, kTorsionCandidateCount) &&
        torsion_pointer_valid(
            candidates->baseline_v6_accepted_steps,
            kTorsionCandidateCount) &&
        torsion_pointer_valid(candidates->source_x_angstrom, coordinate_count) &&
        torsion_pointer_valid(candidates->source_y_angstrom, coordinate_count) &&
        torsion_pointer_valid(candidates->source_z_angstrom, coordinate_count) &&
        torsion_pointer_valid(
            candidates->baseline_v6_x_angstrom, coordinate_count) &&
        torsion_pointer_valid(
            candidates->baseline_v6_y_angstrom, coordinate_count) &&
        torsion_pointer_valid(
            candidates->baseline_v6_z_angstrom, coordinate_count) &&
        torsion_pointer_valid(
            candidates->baseline_v6_torsion_angles_radians,
            coordinate_count);
    if (!channels_valid) {
        return torsion_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_TORSION_V7_LANE
            " torsion V7 batch channels are invalid");
    }

    TorsionDeviceGuard guard;
    const hipError_t set_status = hipSetDevice(state->device_ordinal);
    if (set_status != hipSuccess) {
        return torsion_fail_hip(
            set_status,
            error_message,
            error_capacity,
            "torsion V7 device selection");
    }

    TorsionDeviceBuffer<int32_t> candidate_state;
    TorsionDeviceBuffer<uint8_t> eligible;
    TorsionDeviceBuffer<uint64_t> max_steps;
    TorsionDeviceBuffer<uint64_t> baseline_steps;
    TorsionDeviceBuffer<double> source_x;
    TorsionDeviceBuffer<double> source_y;
    TorsionDeviceBuffer<double> source_z;
    TorsionDeviceBuffer<double> baseline_x;
    TorsionDeviceBuffer<double> baseline_y;
    TorsionDeviceBuffer<double> baseline_z;
    TorsionDeviceBuffer<double> baseline_angles;
    TorsionDeviceBuffer<bg_docking_torsion_v7_row_v1> rows;
    TorsionDeviceBuffer<bg_docking_torsion_v7_move_v1> moves;
    TorsionDeviceBuffer<double> optimized_x;
    TorsionDeviceBuffer<double> optimized_y;
    TorsionDeviceBuffer<double> optimized_z;
    TorsionDeviceBuffer<double> optimized_angles;
    TorsionDeviceBuffer<double> final_x;
    TorsionDeviceBuffer<double> final_y;
    TorsionDeviceBuffer<double> final_z;
    TorsionDeviceBuffer<double> final_angles;
    TorsionDeviceBuffer<double> current_x;
    TorsionDeviceBuffer<double> current_y;
    TorsionDeviceBuffer<double> current_z;
    TorsionDeviceBuffer<double> current_angles;
    TorsionDeviceBuffer<double> trial_x;
    TorsionDeviceBuffer<double> trial_y;
    TorsionDeviceBuffer<double> trial_z;
    TorsionDeviceBuffer<double> best_x;
    TorsionDeviceBuffer<double> best_y;
    TorsionDeviceBuffer<double> best_z;
    TorsionDeviceBuffer<double> current_receptor;
    TorsionDeviceBuffer<double> trial_receptor;
    TorsionDeviceBuffer<double> best_receptor;
    TorsionDeviceBuffer<double> current_internal;
    TorsionDeviceBuffer<double> trial_internal;
    TorsionDeviceBuffer<double> best_internal;

#define BG_HIP_TORSION_COPY(buffer, source, count, operation)              \
    do {                                                                   \
        const hipError_t copy_status = (buffer).copy_from((source), (count)); \
        if (copy_status != hipSuccess) {                                   \
            return torsion_fail_hip(                                       \
                copy_status, error_message, error_capacity, (operation));  \
        }                                                                  \
    } while (false)
#define BG_HIP_TORSION_ALLOCATE(buffer, count, operation)                  \
    do {                                                                   \
        const hipError_t allocation_status = (buffer).allocate((count));   \
        if (allocation_status != hipSuccess) {                             \
            return torsion_fail_hip(                                       \
                allocation_status,                                        \
                error_message,                                             \
                error_capacity,                                            \
                (operation));                                              \
        }                                                                  \
    } while (false)
    BG_HIP_TORSION_COPY(
        candidate_state,
        candidates->candidate_state,
        kTorsionCandidateCount,
        "torsion V7 candidate-state copy");
    BG_HIP_TORSION_COPY(
        eligible,
        candidates->proposal_is_torsion_eligible,
        kTorsionCandidateCount,
        "torsion V7 eligibility copy");
    BG_HIP_TORSION_COPY(
        max_steps,
        candidates->max_steps,
        kTorsionCandidateCount,
        "torsion V7 max-step copy");
    BG_HIP_TORSION_COPY(
        baseline_steps,
        candidates->baseline_v6_accepted_steps,
        kTorsionCandidateCount,
        "torsion V7 baseline-step copy");
    BG_HIP_TORSION_COPY(
        source_x,
        candidates->source_x_angstrom,
        coordinate_count,
        "torsion V7 source-x copy");
    BG_HIP_TORSION_COPY(
        source_y,
        candidates->source_y_angstrom,
        coordinate_count,
        "torsion V7 source-y copy");
    BG_HIP_TORSION_COPY(
        source_z,
        candidates->source_z_angstrom,
        coordinate_count,
        "torsion V7 source-z copy");
    BG_HIP_TORSION_COPY(
        baseline_x,
        candidates->baseline_v6_x_angstrom,
        coordinate_count,
        "torsion V7 baseline-x copy");
    BG_HIP_TORSION_COPY(
        baseline_y,
        candidates->baseline_v6_y_angstrom,
        coordinate_count,
        "torsion V7 baseline-y copy");
    BG_HIP_TORSION_COPY(
        baseline_z,
        candidates->baseline_v6_z_angstrom,
        coordinate_count,
        "torsion V7 baseline-z copy");
    BG_HIP_TORSION_COPY(
        baseline_angles,
        candidates->baseline_v6_torsion_angles_radians,
        coordinate_count,
        "torsion V7 baseline-angle copy");
    BG_HIP_TORSION_ALLOCATE(rows, kTorsionCandidateCount, "torsion V7 rows");
    BG_HIP_TORSION_ALLOCATE(
        moves,
        kTorsionCandidateCount * kTorsionMaxMoves,
        "torsion V7 moves");
    BG_HIP_TORSION_ALLOCATE(optimized_x, coordinate_count, "torsion V7 optimized x");
    BG_HIP_TORSION_ALLOCATE(optimized_y, coordinate_count, "torsion V7 optimized y");
    BG_HIP_TORSION_ALLOCATE(optimized_z, coordinate_count, "torsion V7 optimized z");
    BG_HIP_TORSION_ALLOCATE(
        optimized_angles, coordinate_count, "torsion V7 optimized angles");
    BG_HIP_TORSION_ALLOCATE(final_x, coordinate_count, "torsion V7 final x");
    BG_HIP_TORSION_ALLOCATE(final_y, coordinate_count, "torsion V7 final y");
    BG_HIP_TORSION_ALLOCATE(final_z, coordinate_count, "torsion V7 final z");
    BG_HIP_TORSION_ALLOCATE(
        final_angles, coordinate_count, "torsion V7 final angles");
    BG_HIP_TORSION_ALLOCATE(current_x, coordinate_count, "torsion V7 current x");
    BG_HIP_TORSION_ALLOCATE(current_y, coordinate_count, "torsion V7 current y");
    BG_HIP_TORSION_ALLOCATE(current_z, coordinate_count, "torsion V7 current z");
    BG_HIP_TORSION_ALLOCATE(
        current_angles, coordinate_count, "torsion V7 current angles");
    BG_HIP_TORSION_ALLOCATE(trial_x, coordinate_count, "torsion V7 trial x");
    BG_HIP_TORSION_ALLOCATE(trial_y, coordinate_count, "torsion V7 trial y");
    BG_HIP_TORSION_ALLOCATE(trial_z, coordinate_count, "torsion V7 trial z");
    BG_HIP_TORSION_ALLOCATE(best_x, coordinate_count, "torsion V7 best x");
    BG_HIP_TORSION_ALLOCATE(best_y, coordinate_count, "torsion V7 best y");
    BG_HIP_TORSION_ALLOCATE(best_z, coordinate_count, "torsion V7 best z");
    BG_HIP_TORSION_ALLOCATE(
        current_receptor, coordinate_count, "torsion V7 current receptor");
    BG_HIP_TORSION_ALLOCATE(
        trial_receptor, coordinate_count, "torsion V7 trial receptor");
    BG_HIP_TORSION_ALLOCATE(
        best_receptor, coordinate_count, "torsion V7 best receptor");
    const size_t internal_count =
        kTorsionCandidateCount * state->internal_pair_count;
    BG_HIP_TORSION_ALLOCATE(
        current_internal, internal_count, "torsion V7 current internal");
    BG_HIP_TORSION_ALLOCATE(
        trial_internal, internal_count, "torsion V7 trial internal");
    BG_HIP_TORSION_ALLOCATE(
        best_internal, internal_count, "torsion V7 best internal");
#undef BG_HIP_TORSION_ALLOCATE
#undef BG_HIP_TORSION_COPY

    const TorsionDeviceBatch device_batch = {
        candidate_state.get(),
        eligible.get(),
        max_steps.get(),
        baseline_steps.get(),
        source_x.get(),
        source_y.get(),
        source_z.get(),
        baseline_x.get(),
        baseline_y.get(),
        baseline_z.get(),
        baseline_angles.get(),
    };
    const TorsionDeviceOutputs device_outputs = {
        rows.get(),
        moves.get(),
        optimized_x.get(),
        optimized_y.get(),
        optimized_z.get(),
        optimized_angles.get(),
        final_x.get(),
        final_y.get(),
        final_z.get(),
        final_angles.get(),
    };
    const TorsionScratch device_scratch = {
        current_x.get(),
        current_y.get(),
        current_z.get(),
        current_angles.get(),
        trial_x.get(),
        trial_y.get(),
        trial_z.get(),
        best_x.get(),
        best_y.get(),
        best_z.get(),
        current_receptor.get(),
        trial_receptor.get(),
        best_receptor.get(),
        current_internal.get(),
        trial_internal.get(),
        best_internal.get(),
    };
    hipLaunchKernelGGL(
        torsion_fixed64_kernel,
        dim3(1),
        dim3(static_cast<unsigned int>(kTorsionCandidateCount)),
        0,
        0,
        state->device_context(),
        device_batch,
        device_outputs,
        device_scratch);
    hipError_t status = hipGetLastError();
    if (status == hipSuccess) {
        status = hipDeviceSynchronize();
    }
    if (status != hipSuccess) {
        return torsion_fail_hip(
            status,
            error_message,
            error_capacity,
            "torsion V7 kernel execution");
    }

#define BG_HIP_TORSION_RESULT_COPY(buffer, destination, count, operation)  \
    do {                                                                   \
        const hipError_t copy_status = (buffer).copy_to((destination), (count)); \
        if (copy_status != hipSuccess) {                                   \
            return torsion_fail_hip(                                       \
                copy_status, error_message, error_capacity, (operation));  \
        }                                                                  \
    } while (false)
    BG_HIP_TORSION_RESULT_COPY(
        rows, out_rows, kTorsionCandidateCount, "torsion V7 row result copy");
    BG_HIP_TORSION_RESULT_COPY(
        moves,
        out_moves,
        kTorsionCandidateCount * kTorsionMaxMoves,
        "torsion V7 move result copy");
    BG_HIP_TORSION_RESULT_COPY(
        optimized_x,
        out_optimized_x_angstrom,
        coordinate_count,
        "torsion V7 optimized-x result copy");
    BG_HIP_TORSION_RESULT_COPY(
        optimized_y,
        out_optimized_y_angstrom,
        coordinate_count,
        "torsion V7 optimized-y result copy");
    BG_HIP_TORSION_RESULT_COPY(
        optimized_z,
        out_optimized_z_angstrom,
        coordinate_count,
        "torsion V7 optimized-z result copy");
    BG_HIP_TORSION_RESULT_COPY(
        optimized_angles,
        out_optimized_torsion_angles_radians,
        coordinate_count,
        "torsion V7 optimized-angle result copy");
    BG_HIP_TORSION_RESULT_COPY(
        final_x,
        out_final_x_angstrom,
        coordinate_count,
        "torsion V7 final-x result copy");
    BG_HIP_TORSION_RESULT_COPY(
        final_y,
        out_final_y_angstrom,
        coordinate_count,
        "torsion V7 final-y result copy");
    BG_HIP_TORSION_RESULT_COPY(
        final_z,
        out_final_z_angstrom,
        coordinate_count,
        "torsion V7 final-z result copy");
    BG_HIP_TORSION_RESULT_COPY(
        final_angles,
        out_final_torsion_angles_radians,
        coordinate_count,
        "torsion V7 final-angle result copy");
#undef BG_HIP_TORSION_RESULT_COPY
    return BG_STATUS_OK;
}
