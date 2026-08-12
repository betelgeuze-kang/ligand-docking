#ifndef BETELGEUZE_NATIVE_HIP_SAFE_PROVIDER_H
#define BETELGEUZE_NATIVE_HIP_SAFE_PROVIDER_H

#include "betelgeuze/engine.h"

#include <stddef.h>
#include <stdint.h>

#if defined(__cplusplus)
extern "C" {
#endif

#define BG_HIP_SAFE_PROVIDER_ABI_VERSION UINT32_C(1)
#define BG_HIP_SAFE_ERROR_CAPACITY UINT32_C(256)
#define BG_DOCKING_SCORER_PROVIDER_ABI_VERSION UINT32_C(1)

typedef struct bg_hip_safe_system_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t atom_count;
    const double *position_x;
    const double *position_y;
    const double *position_z;
    const double *charge;
    uint64_t reserved[4];
} bg_hip_safe_system_v1;

typedef struct bg_hip_safe_bond_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const double *equilibrium;
    const double *force_constant;
} bg_hip_safe_bond_soa_v1;

typedef struct bg_hip_safe_angle_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const size_t *atom_k;
    const double *equilibrium;
    const double *force_constant;
} bg_hip_safe_angle_soa_v1;

typedef struct bg_hip_safe_torsion_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const size_t *atom_k;
    const size_t *atom_l;
    const uint32_t *periodicity;
    const double *phase;
    const double *amplitude;
} bg_hip_safe_torsion_soa_v1;

typedef struct bg_hip_safe_pair_v1 {
    size_t atom_i;
    size_t atom_j;
} bg_hip_safe_pair_v1;

typedef struct bg_hip_safe_pair_scale_v1 {
    size_t atom_i;
    size_t atom_j;
    double lennard_jones;
    double coulomb;
} bg_hip_safe_pair_scale_v1;

typedef struct bg_hip_safe_forcefield_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t atom_count;
    const double *sigma;
    const double *epsilon;
    bg_hip_safe_bond_soa_v1 bonds;
    bg_hip_safe_angle_soa_v1 angles;
    bg_hip_safe_torsion_soa_v1 torsions;
    size_t exclusion_count;
    const bg_hip_safe_pair_v1 *exclusions;
    size_t pair_scale_count;
    const bg_hip_safe_pair_scale_v1 *pair_scales;
    uint32_t periodic_axes_mask;
    uint32_t reserved0;
    double cell_lengths[3];
    double cutoff;
    double switch_start;
    double dielectric;
    double screening_kappa;
    double minimum_pair_distance;
    uint64_t reserved[4];
} bg_hip_safe_forcefield_v1;

typedef struct bg_hip_safe_energy_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    double harmonic_bond;
    double harmonic_angle;
    double periodic_torsion;
    double lennard_jones;
    double coulomb;
    double total;
    uint64_t reserved[4];
} bg_hip_safe_energy_v1;

typedef struct bg_hip_safe_force_output_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t capacity;
    double *x;
    double *y;
    double *z;
    uint64_t reserved[4];
} bg_hip_safe_force_output_v1;

/* Host-derived immutable ScorerV1 state. The public descriptor has already
 * passed the independent C++ qualification validator before this private
 * provider boundary is entered. */
typedef struct bg_docking_scorer_derived_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    const double *reference_dihedrals_radians;
    double reference_internal_vdw;
    const size_t *receptor_donor_by_hydrogen;
    const size_t *ligand_donor_by_hydrogen;
    const uint8_t *ligand_donor_heavy_mask;
    uint64_t reserved[4];
} bg_docking_scorer_derived_v1;

int32_t bg_hip_safe_provider_is_available_v1(
    int32_t device_ordinal,
    uint8_t *available,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_evaluate_v1(
    int32_t device_ordinal,
    const bg_hip_safe_system_v1 *system,
    const bg_hip_safe_forcefield_v1 *forcefield,
    uint8_t compute_forces,
    bg_hip_safe_energy_v1 *out_energy,
    bg_hip_safe_force_output_v1 *out_forces,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_docking_fixed64_so3_v1_generate(
    int32_t device_ordinal,
    const bg_docking_fixed64_so3_input_v1 *input,
    bg_docking_fixed64_so3_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_docking_geometric_admission_v1_create(
    int32_t device_ordinal,
    const bg_docking_geometric_admission_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_safe_docking_geometric_admission_v1_destroy(void *state);

int32_t bg_hip_safe_docking_geometric_admission_v1_evaluate_fixed64(
    const void *state,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 *candidates,
    bg_docking_geometric_admission_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_docking_scorer_v1_create(
    int32_t device_ordinal,
    const bg_docking_scorer_v1_context_soa_v1 *descriptor,
    const bg_docking_scorer_derived_v1 *derived,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_safe_docking_scorer_v1_destroy(void *state);

int32_t bg_hip_safe_docking_scorer_v1_score_fixed64(
    const void *state,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 *candidates,
    bg_docking_scorer_v1_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_docking_pose_validity_v1_create(
    int32_t device_ordinal,
    const bg_docking_pose_validity_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_safe_docking_pose_validity_v1_destroy(void *state);

int32_t bg_hip_safe_docking_pose_validity_v1_evaluate_fixed64(
    const void *state,
    const bg_docking_pose_validity_candidate_batch_soa_v1 *candidates,
    bg_docking_pose_validity_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_docking_stable_top_k_v1_create(
    int32_t device_ordinal,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_safe_docking_stable_top_k_v1_destroy(void *state);

int32_t bg_hip_safe_docking_stable_top_k_v1_rank_fixed64(
    const void *state,
    const bg_docking_stable_top_k_input_v1 *input,
    bg_docking_stable_top_k_row_v1 *out_rows,
    uint32_t *out_primary_slot_indices,
    uint64_t *out_primary_count,
    uint32_t *out_valid_slot_indices,
    uint64_t *out_valid_count,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64(
    const void *state,
    const bg_docking_rmsd_cluster_input_v1 *input,
    bg_docking_rmsd_cluster_row_v1 *out_rows,
    uint32_t *out_representative_slot_indices,
    uint64_t *out_cluster_count,
    uint32_t *out_top_k_slot_indices,
    uint64_t *out_top_k_count,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_docking_rigid_refinement_create(
    int32_t device_ordinal,
    const bg_docking_rigid_refinement_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_safe_docking_rigid_refinement_destroy(void *state);

int32_t bg_hip_safe_docking_rigid_refinement_fixed64(
    const void *state,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 *candidates,
    bg_docking_rigid_refinement_row_v1 *out_rows,
    double *out_selected_x,
    double *out_selected_y,
    double *out_selected_z,
    double *out_comparison_v2_x,
    double *out_comparison_v2_y,
    double *out_comparison_v2_z,
    double *out_baseline_v3_x,
    double *out_baseline_v3_y,
    double *out_baseline_v3_z,
    double *out_clearance_v4_x,
    double *out_clearance_v4_y,
    double *out_clearance_v4_z,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_safe_docking_torsion_v7_create(
    int32_t device_ordinal,
    const bg_docking_torsion_v7_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_safe_docking_torsion_v7_destroy(void *state);

int32_t bg_hip_safe_docking_torsion_v7_refine_fixed64(
    const void *state,
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
    size_t error_capacity);

int32_t bg_hip_fast_docking_fixed64_so3_v1_generate(
    int32_t device_ordinal,
    const bg_docking_fixed64_so3_input_v1 *input,
    bg_docking_fixed64_so3_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_fast_docking_geometric_admission_v1_create(
    int32_t device_ordinal,
    const bg_docking_geometric_admission_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_fast_docking_geometric_admission_v1_destroy(void *state);

int32_t bg_hip_fast_docking_geometric_admission_v1_evaluate_fixed64(
    const void *state,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 *candidates,
    bg_docking_geometric_admission_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_fast_docking_scorer_v1_create(
    int32_t device_ordinal,
    const bg_docking_scorer_v1_context_soa_v1 *descriptor,
    const bg_docking_scorer_derived_v1 *derived,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_fast_docking_scorer_v1_destroy(void *state);

int32_t bg_hip_fast_docking_scorer_v1_score_fixed64(
    const void *state,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 *candidates,
    bg_docking_scorer_v1_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_fast_docking_pose_validity_v1_create(
    int32_t device_ordinal,
    const bg_docking_pose_validity_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_fast_docking_pose_validity_v1_destroy(void *state);

int32_t bg_hip_fast_docking_pose_validity_v1_evaluate_fixed64(
    const void *state,
    const bg_docking_pose_validity_candidate_batch_soa_v1 *candidates,
    bg_docking_pose_validity_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_fast_docking_stable_top_k_v1_create(
    int32_t device_ordinal,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_fast_docking_stable_top_k_v1_destroy(void *state);

int32_t bg_hip_fast_docking_stable_top_k_v1_rank_fixed64(
    const void *state,
    const bg_docking_stable_top_k_input_v1 *input,
    bg_docking_stable_top_k_row_v1 *out_rows,
    uint32_t *out_primary_slot_indices,
    uint64_t *out_primary_count,
    uint32_t *out_valid_slot_indices,
    uint64_t *out_valid_count,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_fast_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64(
    const void *state,
    const bg_docking_rmsd_cluster_input_v1 *input,
    bg_docking_rmsd_cluster_row_v1 *out_rows,
    uint32_t *out_representative_slot_indices,
    uint64_t *out_cluster_count,
    uint32_t *out_top_k_slot_indices,
    uint64_t *out_top_k_count,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_fast_docking_rigid_refinement_create(
    int32_t device_ordinal,
    const bg_docking_rigid_refinement_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_fast_docking_rigid_refinement_destroy(void *state);

int32_t bg_hip_fast_docking_rigid_refinement_fixed64(
    const void *state,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 *candidates,
    bg_docking_rigid_refinement_row_v1 *out_rows,
    double *out_selected_x,
    double *out_selected_y,
    double *out_selected_z,
    double *out_comparison_v2_x,
    double *out_comparison_v2_y,
    double *out_comparison_v2_z,
    double *out_baseline_v3_x,
    double *out_baseline_v3_y,
    double *out_baseline_v3_z,
    double *out_clearance_v4_x,
    double *out_clearance_v4_y,
    double *out_clearance_v4_z,
    char *error_message,
    size_t error_capacity);

int32_t bg_hip_fast_docking_torsion_v7_create(
    int32_t device_ordinal,
    const bg_docking_torsion_v7_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity);

void bg_hip_fast_docking_torsion_v7_destroy(void *state);

int32_t bg_hip_fast_docking_torsion_v7_refine_fixed64(
    const void *state,
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
    size_t error_capacity);

#if defined(__cplusplus)
}
#endif

#endif  // BETELGEUZE_NATIVE_HIP_SAFE_PROVIDER_H
