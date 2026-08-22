#ifndef BETELGEUZE_NATIVE_INTERNAL_HPP
#define BETELGEUZE_NATIVE_INTERNAL_HPP

#if !defined(BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#  define BG_INTERNAL_UNDEF_DESCRIPTOR_INIT_MACRO_GUARD
#endif
#include "betelgeuze/engine.h"
#include "cpu/neighbor_pair.hpp"
#if defined(BG_INTERNAL_UNDEF_DESCRIPTOR_INIT_MACRO_GUARD)
#  undef BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#  undef BG_INTERNAL_UNDEF_DESCRIPTOR_INIT_MACRO_GUARD
#endif

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <new>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <vector>

namespace betelgeuze::native::docking::fixed64_allocation {
[[nodiscard]] bg_status verify_snapshot(
    const uint8_t (&inventory_sha256)[32],
    const uint8_t (&allocation_sha256)[32],
    const bg_docking_fixed64_allocation_row_v1 *rows,
    std::size_t row_count) noexcept;
}

namespace betelgeuze::native::docking::fixed64_single_anchor {
[[nodiscard]] bg_status place_for_shared_admission(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    bg_docking_fixed64_single_anchor_output_v1 *output);
}

namespace betelgeuze::native::docking::fixed64_producer {
[[nodiscard]] bg_status validate_for_composition(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_producer_input_v1 &input,
    const bg_docking_fixed64_producer_output_v1 &output);
}

namespace betelgeuze::native::docking::downstream {
[[nodiscard]] std::array<uint8_t, 32> coordinate_digest_for_composition(
    const bg_docking_scorer_v1_candidate_batch_soa_v1 &candidates,
    std::size_t ligand_count,
    std::size_t slot) noexcept;
}

namespace betelgeuze::native::docking::refinement_pipeline {
[[nodiscard]] bg_status validate_outputs_for_composition(
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    std::size_t coordinate_count,
    bg_docking_rigid_refinement_output_v1 &rigid,
    bg_docking_torsion_v7_output_v1 &torsion,
    bg_docking_scorer_v1_output_v1 &scorer,
    bg_docking_pose_validity_output_v1 &validity,
    bg_docking_stable_top_k_output_v1 &ranking,
    bg_docking_rmsd_cluster_output_v1 &cluster,
    bg_docking_fixed64_refinement_output_v1 &output);
[[nodiscard]] bg_status validate_input_and_overlap_for_composition(
    const bg_context &context,
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    const bg_docking_fixed64_refinement_input_v1 &input,
    bg_docking_rigid_refinement_output_v1 &rigid,
    bg_docking_torsion_v7_output_v1 &torsion,
    bg_docking_scorer_v1_output_v1 &scorer,
    bg_docking_pose_validity_output_v1 &validity,
    bg_docking_stable_top_k_output_v1 &ranking,
    bg_docking_rmsd_cluster_output_v1 &cluster,
    bg_docking_fixed64_refinement_output_v1 &output);
[[nodiscard]] bg_status run_stage_for_composition(
    const bg_context &context,
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    const bg_docking_fixed64_refinement_input_v1 &input,
    bg_docking_rigid_refinement_output_v1 &rigid,
    bg_docking_torsion_v7_output_v1 &torsion,
    bg_docking_fixed64_refinement_output_v1 &output);
[[nodiscard]] bg_status validate_for_composition(
    const bg_context &context,
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    const bg_docking_fixed64_refinement_input_v1 &input,
    bg_docking_rigid_refinement_output_v1 &rigid,
    bg_docking_torsion_v7_output_v1 &torsion,
    bg_docking_scorer_v1_output_v1 &scorer,
    bg_docking_pose_validity_output_v1 &validity,
    bg_docking_stable_top_k_output_v1 &ranking,
    bg_docking_rmsd_cluster_output_v1 &cluster,
    bg_docking_fixed64_refinement_output_v1 &output);
}

struct bg_context final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    int32_t device_ordinal = 0;
    /* Backend-private ownership.  Public callers only ever see bg_context as
     * an opaque handle; the selected provider initializes and destroys this
     * state with the context. */
    void *backend_state = nullptr;
};

struct bg_docking_geometric_admission_v1 final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    int32_t device_ordinal = 0;
    uint64_t receptor_atom_count = 0;
    uint64_t ligand_atom_count = 0;
    uint64_t ligand_heavy_atom_count = 0;
    uint64_t max_batch_exact_pair_evaluations = 0;
    std::array<double, 3> pocket_center_angstrom{};
    double pocket_radius_angstrom = 0.0;
    double hard_rejection_minimum_vdw_ratio = 0.0;
    std::vector<double> receptor_x_angstrom;
    std::vector<double> receptor_y_angstrom;
    std::vector<double> receptor_z_angstrom;
    std::vector<double> receptor_vdw_radius_angstrom;
    std::vector<double> ligand_vdw_radius_angstrom;
    std::vector<uint8_t> ligand_heavy_atom_mask;
    std::array<uint8_t, 32> authority_input_receipt_sha256{};
    std::array<uint8_t, 32> receptor_system_sha256{};
    std::array<uint8_t, 32> ligand_system_sha256{};
    std::array<uint8_t, 32> backend_receipt_sha256{};
    void *provider_state = nullptr;
};

struct bg_docking_scorer_v1 final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    int32_t device_ordinal = 0;
    void *provider_state = nullptr;
};

struct bg_docking_pose_validity_v1 final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    int32_t device_ordinal = 0;
    void *provider_state = nullptr;
};

struct bg_docking_stable_top_k_v1 final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    int32_t device_ordinal = 0;
    void *provider_state = nullptr;
};

struct bg_docking_fixed64_downstream_v1 final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    int32_t device_ordinal = 0;
    uint64_t ligand_atom_count = 0;
    bg_docking_scorer_v1 *scorer = nullptr;
    bg_docking_pose_validity_v1 *validity = nullptr;
    bg_docking_stable_top_k_v1 *ranker = nullptr;
};

struct bg_docking_fixed64_refinement_pipeline_v1 final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    int32_t device_ordinal = 0;
    uint64_t ligand_atom_count = 0;
    bg_docking_rigid_refinement *rigid = nullptr;
    bg_docking_torsion_v7 *torsion = nullptr;
    bg_docking_fixed64_downstream_v1 *downstream = nullptr;
};

struct bg_docking_fixed64_pipeline_v1 final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    int32_t device_ordinal = 0;
    uint64_t receptor_atom_count = 0;
    uint64_t ligand_atom_count = 0;
    bg_docking_geometric_admission_v1 *admission = nullptr;
    bg_docking_fixed64_refinement_pipeline_v1 *refinement = nullptr;
    std::array<uint8_t, 32> admission_context_receipt_sha256{};
    std::array<uint8_t, 32> refinement_context_receipt_sha256{};
    std::array<uint8_t, 32> scorer_context_receipt_sha256{};
    std::array<uint8_t, 32> validity_context_receipt_sha256{};
    std::array<uint8_t, 32> component_binding_receipt_sha256{};
};

struct bg_docking_fixed64_pipeline_v2_workspace final {
    uint64_t successful_run_count = 0;
    uint64_t coordinate_capacity_growth_count = 0;
    std::size_t provisioned_coordinate_count = 0;
    std::vector<double> producer_x;
    std::vector<double> producer_y;
    std::vector<double> producer_z;
    std::array<std::vector<double>, 12> rigid_coordinates;
    std::array<std::vector<double>, 8> torsion_coordinates;
    std::array<std::vector<double>, 3> final_coordinates;
};

struct bg_docking_fixed64_pipeline_v2 final {
    bg_docking_fixed64_pipeline_v1 *components = nullptr;
    // ABI v2 pipeline handles require external synchronization. Keeping the
    // workspace mutable preserves the frozen const run signature while making
    // repeated prepared-session runs allocation-stable.
    mutable bg_docking_fixed64_pipeline_v2_workspace workspace;
};

struct bg_docking_rigid_refinement final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    int32_t device_ordinal = 0;
    uint64_t ligand_atom_count = 0;
    void *provider_state = nullptr;
};

struct bg_docking_torsion_v7 final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    int32_t device_ordinal = 0;
    uint64_t ligand_atom_count = 0;
    void *provider_state = nullptr;
};

struct bg_system final {
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    std::vector<double> position_x;
    std::vector<double> position_y;
    std::vector<double> position_z;
    std::vector<double> velocity_x;
    std::vector<double> velocity_y;
    std::vector<double> velocity_z;
    std::vector<double> mass;
    std::vector<double> charge;
};

struct bg_forcefield final {
    struct BondSoa {
        std::vector<std::size_t> atom_i;
        std::vector<std::size_t> atom_j;
        std::vector<double> equilibrium;
        std::vector<double> force_constant;
    } bonds;

    struct AngleSoa {
        std::vector<std::size_t> atom_i;
        std::vector<std::size_t> atom_j;
        std::vector<std::size_t> atom_k;
        std::vector<double> equilibrium;
        std::vector<double> force_constant;
    } angles;

    struct TorsionSoa {
        std::vector<std::size_t> atom_i;
        std::vector<std::size_t> atom_j;
        std::vector<std::size_t> atom_k;
        std::vector<std::size_t> atom_l;
        std::vector<uint32_t> periodicity;
        std::vector<double> phase;
        std::vector<double> amplitude;
    } torsions;

    struct Pair {
        std::size_t atom_i = 0;
        std::size_t atom_j = 0;

        friend bool operator<(const Pair &left, const Pair &right) noexcept {
            return left.atom_i < right.atom_i ||
                   (left.atom_i == right.atom_i &&
                    left.atom_j < right.atom_j);
        }

        friend bool operator==(const Pair &left, const Pair &right) noexcept {
            return left.atom_i == right.atom_i && left.atom_j == right.atom_j;
        }
    };

    struct PairScale {
        Pair pair;
        double lennard_jones = 1.0;
        double coulomb = 1.0;
    };

    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    std::size_t atom_count = 0;
    std::vector<double> sigma;
    std::vector<double> epsilon;
    std::vector<Pair> exclusions;
    std::vector<PairScale> pair_scales;
    uint32_t periodic_axes_mask = 0;
    std::array<double, 3> cell_lengths = {0.0, 0.0, 0.0};
    double cutoff = 10.0;
    double switch_start = 8.0;
    double dielectric = 1.0;
    double screening_kappa = 0.0;
    double minimum_pair_distance = 1.0e-6;
};

struct bg_simulation final {
    struct DistanceConstraint final {
        std::size_t atom_i = 0;
        std::size_t atom_j = 0;
        double distance = 0.0;
    };

    struct NeighborListCacheData final {
        std::vector<double> reference_x;
        std::vector<double> reference_y;
        std::vector<double> reference_z;
        std::vector<betelgeuze::native::cpu::NeighborPair> pairs;
    };

    struct NeighborListCache final {
        std::shared_ptr<const NeighborListCacheData> data;
        std::shared_ptr<betelgeuze::native::cpu::NeighborBuildScratch>
            build_scratch;
        uint64_t build_count = UINT64_C(0);
        uint64_t reuse_count = UINT64_C(0);
    };

    struct DynamicStateScratch final {
        std::vector<double> position_x;
        std::vector<double> position_y;
        std::vector<double> position_z;
        std::vector<double> velocity_x;
        std::vector<double> velocity_y;
        std::vector<double> velocity_z;
    };

    struct ParticleVectorScratch final {
        std::vector<double> x;
        std::vector<double> y;
        std::vector<double> z;
    };

    struct ConstraintValidationScratch final {
        struct Direction final {
            double x = 0.0;
            double y = 0.0;
            double z = 0.0;
        };

        std::vector<double> gram;
        std::vector<Direction> directions;
    };

    bg_simulation() = default;
    bg_simulation(const bg_simulation &) = delete;
    bg_simulation &operator=(const bg_simulation &) = delete;
    bg_simulation(bg_simulation &&) noexcept = default;
    bg_simulation &operator=(bg_simulation &&) noexcept = default;

    bg_system system;
    bg_forcefield forcefield;
    std::vector<DistanceConstraint> constraints;
    double constraint_tolerance = 1.0e-10;
    double constraint_velocity_tolerance = 1.0e-10;
    uint32_t constraint_max_iterations = UINT32_C(100);
    bg_integrator integrator = BG_INTEGRATOR_VELOCITY_VERLET;
    double timestep_femtoseconds = 1.0;
    double temperature_kelvin = 300.0;
    double friction_per_femtosecond = 0.001;
    uint64_t random_seed = UINT64_C(0);
    uint64_t absolute_step = UINT64_C(0);
    std::array<uint8_t, 32> static_fingerprint{};
    NeighborListCache neighbor_list_cache;
    DynamicStateScratch dynamic_state_scratch;
    ParticleVectorScratch force_evaluation_scratch;
    ParticleVectorScratch constraint_drift_scratch;
    ConstraintValidationScratch constraint_validation_scratch;
};

namespace betelgeuze::native {

inline constexpr std::size_t kLastErrorCapacity = 1024;
extern thread_local std::array<char, kLastErrorCapacity> last_error;

inline void clear_last_error() noexcept {
    last_error[0] = '\0';
}

inline void set_last_error(const char *message) noexcept {
    if (message == nullptr) {
        message = "";
    }
    std::size_t index = 0;
    while (index + 1 < last_error.size() && message[index] != '\0') {
        last_error[index] = message[index];
        ++index;
    }
    last_error[index] = '\0';
}

inline bg_status fail(bg_status status, const char *message) noexcept {
    set_last_error(message);
    return status;
}

template <typename Function>
bg_status guarded_status(Function &&function) noexcept {
    clear_last_error();
    try {
        return std::forward<Function>(function)();
    } catch (const std::length_error &) {
        set_last_error("native container capacity exceeded");
        return BG_STATUS_CAPACITY_OVERFLOW;
    } catch (const std::bad_alloc &) {
        set_last_error("native allocation failed");
        return BG_STATUS_OUT_OF_MEMORY;
    } catch (const std::exception &) {
        set_last_error("native operation failed");
        return BG_STATUS_INTERNAL_ERROR;
    } catch (...) {
        set_last_error("unknown native exception");
        return BG_STATUS_INTERNAL_ERROR;
    }
}

inline bg_status validate_descriptor_header(
    uint32_t observed_size,
    std::size_t expected_size,
    uint32_t observed_version,
    const char *size_error,
    const char *version_error) noexcept {
    static_assert(sizeof(std::size_t) <= sizeof(uint64_t));
    if (expected_size > std::numeric_limits<uint32_t>::max() ||
        observed_size != static_cast<uint32_t>(expected_size)) {
        return fail(BG_STATUS_ABI_MISMATCH, size_error);
    }
    if (observed_version != BG_ABI_VERSION) {
        return fail(BG_STATUS_ABI_MISMATCH, version_error);
    }
    return BG_STATUS_OK;
}

/*
 * Initializers receive the layout identity compiled into the caller.  Check
 * it before dereferencing the descriptor so an older, smaller allocation is
 * never overwritten by a newer library.  ABI v1 intentionally requires an
 * exact match; incompatible layouts fail without touching caller storage.
 */
inline bg_status validate_initializer_compatibility(
    const void *descriptor,
    std::size_t caller_struct_size,
    std::size_t native_struct_size,
    uint32_t caller_abi_version,
    const char *null_error,
    const char *size_error,
    const char *version_error) noexcept {
    if (descriptor == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, null_error);
    }
    if (native_struct_size > std::numeric_limits<uint32_t>::max() ||
        caller_struct_size != native_struct_size) {
        return fail(BG_STATUS_ABI_MISMATCH, size_error);
    }
    if (caller_abi_version != BG_ABI_VERSION) {
        return fail(BG_STATUS_ABI_MISMATCH, version_error);
    }
    return BG_STATUS_OK;
}

template <std::size_t Size>
bool reserved_is_zero(const uint64_t (&reserved)[Size]) noexcept {
    for (const uint64_t value : reserved) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

inline bg_status validate_unit_system(bg_unit_system units) noexcept {
    if (units != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "unit_system must be BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL");
    }
    return BG_STATUS_OK;
}

inline bg_status checked_particle_count(
    uint64_t particle_count,
    std::size_t *out_count) noexcept {
    if (out_count == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "internal count output is null");
    }
    if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
        if (particle_count > static_cast<uint64_t>(
                                 std::numeric_limits<std::size_t>::max())) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "particle_count does not fit the native address space");
        }
    }

    constexpr std::size_t channel_count = 8;
    constexpr std::size_t bytes_per_particle = channel_count * sizeof(double);
    const uint64_t max_total_count = static_cast<uint64_t>(
        std::numeric_limits<std::size_t>::max() / bytes_per_particle);
    if (particle_count > max_total_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "particle_count overflows owned SoA capacity");
    }

    const uint64_t max_vector_count = static_cast<uint64_t>(
        std::numeric_limits<std::ptrdiff_t>::max() / sizeof(double));
    if (particle_count > max_vector_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "particle_count exceeds vector capacity");
    }

    *out_count = static_cast<std::size_t>(particle_count);
    return BG_STATUS_OK;
}

inline std::vector<double> copy_channel(
    const double *source,
    std::size_t count) {
    if (count == 0) {
        return {};
    }
    return std::vector<double>(source, source + count);
}

inline bool all_finite(const std::vector<double> &values) noexcept {
    for (const double value : values) {
        if (!std::isfinite(value)) {
            return false;
        }
    }
    return true;
}

inline bool all_positive_finite(const std::vector<double> &values) noexcept {
    for (const double value : values) {
        if (!std::isfinite(value) || value <= 0.0) {
            return false;
        }
    }
    return true;
}

inline bool double_pointer_is_aligned(const double *pointer) noexcept {
    return pointer == nullptr ||
           (reinterpret_cast<std::uintptr_t>(pointer) % alignof(double)) == 0;
}

template <typename Type>
inline bool pointer_is_aligned(const Type *pointer) noexcept {
    return pointer == nullptr ||
           (reinterpret_cast<std::uintptr_t>(pointer) % alignof(Type)) == 0;
}

inline bg_status checked_element_count(
    uint64_t observed_count,
    std::size_t element_size,
    const char *overflow_message,
    std::size_t *out_count) noexcept {
    if (out_count == nullptr || element_size == 0) {
        return fail(BG_STATUS_INTERNAL_ERROR, "invalid internal count request");
    }
    if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
        if (observed_count > static_cast<uint64_t>(
                                 std::numeric_limits<std::size_t>::max())) {
            return fail(BG_STATUS_CAPACITY_OVERFLOW, overflow_message);
        }
    }
    const auto max_count = static_cast<uint64_t>(
        std::numeric_limits<std::size_t>::max() / element_size);
    if (observed_count > max_count) {
        return fail(BG_STATUS_CAPACITY_OVERFLOW, overflow_message);
    }
    const auto max_difference_count = static_cast<uint64_t>(
        std::numeric_limits<std::ptrdiff_t>::max() / element_size);
    if (observed_count > max_difference_count) {
        return fail(BG_STATUS_CAPACITY_OVERFLOW, overflow_message);
    }
    *out_count = static_cast<std::size_t>(observed_count);
    return BG_STATUS_OK;
}

inline const double *borrowed_data(const std::vector<double> &values) noexcept {
    return values.empty() ? nullptr : values.data();
}

}  // namespace betelgeuze::native

#endif  // BETELGEUZE_NATIVE_INTERNAL_HPP
