#ifndef BETELGEUZE_NATIVE_RUST_PROVIDER_H
#define BETELGEUZE_NATIVE_RUST_PROVIDER_H

#include "betelgeuze/engine.h"

#include <stddef.h>
#include <stdint.h>

#if defined(__cplusplus)
extern "C" {
#endif

#define BG_RUST_CPU_PROVIDER_ABI_VERSION UINT32_C(1)
#define BG_RUST_CPU_ERROR_CAPACITY UINT32_C(256)

typedef struct bg_rust_cpu_system_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t atom_count;
    const double *position_x;
    const double *position_y;
    const double *position_z;
    const double *charge;
    uint64_t reserved[4];
} bg_rust_cpu_system_v1;

typedef struct bg_rust_cpu_bond_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const double *equilibrium;
    const double *force_constant;
} bg_rust_cpu_bond_soa_v1;

typedef struct bg_rust_cpu_angle_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const size_t *atom_k;
    const double *equilibrium;
    const double *force_constant;
} bg_rust_cpu_angle_soa_v1;

typedef struct bg_rust_cpu_torsion_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const size_t *atom_k;
    const size_t *atom_l;
    const uint32_t *periodicity;
    const double *phase;
    const double *amplitude;
} bg_rust_cpu_torsion_soa_v1;

typedef struct bg_rust_cpu_pair_v1 {
    size_t atom_i;
    size_t atom_j;
} bg_rust_cpu_pair_v1;

typedef struct bg_rust_cpu_pair_scale_v1 {
    size_t atom_i;
    size_t atom_j;
    double lennard_jones;
    double coulomb;
} bg_rust_cpu_pair_scale_v1;

typedef struct bg_rust_cpu_forcefield_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t atom_count;
    const double *sigma;
    const double *epsilon;
    bg_rust_cpu_bond_soa_v1 bonds;
    bg_rust_cpu_angle_soa_v1 angles;
    bg_rust_cpu_torsion_soa_v1 torsions;
    size_t exclusion_count;
    const bg_rust_cpu_pair_v1 *exclusions;
    size_t pair_scale_count;
    const bg_rust_cpu_pair_scale_v1 *pair_scales;
    uint32_t periodic_axes_mask;
    uint32_t reserved0;
    double cell_lengths[3];
    double cutoff;
    double switch_start;
    double dielectric;
    double screening_kappa;
    double minimum_pair_distance;
    uint64_t reserved[4];
} bg_rust_cpu_forcefield_v1;

typedef struct bg_rust_cpu_energy_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    double harmonic_bond;
    double harmonic_angle;
    double periodic_torsion;
    double lennard_jones;
    double coulomb;
    double total;
    uint64_t reserved[4];
} bg_rust_cpu_energy_v1;

typedef struct bg_rust_cpu_force_output_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t capacity;
    double *x;
    double *y;
    double *z;
    uint64_t reserved[4];
} bg_rust_cpu_force_output_v1;

typedef struct bg_rust_cpu_error_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    char message[BG_RUST_CPU_ERROR_CAPACITY];
    uint64_t reserved[4];
} bg_rust_cpu_error_v1;

uint32_t bg_rust_cpu_provider_abi_version_v1(void);

int32_t bg_rust_cpu_evaluate_v1(
    const bg_rust_cpu_system_v1 *system,
    const bg_rust_cpu_forcefield_v1 *forcefield,
    uint8_t compute_forces,
    bg_rust_cpu_energy_v1 *out_energy,
    bg_rust_cpu_force_output_v1 *out_forces,
    bg_rust_cpu_error_v1 *out_error);

int32_t bg_rust_cpu_docking_geometric_admission_v1_create(
    const bg_docking_geometric_admission_context_soa_v1 *descriptor,
    void **out_state,
    bg_rust_cpu_error_v1 *out_error);

void bg_rust_cpu_docking_geometric_admission_v1_destroy(void *state);

int32_t bg_rust_cpu_docking_geometric_admission_v1_evaluate_fixed64(
    const void *state,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 *candidates,
    bg_docking_geometric_admission_row_v1 *out_rows,
    bg_rust_cpu_error_v1 *out_error);

int32_t bg_rust_cpu_docking_fixed64_allocation_v1_build(
    const bg_docking_fixed64_allocation_input_v1 *input,
    bg_docking_fixed64_allocation_row_v1 *out_rows,
    uint8_t *out_inventory_sha256,
    uint8_t *out_allocation_sha256,
    uint64_t *out_ready_count,
    uint64_t *out_typed_failure_count,
    bg_rust_cpu_error_v1 *out_error);

int32_t bg_rust_cpu_docking_scorer_v1_create(
    const bg_docking_scorer_v1_context_soa_v1 *descriptor,
    void **out_state,
    bg_rust_cpu_error_v1 *out_error);

void bg_rust_cpu_docking_scorer_v1_destroy(void *state);

int32_t bg_rust_cpu_docking_scorer_v1_score_fixed64(
    const void *state,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 *candidates,
    bg_docking_scorer_v1_row_v1 *out_rows,
    bg_rust_cpu_error_v1 *out_error);

int32_t bg_rust_cpu_docking_pose_validity_v1_create(
    const bg_docking_pose_validity_context_soa_v1 *descriptor,
    void **out_state,
    bg_rust_cpu_error_v1 *out_error);

void bg_rust_cpu_docking_pose_validity_v1_destroy(void *state);

int32_t bg_rust_cpu_docking_pose_validity_v1_evaluate_fixed64(
    const void *state,
    const bg_docking_pose_validity_candidate_batch_soa_v1 *candidates,
    bg_docking_pose_validity_row_v1 *out_rows,
    bg_rust_cpu_error_v1 *out_error);

int32_t bg_rust_cpu_docking_stable_top_k_v1_create(
    void **out_state,
    bg_rust_cpu_error_v1 *out_error);

void bg_rust_cpu_docking_stable_top_k_v1_destroy(void *state);

int32_t bg_rust_cpu_docking_stable_top_k_v1_rank_fixed64(
    const void *state,
    const bg_docking_stable_top_k_input_v1 *input,
    bg_docking_stable_top_k_row_v1 *out_rows,
    uint32_t *out_primary_slot_indices,
    uint64_t *out_primary_count,
    uint32_t *out_valid_slot_indices,
    uint64_t *out_valid_count,
    bg_rust_cpu_error_v1 *out_error);

int32_t bg_rust_cpu_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64(
    const void *state,
    const bg_docking_rmsd_cluster_input_v1 *input,
    bg_docking_rmsd_cluster_row_v1 *out_rows,
    uint32_t *out_representative_slot_indices,
    uint64_t *out_cluster_count,
    uint32_t *out_top_k_slot_indices,
    uint64_t *out_top_k_count,
    bg_rust_cpu_error_v1 *out_error);

typedef struct bg_rust_cpu_rigid_v2_config_v1 {
    double overlap_scale;
    double maximum_step_angstrom;
    double minimum_step_angstrom;
    double maximum_total_translation_angstrom;
    size_t maximum_backtracking_evaluations;
    double penalty_tolerance;
    double epsilon_angstrom;
    uint64_t reserved[4];
} bg_rust_cpu_rigid_v2_config_v1;

typedef struct bg_rust_cpu_rigid_v3_config_v1 {
    bg_rust_cpu_rigid_v2_config_v1 v2;
    double maximum_rotation_step_radians;
    double minimum_rotation_step_radians;
    double maximum_total_rotation_radians;
    size_t maximum_rotation_steps;
    double minimum_rotation_relative_penalty_reduction;
    double maximum_centroid_offset_angstrom;
    uint64_t reserved[4];
} bg_rust_cpu_rigid_v3_config_v1;

typedef struct bg_rust_cpu_rigid_context_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t receptor_atom_count;
    size_t ligand_atom_count;
    const double *receptor_x_angstrom;
    const double *receptor_y_angstrom;
    const double *receptor_z_angstrom;
    const double *receptor_vdw_radius_angstrom;
    const double *ligand_vdw_radius_angstrom;
    double pocket_center_angstrom[3];
    double pocket_radius_angstrom;
    bg_rust_cpu_rigid_v2_config_v1 v2;
    bg_rust_cpu_rigid_v3_config_v1 v3;
    bg_rust_cpu_rigid_v3_config_v1 clearance_v4;
    uint64_t reserved[8];
} bg_rust_cpu_rigid_context_v1;

typedef struct bg_rust_cpu_rigid_batch_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t candidate_count;
    size_t ligand_atom_count;
    const int32_t *candidate_mode;
    const size_t *max_steps;
    const double *x_angstrom;
    const double *y_angstrom;
    const double *z_angstrom;
    uint64_t reserved[8];
} bg_rust_cpu_rigid_batch_v1;

typedef struct bg_rust_cpu_rigid_evidence_v1 {
    int32_t profile;
    uint8_t available;
    uint8_t reserved0[3];
    size_t accepted_steps;
    size_t accepted_translation_steps;
    size_t accepted_rotation_steps;
    size_t line_search_evaluation_count;
    size_t fallback_direction_step_count;
    double initial_penalty;
    double final_penalty;
    double total_translation_angstrom[3];
    double total_rotation_vector_radians[3];
    double total_rotation_path_radians;
    double initial_centroid_offset_angstrom;
    double final_centroid_offset_angstrom;
    double maximum_centroid_offset_angstrom;
    uint64_t reserved[4];
} bg_rust_cpu_rigid_evidence_v1;

typedef struct bg_rust_cpu_rigid_row_v1 {
    uint32_t slot_index;
    int32_t status;
    int32_t failure_code;
    int32_t candidate_mode;
    int32_t selected_profile;
    uint8_t baseline_duplicate_of_v2;
    uint8_t clearance_evaluated;
    uint8_t clearance_selected;
    uint8_t reserved0;
    bg_rust_cpu_rigid_evidence_v1 selected;
    bg_rust_cpu_rigid_evidence_v1 comparison_v2;
    bg_rust_cpu_rigid_evidence_v1 baseline_v3;
    bg_rust_cpu_rigid_evidence_v1 clearance_v4;
    uint64_t reserved[8];
} bg_rust_cpu_rigid_row_v1;

int32_t bg_rust_cpu_docking_rigid_refinement_create(
    const bg_rust_cpu_rigid_context_v1 *descriptor,
    void **out_state,
    bg_rust_cpu_error_v1 *out_error);

void bg_rust_cpu_docking_rigid_refinement_destroy(void *state);

int32_t bg_rust_cpu_docking_rigid_refinement_fixed64(
    const void *state,
    const bg_rust_cpu_rigid_batch_v1 *batch,
    bg_rust_cpu_rigid_row_v1 *out_rows,
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
    bg_rust_cpu_error_v1 *out_error);

#define BG_RUST_CPU_TORSION_V7_MAX_MOVES UINT32_C(8)

typedef struct bg_rust_cpu_torsion_v7_context_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t receptor_atom_count;
    size_t ligand_atom_count;
    size_t rotor_count;
    size_t internal_pair_count;
    const double *receptor_x_angstrom;
    const double *receptor_y_angstrom;
    const double *receptor_z_angstrom;
    const double *receptor_vdw_radius_angstrom;
    const double *ligand_vdw_radius_angstrom;
    double pocket_center_angstrom[3];
    const int32_t *parent_atom_index;
    const size_t *rotatable_child_atom_index;
    const size_t *internal_pair_atom_i;
    const size_t *internal_pair_atom_j;
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
    uint64_t reserved[8];
} bg_rust_cpu_torsion_v7_context_v1;

typedef struct bg_rust_cpu_torsion_v7_batch_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t candidate_count;
    size_t ligand_atom_count;
    const int32_t *candidate_state;
    const uint8_t *proposal_is_torsion_eligible;
    const size_t *max_steps;
    const size_t *baseline_v6_accepted_steps;
    const double *source_x_angstrom;
    const double *source_y_angstrom;
    const double *source_z_angstrom;
    const double *baseline_v6_x_angstrom;
    const double *baseline_v6_y_angstrom;
    const double *baseline_v6_z_angstrom;
    const double *baseline_v6_torsion_angles_radians;
    uint64_t reserved[8];
} bg_rust_cpu_torsion_v7_batch_v1;

typedef struct bg_rust_cpu_torsion_v7_row_v1 {
    uint32_t slot_index;
    int32_t status;
    int32_t failure_code;
    int32_t skip_reason;
    int32_t selection_reason;
    uint8_t selection_window_reachable;
    uint8_t evaluation_stopped_after_selection_window_became_unreachable;
    uint8_t torsion_evaluated;
    uint8_t torsion_variant_available;
    uint8_t torsion_selected;
    uint8_t reserved0[3];
    size_t torsion_step_budget;
    size_t fixed_objective_evaluation_count;
    size_t torsion_trial_objective_evaluation_count;
    size_t evaluated_torsion_steps;
    size_t accepted_torsion_steps;
    size_t baseline_v6_accepted_steps;
    double source_receptor_penalty;
    double source_internal_penalty;
    double source_combined_penalty;
    double baseline_receptor_penalty;
    double baseline_internal_penalty;
    double baseline_combined_penalty;
    double optimized_receptor_penalty;
    double optimized_internal_penalty;
    double optimized_combined_penalty;
    double final_receptor_penalty;
    double final_internal_penalty;
    double final_combined_penalty;
    double evaluated_total_torsion_path_radians;
    double accepted_total_torsion_path_radians;
    uint64_t reserved[8];
} bg_rust_cpu_torsion_v7_row_v1;

typedef struct bg_rust_cpu_torsion_v7_move_v1 {
    uint32_t slot_index;
    uint32_t move_index;
    uint8_t evaluated;
    uint8_t selected;
    uint16_t reserved0;
    size_t rotatable_child_atom_index;
    double delta_radians;
    double receptor_penalty;
    double internal_penalty;
    double combined_penalty;
    uint64_t reserved[4];
} bg_rust_cpu_torsion_v7_move_v1;

int32_t bg_rust_cpu_docking_torsion_v7_create(
    const bg_rust_cpu_torsion_v7_context_v1 *descriptor,
    void **out_state,
    bg_rust_cpu_error_v1 *out_error);

void bg_rust_cpu_docking_torsion_v7_destroy(void *state);

int32_t bg_rust_cpu_docking_torsion_v7_refine_fixed64(
    const void *state,
    const bg_rust_cpu_torsion_v7_batch_v1 *batch,
    bg_rust_cpu_torsion_v7_row_v1 *out_rows,
    bg_rust_cpu_torsion_v7_move_v1 *out_moves,
    double *out_optimized_x_angstrom,
    double *out_optimized_y_angstrom,
    double *out_optimized_z_angstrom,
    double *out_optimized_torsion_angles_radians,
    double *out_final_x_angstrom,
    double *out_final_y_angstrom,
    double *out_final_z_angstrom,
    double *out_final_torsion_angles_radians,
    bg_rust_cpu_error_v1 *out_error);

#if defined(__cplusplus)
}
#endif

#endif  // BETELGEUZE_NATIVE_RUST_PROVIDER_H
