use core::mem::{align_of, offset_of, size_of};

use betelgeuze_sys::*;

#[test]
fn scalar_aliases_and_discriminants_match_the_c_header() {
    assert_eq!(BG_ABI_VERSION_MAJOR, 1);
    assert_eq!(BG_ABI_VERSION_MINOR, 12);
    assert_eq!(BG_ABI_VERSION, 1);
    assert_eq!(size_of::<bg_status>(), 4);
    assert_eq!(size_of::<bg_backend>(), 4);
    assert_eq!(size_of::<bg_unit_system>(), 4);
    assert_eq!(size_of::<bg_integrator>(), 4);
    assert_eq!(size_of::<bg_docking_scorer_v1_candidate_state>(), 4);
    assert_eq!(size_of::<bg_docking_scorer_v1_row_status>(), 4);
    assert_eq!(size_of::<bg_docking_scorer_v1_failure>(), 4);
    assert_eq!(size_of::<bg_docking_pose_validity_candidate_state>(), 4);
    assert_eq!(size_of::<bg_docking_pose_validity_row_status>(), 4);
    assert_eq!(size_of::<bg_docking_pose_validity_failure>(), 4);
    assert_eq!(size_of::<bg_docking_rmsd_cluster_row_status>(), 4);
    assert_eq!(size_of::<bg_docking_rigid_refinement_candidate_mode>(), 4);
    assert_eq!(size_of::<bg_docking_rigid_refinement_row_status>(), 4);
    assert_eq!(size_of::<bg_docking_rigid_refinement_failure>(), 4);
    assert_eq!(size_of::<bg_docking_rigid_refinement_profile>(), 4);
    assert_eq!(size_of::<bg_docking_torsion_v7_candidate_state>(), 4);
    assert_eq!(size_of::<bg_docking_torsion_v7_row_status>(), 4);
    assert_eq!(size_of::<bg_docking_torsion_v7_failure>(), 4);
    assert_eq!(BG_DOCKING_FIXED64_CANDIDATE_COUNT, 64);
    assert_eq!(BG_DOCKING_SCORER_V1_TERM_COUNT, 8);
    assert_eq!(BG_DOCKING_STABLE_TOP_K_LIMIT, 5);
    assert_eq!(BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT, 5);
    assert_eq!(BG_DOCKING_TORSION_V7_MAX_MOVES, 8);
    assert_eq!(BG_STATUS_OK, 0);
    assert_eq!(BG_STATUS_INTERNAL_ERROR, 9);
    assert_eq!(BG_STATUS_NUMERICAL_ERROR, 10);
    assert_eq!(BG_BACKEND_AUTO, 0);
    assert_eq!(BG_BACKEND_CPU, 1);
    assert_eq!(BG_BACKEND_HIP, 2);
    assert_eq!(BG_BACKEND_CPP_CPU_REFERENCE, 1);
    assert_eq!(BG_BACKEND_HIP_FAST, 2);
    assert_eq!(BG_BACKEND_RUST_CPU, 3);
    assert_eq!(BG_BACKEND_HIP_SAFE, 4);
    assert_eq!(BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL, 1);
    assert_eq!(BG_INTEGRATOR_VELOCITY_VERLET, 1);
    assert_eq!(BG_INTEGRATOR_LANGEVIN_BAOAB, 2);
    assert_eq!(BG_PERIODIC_AXIS_X, 1);
    assert_eq!(BG_PERIODIC_AXIS_Y, 2);
    assert_eq!(BG_PERIODIC_AXIS_Z, 4);
    assert_eq!(BG_PERIODIC_AXES_ALL, 7);
}

#[test]
fn docking_rigid_refinement_layouts_match_the_c_header() {
    assert_eq!(size_of::<bg_docking_rigid_v2_config_v1>(), 88);
    assert_eq!(size_of::<bg_docking_rigid_v3_config_v1>(), 168);
    assert_eq!(size_of::<bg_docking_rigid_refinement_context_soa_v1>(), 592);
    assert_eq!(
        offset_of!(
            bg_docking_rigid_refinement_context_soa_v1,
            receptor_atom_count
        ),
        16
    );
    assert_eq!(
        offset_of!(
            bg_docking_rigid_refinement_context_soa_v1,
            receptor_x_angstrom
        ),
        32
    );
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_context_soa_v1, v2),
        104
    );
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_context_soa_v1, v3),
        192
    );
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_context_soa_v1, clearance_v4),
        360
    );
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_context_soa_v1, reserved),
        528
    );

    assert_eq!(
        size_of::<bg_docking_rigid_refinement_candidate_batch_soa_v1>(),
        136
    );
    assert_eq!(
        offset_of!(
            bg_docking_rigid_refinement_candidate_batch_soa_v1,
            candidate_mode
        ),
        32
    );
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_candidate_batch_soa_v1, reserved),
        72
    );

    assert_eq!(size_of::<bg_docking_rigid_refinement_evidence_v1>(), 176);
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_evidence_v1, accepted_steps),
        8
    );
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_evidence_v1, initial_penalty),
        48
    );
    assert_eq!(
        offset_of!(
            bg_docking_rigid_refinement_evidence_v1,
            total_translation_angstrom
        ),
        64
    );
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_evidence_v1, reserved),
        144
    );

    assert_eq!(size_of::<bg_docking_rigid_refinement_row_v1>(), 792);
    assert_eq!(offset_of!(bg_docking_rigid_refinement_row_v1, selected), 24);
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_row_v1, reserved),
        728
    );

    assert_eq!(size_of::<bg_docking_rigid_refinement_output_v1>(), 224);
    assert_eq!(offset_of!(bg_docking_rigid_refinement_output_v1, rows), 48);
    assert_eq!(
        offset_of!(
            bg_docking_rigid_refinement_output_v1,
            molecular_execution_authorized
        ),
        152
    );
    assert_eq!(
        offset_of!(bg_docking_rigid_refinement_output_v1, reserved),
        160
    );
}

#[test]
fn docking_torsion_v7_layouts_match_the_c_header() {
    assert_eq!(size_of::<bg_docking_torsion_v7_context_soa_v1>(), 328);
    assert_eq!(align_of::<bg_docking_torsion_v7_context_soa_v1>(), 8);
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_context_soa_v1, receptor_atom_count),
        16
    );
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_context_soa_v1, receptor_x_angstrom),
        48
    );
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_context_soa_v1, pocket_center_angstrom),
        88
    );
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_context_soa_v1, parent_atom_index),
        112
    );
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_context_soa_v1, receptor_overlap_scale),
        144
    );
    assert_eq!(
        offset_of!(
            bg_docking_torsion_v7_context_soa_v1,
            maximum_baseline_v6_steps
        ),
        168
    );
    assert_eq!(
        offset_of!(
            bg_docking_torsion_v7_context_soa_v1,
            maximum_torsion_step_radians
        ),
        200
    );
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_context_soa_v1, reserved),
        264
    );

    assert_eq!(
        size_of::<bg_docking_torsion_v7_candidate_batch_soa_v1>(),
        184
    );
    assert_eq!(
        align_of::<bg_docking_torsion_v7_candidate_batch_soa_v1>(),
        8
    );
    assert_eq!(
        offset_of!(
            bg_docking_torsion_v7_candidate_batch_soa_v1,
            candidate_state
        ),
        32
    );
    assert_eq!(
        offset_of!(
            bg_docking_torsion_v7_candidate_batch_soa_v1,
            source_x_angstrom
        ),
        64
    );
    assert_eq!(
        offset_of!(
            bg_docking_torsion_v7_candidate_batch_soa_v1,
            baseline_v6_torsion_angles_radians
        ),
        112
    );
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_candidate_batch_soa_v1, reserved),
        120
    );

    assert_eq!(size_of::<bg_docking_torsion_v7_row_v1>(), 256);
    assert_eq!(align_of::<bg_docking_torsion_v7_row_v1>(), 8);
    assert_eq!(offset_of!(bg_docking_torsion_v7_row_v1, status), 4);
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_row_v1, selection_window_reachable),
        20
    );
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_row_v1, torsion_step_budget),
        32
    );
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_row_v1, source_receptor_penalty),
        80
    );
    assert_eq!(offset_of!(bg_docking_torsion_v7_row_v1, reserved), 192);

    assert_eq!(size_of::<bg_docking_torsion_v7_move_v1>(), 88);
    assert_eq!(align_of::<bg_docking_torsion_v7_move_v1>(), 8);
    assert_eq!(offset_of!(bg_docking_torsion_v7_move_v1, evaluated), 8);
    assert_eq!(
        offset_of!(bg_docking_torsion_v7_move_v1, rotatable_child_atom_index),
        16
    );
    assert_eq!(offset_of!(bg_docking_torsion_v7_move_v1, delta_radians), 24);
    assert_eq!(offset_of!(bg_docking_torsion_v7_move_v1, reserved), 56);

    assert_eq!(size_of::<bg_docking_torsion_v7_output_v1>(), 216);
    assert_eq!(align_of::<bg_docking_torsion_v7_output_v1>(), 8);
    assert_eq!(offset_of!(bg_docking_torsion_v7_output_v1, row_capacity), 8);
    assert_eq!(offset_of!(bg_docking_torsion_v7_output_v1, unit_system), 56);
    assert_eq!(offset_of!(bg_docking_torsion_v7_output_v1, rows), 64);
    assert_eq!(
        offset_of!(
            bg_docking_torsion_v7_output_v1,
            molecular_execution_authorized
        ),
        144
    );
    assert_eq!(offset_of!(bg_docking_torsion_v7_output_v1, reserved), 152);
}

#[cfg(target_pointer_width = "64")]
#[test]
fn fixed64_refinement_pipeline_layouts_match_the_c_header() {
    assert_eq!(size_of::<bg_docking_fixed64_refinement_input_v1>(), 192);
    assert_eq!(align_of::<bg_docking_fixed64_refinement_input_v1>(), 8);
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_input_v1, candidate_count),
        8
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_input_v1, candidate_mode),
        32
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_input_v1, source_x_angstrom),
        64
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_input_v1, source_quaternion_x),
        96
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_input_v1, reserved),
        128
    );

    assert_eq!(size_of::<bg_docking_fixed64_refinement_row_v1>(), 104);
    assert_eq!(align_of::<bg_docking_fixed64_refinement_row_v1>(), 8);
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_row_v1, rigid_failure_code),
        16
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_row_v1, torsion_v7_applicable),
        32
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_row_v1, coordinate_sha256),
        36
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_row_v1, reserved),
        72
    );

    assert_eq!(size_of::<bg_docking_fixed64_refinement_output_v1>(), 200);
    assert_eq!(align_of::<bg_docking_fixed64_refinement_output_v1>(), 8);
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_output_v1, row_capacity),
        8
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_output_v1, unit_system),
        56
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_output_v1, rows),
        64
    );
    assert_eq!(
        offset_of!(
            bg_docking_fixed64_refinement_output_v1,
            molecular_execution_authorized
        ),
        128
    );
    assert_eq!(
        offset_of!(bg_docking_fixed64_refinement_output_v1, reserved),
        136
    );
}

#[test]
fn docking_rmsd_cluster_layouts_match_the_c_header() {
    assert_eq!(size_of::<bg_docking_rmsd_cluster_input_v1>(), 120);
    assert_eq!(align_of::<bg_docking_rmsd_cluster_input_v1>(), 8);
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_input_v1, candidate_count),
        8
    );
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_input_v1, ligand_atom_count),
        16
    );
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_input_v1, valid_index_count),
        24
    );
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_input_v1, rmsd_threshold_angstrom),
        40
    );
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_input_v1, ranking_rows),
        48
    );
    assert_eq!(offset_of!(bg_docking_rmsd_cluster_input_v1, reserved), 88);

    assert_eq!(size_of::<bg_docking_rmsd_cluster_row_v1>(), 112);
    assert_eq!(align_of::<bg_docking_rmsd_cluster_row_v1>(), 8);
    assert_eq!(offset_of!(bg_docking_rmsd_cluster_row_v1, status), 4);
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_row_v1, stable_valid_rank),
        12
    );
    assert_eq!(offset_of!(bg_docking_rmsd_cluster_row_v1, cluster_size), 32);
    assert_eq!(offset_of!(bg_docking_rmsd_cluster_row_v1, reserved1), 36);
    assert_eq!(
        offset_of!(
            bg_docking_rmsd_cluster_row_v1,
            direct_rmsd_to_representative_angstrom
        ),
        40
    );
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_row_v1, coordinate_sha256),
        48
    );
    assert_eq!(offset_of!(bg_docking_rmsd_cluster_row_v1, reserved), 80);

    assert_eq!(size_of::<bg_docking_rmsd_cluster_output_v1>(), 128);
    assert_eq!(align_of::<bg_docking_rmsd_cluster_output_v1>(), 8);
    assert_eq!(
        offset_of!(
            bg_docking_rmsd_cluster_output_v1,
            representative_index_capacity
        ),
        24
    );
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_output_v1, top_k_index_capacity),
        40
    );
    assert_eq!(
        offset_of!(bg_docking_rmsd_cluster_output_v1, unit_system),
        56
    );
    assert_eq!(offset_of!(bg_docking_rmsd_cluster_output_v1, rows), 64);
    assert_eq!(
        offset_of!(
            bg_docking_rmsd_cluster_output_v1,
            existing_rank_auto_change_authorized
        ),
        88
    );
    assert_eq!(offset_of!(bg_docking_rmsd_cluster_output_v1, reserved), 96);
}

#[test]
fn docking_stable_top_k_layouts_match_the_c_header() {
    assert_eq!(size_of::<bg_docking_stable_top_k_input_v1>(), 80);
    assert_eq!(align_of::<bg_docking_stable_top_k_input_v1>(), 8);
    assert_eq!(
        offset_of!(bg_docking_stable_top_k_input_v1, candidate_count),
        8
    );
    assert_eq!(
        offset_of!(bg_docking_stable_top_k_input_v1, scorer_rows),
        24
    );
    assert_eq!(
        offset_of!(bg_docking_stable_top_k_input_v1, coordinate_sha256),
        40
    );
    assert_eq!(offset_of!(bg_docking_stable_top_k_input_v1, reserved), 48);
    assert_eq!(size_of::<bg_docking_stable_top_k_row_v1>(), 88);
    assert_eq!(offset_of!(bg_docking_stable_top_k_row_v1, stable_rank), 8);
    assert_eq!(offset_of!(bg_docking_stable_top_k_row_v1, total_score), 16);
    assert_eq!(
        offset_of!(bg_docking_stable_top_k_row_v1, coordinate_sha256),
        24
    );
    assert_eq!(offset_of!(bg_docking_stable_top_k_row_v1, reserved), 56);
    assert_eq!(size_of::<bg_docking_stable_top_k_output_v1>(), 128);
    assert_eq!(
        offset_of!(bg_docking_stable_top_k_output_v1, unit_system),
        56
    );
    assert_eq!(offset_of!(bg_docking_stable_top_k_output_v1, rows), 64);
    assert_eq!(
        offset_of!(
            bg_docking_stable_top_k_output_v1,
            existing_rank_auto_change_authorized
        ),
        88
    );
    assert_eq!(offset_of!(bg_docking_stable_top_k_output_v1, reserved), 96);
}

#[test]
fn docking_pose_validity_layouts_match_the_c_header() {
    assert_eq!(size_of::<bg_docking_pose_validity_context_soa_v1>(), 560);
    assert_eq!(align_of::<bg_docking_pose_validity_context_soa_v1>(), 8);
    assert_eq!(
        offset_of!(bg_docking_pose_validity_context_soa_v1, receptor_atom_count),
        16
    );
    assert_eq!(
        offset_of!(bg_docking_pose_validity_context_soa_v1, bond_count),
        96
    );
    assert_eq!(
        offset_of!(
            bg_docking_pose_validity_context_soa_v1,
            pocket_center_angstrom
        ),
        184
    );
    assert_eq!(
        offset_of!(bg_docking_pose_validity_context_soa_v1, max_pair_checks),
        272
    );
    assert_eq!(
        offset_of!(
            bg_docking_pose_validity_context_soa_v1,
            authority_input_receipt_sha256
        ),
        304
    );
    assert_eq!(
        offset_of!(bg_docking_pose_validity_context_soa_v1, reserved),
        496
    );
    assert_eq!(
        size_of::<bg_docking_pose_validity_candidate_batch_soa_v1>(),
        136
    );
    assert_eq!(
        offset_of!(
            bg_docking_pose_validity_candidate_batch_soa_v1,
            candidate_state
        ),
        32
    );
    assert_eq!(
        offset_of!(
            bg_docking_pose_validity_candidate_batch_soa_v1,
            quaternion_x
        ),
        48
    );
    assert_eq!(
        offset_of!(bg_docking_pose_validity_candidate_batch_soa_v1, x_angstrom),
        80
    );
    assert_eq!(
        offset_of!(bg_docking_pose_validity_candidate_batch_soa_v1, reserved),
        104
    );
    assert_eq!(size_of::<bg_docking_pose_validity_row_v1>(), 240);
    assert_eq!(
        offset_of!(bg_docking_pose_validity_row_v1, passed_check_mask),
        16
    );
    assert_eq!(
        offset_of!(bg_docking_pose_validity_row_v1, observed_count),
        24
    );
    assert_eq!(offset_of!(bg_docking_pose_validity_row_v1, atom_count), 32);
    assert_eq!(
        offset_of!(
            bg_docking_pose_validity_row_v1,
            rotation_orthogonality_max_error
        ),
        40
    );
    assert_eq!(offset_of!(bg_docking_pose_validity_row_v1, reserved), 208);
    assert_eq!(size_of::<bg_docking_pose_validity_output_v1>(), 72);
    assert_eq!(offset_of!(bg_docking_pose_validity_output_v1, rows), 32);
    assert_eq!(offset_of!(bg_docking_pose_validity_output_v1, reserved), 40);
}

#[test]
fn docking_scorer_v1_layouts_match_the_c_header() {
    assert_eq!(size_of::<bg_docking_scorer_v1_context_soa_v1>(), 608);
    assert_eq!(align_of::<bg_docking_scorer_v1_context_soa_v1>(), 8);
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, unit_system),
        8
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, receptor_atom_count),
        16
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, receptor_x_angstrom),
        32
    );
    assert_eq!(
        offset_of!(
            bg_docking_scorer_v1_context_soa_v1,
            ligand_reference_x_angstrom
        ),
        96
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, receptor_donor_count),
        160
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, ligand_exclusion_count),
        208
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, rotor_count),
        232
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, pocket_center_angstrom),
        272
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, weights),
        304
    );
    assert_eq!(
        offset_of!(
            bg_docking_scorer_v1_context_soa_v1,
            max_receptor_candidate_pairs
        ),
        400
    );
    assert_eq!(
        offset_of!(
            bg_docking_scorer_v1_context_soa_v1,
            authority_input_receipt_sha256
        ),
        416
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_context_soa_v1, reserved),
        544
    );

    assert_eq!(size_of::<bg_docking_scorer_v1_candidate_batch_soa_v1>(), 96);
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_candidate_batch_soa_v1, candidate_count),
        8
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_candidate_batch_soa_v1, candidate_state),
        32
    );
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_candidate_batch_soa_v1, reserved),
        64
    );

    assert_eq!(size_of::<bg_docking_scorer_v1_row_v1>(), 160);
    assert_eq!(offset_of!(bg_docking_scorer_v1_row_v1, weighted_terms), 16);
    assert_eq!(offset_of!(bg_docking_scorer_v1_row_v1, total_score), 80);
    assert_eq!(
        offset_of!(bg_docking_scorer_v1_row_v1, receptor_candidate_pair_count),
        88
    );
    assert_eq!(offset_of!(bg_docking_scorer_v1_row_v1, reserved), 128);

    assert_eq!(size_of::<bg_docking_scorer_v1_output_v1>(), 72);
    assert_eq!(offset_of!(bg_docking_scorer_v1_output_v1, row_capacity), 8);
    assert_eq!(offset_of!(bg_docking_scorer_v1_output_v1, rows), 32);
    assert_eq!(offset_of!(bg_docking_scorer_v1_output_v1, reserved), 40);
}

#[test]
fn context_options_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_context_options>(), 64);
    assert_eq!(align_of::<bg_context_options>(), align_of::<u64>());
    assert_eq!(offset_of!(bg_context_options, struct_size), 0);
    assert_eq!(offset_of!(bg_context_options, abi_version), 4);
    assert_eq!(offset_of!(bg_context_options, backend), 8);
    assert_eq!(offset_of!(bg_context_options, unit_system), 12);
    assert_eq!(offset_of!(bg_context_options, device_ordinal), 16);
    assert_eq!(offset_of!(bg_context_options, reserved0), 20);
    assert_eq!(offset_of!(bg_context_options, flags), 24);
    assert_eq!(offset_of!(bg_context_options, reserved), 32);
}

#[cfg(target_pointer_width = "64")]
#[test]
fn particle_soa_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_particle_soa>(), 120);
    assert_eq!(align_of::<bg_particle_soa>(), 8);
    assert_eq!(offset_of!(bg_particle_soa, struct_size), 0);
    assert_eq!(offset_of!(bg_particle_soa, abi_version), 4);
    assert_eq!(offset_of!(bg_particle_soa, particle_count), 8);
    assert_eq!(offset_of!(bg_particle_soa, unit_system), 16);
    assert_eq!(offset_of!(bg_particle_soa, reserved0), 20);
    assert_eq!(offset_of!(bg_particle_soa, position_x_angstrom), 24);
    assert_eq!(offset_of!(bg_particle_soa, position_y_angstrom), 32);
    assert_eq!(offset_of!(bg_particle_soa, position_z_angstrom), 40);
    assert_eq!(
        offset_of!(bg_particle_soa, velocity_x_angstrom_per_femtosecond),
        48
    );
    assert_eq!(
        offset_of!(bg_particle_soa, velocity_y_angstrom_per_femtosecond),
        56
    );
    assert_eq!(
        offset_of!(bg_particle_soa, velocity_z_angstrom_per_femtosecond),
        64
    );
    assert_eq!(offset_of!(bg_particle_soa, mass_dalton), 72);
    assert_eq!(offset_of!(bg_particle_soa, charge_elementary), 80);
    assert_eq!(offset_of!(bg_particle_soa, reserved), 88);

    assert_eq!(size_of::<bg_particle_soa_view>(), 120);
    assert_eq!(align_of::<bg_particle_soa_view>(), 8);
    assert_eq!(offset_of!(bg_particle_soa_view, particle_count), 8);
    assert_eq!(offset_of!(bg_particle_soa_view, position_x_angstrom), 24);
    assert_eq!(offset_of!(bg_particle_soa_view, charge_elementary), 80);
    assert_eq!(offset_of!(bg_particle_soa_view, reserved), 88);
}

#[cfg(target_pointer_width = "64")]
#[test]
fn position_soa_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_position_soa>(), 80);
    assert_eq!(align_of::<bg_position_soa>(), 8);
    assert_eq!(offset_of!(bg_position_soa, struct_size), 0);
    assert_eq!(offset_of!(bg_position_soa, abi_version), 4);
    assert_eq!(offset_of!(bg_position_soa, particle_count), 8);
    assert_eq!(offset_of!(bg_position_soa, unit_system), 16);
    assert_eq!(offset_of!(bg_position_soa, reserved0), 20);
    assert_eq!(offset_of!(bg_position_soa, x_angstrom), 24);
    assert_eq!(offset_of!(bg_position_soa, y_angstrom), 32);
    assert_eq!(offset_of!(bg_position_soa, z_angstrom), 40);
    assert_eq!(offset_of!(bg_position_soa, reserved), 48);
}

#[cfg(target_pointer_width = "64")]
#[test]
fn forcefield_soa_v1_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_forcefield_soa_v1>(), 352);
    assert_eq!(align_of::<bg_forcefield_soa_v1>(), 8);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, struct_size), 0);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, abi_version), 4);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, atom_count), 8);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, unit_system), 16);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, periodic_axes_mask), 20);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, sigma_angstrom), 24);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, epsilon_kcal_per_mol), 32);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, bond_count), 40);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, bond_atom_i), 48);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, bond_atom_j), 56);
    assert_eq!(
        offset_of!(bg_forcefield_soa_v1, bond_equilibrium_angstrom),
        64
    );
    assert_eq!(
        offset_of!(
            bg_forcefield_soa_v1,
            bond_force_constant_kcal_per_mol_angstrom2
        ),
        72
    );
    assert_eq!(offset_of!(bg_forcefield_soa_v1, angle_count), 80);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, angle_atom_i), 88);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, angle_atom_j), 96);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, angle_atom_k), 104);
    assert_eq!(
        offset_of!(bg_forcefield_soa_v1, angle_equilibrium_radians),
        112
    );
    assert_eq!(
        offset_of!(
            bg_forcefield_soa_v1,
            angle_force_constant_kcal_per_mol_radian2
        ),
        120
    );
    assert_eq!(offset_of!(bg_forcefield_soa_v1, torsion_count), 128);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, torsion_atom_i), 136);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, torsion_atom_j), 144);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, torsion_atom_k), 152);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, torsion_atom_l), 160);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, torsion_periodicity), 168);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, torsion_phase_radians), 176);
    assert_eq!(
        offset_of!(bg_forcefield_soa_v1, torsion_amplitude_kcal_per_mol),
        184
    );
    assert_eq!(offset_of!(bg_forcefield_soa_v1, exclusion_count), 192);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, exclusion_atom_i), 200);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, exclusion_atom_j), 208);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, pair_scale_count), 216);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, pair_scale_atom_i), 224);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, pair_scale_atom_j), 232);
    assert_eq!(
        offset_of!(bg_forcefield_soa_v1, pair_scale_lennard_jones),
        240
    );
    assert_eq!(offset_of!(bg_forcefield_soa_v1, pair_scale_coulomb), 248);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, cell_lengths_angstrom), 256);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, cutoff_angstrom), 280);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, switch_start_angstrom), 288);
    assert_eq!(offset_of!(bg_forcefield_soa_v1, dielectric), 296);
    assert_eq!(
        offset_of!(bg_forcefield_soa_v1, screening_kappa_per_angstrom),
        304
    );
    assert_eq!(
        offset_of!(bg_forcefield_soa_v1, minimum_pair_distance_angstrom),
        312
    );
    assert_eq!(offset_of!(bg_forcefield_soa_v1, reserved), 320);
}

#[cfg(target_pointer_width = "64")]
#[test]
fn force_soa_v1_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_force_soa_v1>(), 88);
    assert_eq!(align_of::<bg_force_soa_v1>(), 8);
    assert_eq!(offset_of!(bg_force_soa_v1, struct_size), 0);
    assert_eq!(offset_of!(bg_force_soa_v1, abi_version), 4);
    assert_eq!(offset_of!(bg_force_soa_v1, particle_capacity), 8);
    assert_eq!(offset_of!(bg_force_soa_v1, particle_count), 16);
    assert_eq!(offset_of!(bg_force_soa_v1, unit_system), 24);
    assert_eq!(offset_of!(bg_force_soa_v1, reserved0), 28);
    assert_eq!(offset_of!(bg_force_soa_v1, x_kcal_per_mol_angstrom), 32);
    assert_eq!(offset_of!(bg_force_soa_v1, y_kcal_per_mol_angstrom), 40);
    assert_eq!(offset_of!(bg_force_soa_v1, z_kcal_per_mol_angstrom), 48);
    assert_eq!(offset_of!(bg_force_soa_v1, reserved), 56);
}

#[test]
fn energy_components_v1_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_energy_components_v1>(), 96);
    assert_eq!(align_of::<bg_energy_components_v1>(), align_of::<u64>());
    assert_eq!(offset_of!(bg_energy_components_v1, struct_size), 0);
    assert_eq!(offset_of!(bg_energy_components_v1, abi_version), 4);
    assert_eq!(offset_of!(bg_energy_components_v1, unit_system), 8);
    assert_eq!(offset_of!(bg_energy_components_v1, reserved0), 12);
    assert_eq!(
        offset_of!(bg_energy_components_v1, harmonic_bond_kcal_per_mol),
        16
    );
    assert_eq!(
        offset_of!(bg_energy_components_v1, harmonic_angle_kcal_per_mol),
        24
    );
    assert_eq!(
        offset_of!(bg_energy_components_v1, periodic_torsion_kcal_per_mol),
        32
    );
    assert_eq!(
        offset_of!(bg_energy_components_v1, lennard_jones_kcal_per_mol),
        40
    );
    assert_eq!(
        offset_of!(bg_energy_components_v1, coulomb_kcal_per_mol),
        48
    );
    assert_eq!(offset_of!(bg_energy_components_v1, total_kcal_per_mol), 56);
    assert_eq!(offset_of!(bg_energy_components_v1, reserved), 64);
}

#[cfg(target_pointer_width = "64")]
#[test]
fn distance_constraints_v1_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_distance_constraints_v1>(), 104);
    assert_eq!(align_of::<bg_distance_constraints_v1>(), 8);
    assert_eq!(offset_of!(bg_distance_constraints_v1, struct_size), 0);
    assert_eq!(offset_of!(bg_distance_constraints_v1, abi_version), 4);
    assert_eq!(offset_of!(bg_distance_constraints_v1, constraint_count), 8);
    assert_eq!(offset_of!(bg_distance_constraints_v1, unit_system), 16);
    assert_eq!(offset_of!(bg_distance_constraints_v1, reserved0), 20);
    assert_eq!(offset_of!(bg_distance_constraints_v1, atom_i), 24);
    assert_eq!(offset_of!(bg_distance_constraints_v1, atom_j), 32);
    assert_eq!(
        offset_of!(bg_distance_constraints_v1, distance_angstrom),
        40
    );
    assert_eq!(
        offset_of!(bg_distance_constraints_v1, tolerance_angstrom),
        48
    );
    assert_eq!(
        offset_of!(
            bg_distance_constraints_v1,
            velocity_tolerance_angstrom_per_femtosecond
        ),
        56
    );
    assert_eq!(offset_of!(bg_distance_constraints_v1, max_iterations), 64);
    assert_eq!(offset_of!(bg_distance_constraints_v1, reserved1), 68);
    assert_eq!(offset_of!(bg_distance_constraints_v1, reserved), 72);
}

#[test]
fn simulation_options_v1_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_simulation_options_v1>(), 80);
    assert_eq!(align_of::<bg_simulation_options_v1>(), 8);
    assert_eq!(offset_of!(bg_simulation_options_v1, struct_size), 0);
    assert_eq!(offset_of!(bg_simulation_options_v1, abi_version), 4);
    assert_eq!(offset_of!(bg_simulation_options_v1, unit_system), 8);
    assert_eq!(offset_of!(bg_simulation_options_v1, integrator), 12);
    assert_eq!(
        offset_of!(bg_simulation_options_v1, timestep_femtoseconds),
        16
    );
    assert_eq!(offset_of!(bg_simulation_options_v1, temperature_kelvin), 24);
    assert_eq!(
        offset_of!(bg_simulation_options_v1, friction_per_femtosecond),
        32
    );
    assert_eq!(offset_of!(bg_simulation_options_v1, random_seed), 40);
    assert_eq!(offset_of!(bg_simulation_options_v1, reserved), 48);
}

#[test]
fn minimizer_options_v1_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_minimizer_options_v1>(), 112);
    assert_eq!(align_of::<bg_minimizer_options_v1>(), 8);
    assert_eq!(offset_of!(bg_minimizer_options_v1, struct_size), 0);
    assert_eq!(offset_of!(bg_minimizer_options_v1, abi_version), 4);
    assert_eq!(offset_of!(bg_minimizer_options_v1, unit_system), 8);
    assert_eq!(offset_of!(bg_minimizer_options_v1, reserved0), 12);
    assert_eq!(offset_of!(bg_minimizer_options_v1, max_iterations), 16);
    assert_eq!(
        offset_of!(bg_minimizer_options_v1, max_line_search_steps),
        24
    );
    assert_eq!(offset_of!(bg_minimizer_options_v1, reserved1), 28);
    assert_eq!(
        offset_of!(bg_minimizer_options_v1, initial_step_angstrom2_mol_per_kcal),
        32
    );
    assert_eq!(
        offset_of!(bg_minimizer_options_v1, minimum_step_angstrom2_mol_per_kcal),
        40
    );
    assert_eq!(
        offset_of!(bg_minimizer_options_v1, energy_tolerance_kcal_per_mol),
        48
    );
    assert_eq!(
        offset_of!(
            bg_minimizer_options_v1,
            force_tolerance_kcal_per_mol_angstrom
        ),
        56
    );
    assert_eq!(offset_of!(bg_minimizer_options_v1, armijo_coefficient), 64);
    assert_eq!(offset_of!(bg_minimizer_options_v1, backtrack_factor), 72);
    assert_eq!(offset_of!(bg_minimizer_options_v1, reserved), 80);
}

#[test]
fn dynamics_report_layouts_match_the_c_header() {
    assert_eq!(size_of::<bg_minimization_report_v1>(), 88);
    assert_eq!(align_of::<bg_minimization_report_v1>(), 8);
    assert_eq!(offset_of!(bg_minimization_report_v1, iterations), 16);
    assert_eq!(offset_of!(bg_minimization_report_v1, converged), 24);
    assert_eq!(
        offset_of!(bg_minimization_report_v1, initial_potential_kcal_per_mol),
        32
    );
    assert_eq!(
        offset_of!(bg_minimization_report_v1, final_potential_kcal_per_mol),
        40
    );
    assert_eq!(
        offset_of!(
            bg_minimization_report_v1,
            maximum_force_kcal_per_mol_angstrom
        ),
        48
    );
    assert_eq!(offset_of!(bg_minimization_report_v1, reserved), 56);

    assert_eq!(size_of::<bg_dynamics_report_v1>(), 104);
    assert_eq!(align_of::<bg_dynamics_report_v1>(), 8);
    assert_eq!(offset_of!(bg_dynamics_report_v1, steps_completed), 16);
    assert_eq!(offset_of!(bg_dynamics_report_v1, absolute_step), 24);
    assert_eq!(offset_of!(bg_dynamics_report_v1, degrees_of_freedom), 32);
    assert_eq!(
        offset_of!(bg_dynamics_report_v1, potential_kcal_per_mol),
        40
    );
    assert_eq!(offset_of!(bg_dynamics_report_v1, kinetic_kcal_per_mol), 48);
    assert_eq!(offset_of!(bg_dynamics_report_v1, total_kcal_per_mol), 56);
    assert_eq!(offset_of!(bg_dynamics_report_v1, temperature_kelvin), 64);
    assert_eq!(offset_of!(bg_dynamics_report_v1, reserved), 72);
}

#[test]
fn opaque_handles_are_only_used_behind_pointers() {
    assert_eq!(size_of::<*mut bg_context>(), size_of::<usize>());
    assert_eq!(size_of::<*mut bg_system>(), size_of::<usize>());
    assert_eq!(size_of::<*mut bg_forcefield>(), size_of::<usize>());
    assert_eq!(size_of::<*mut bg_simulation>(), size_of::<usize>());
    assert_eq!(size_of::<*mut bg_docking_scorer_v1>(), size_of::<usize>());
    assert_eq!(
        size_of::<*mut bg_docking_pose_validity_v1>(),
        size_of::<usize>()
    );
    assert_eq!(
        size_of::<*mut bg_docking_stable_top_k_v1>(),
        size_of::<usize>()
    );
    assert_eq!(
        size_of::<*mut bg_docking_fixed64_downstream_v1>(),
        size_of::<usize>()
    );
    assert_eq!(
        size_of::<*mut bg_docking_fixed64_refinement_pipeline_v1>(),
        size_of::<usize>()
    );
    assert_eq!(
        size_of::<*mut bg_docking_rigid_refinement>(),
        size_of::<usize>()
    );
    assert_eq!(size_of::<*mut bg_docking_torsion_v7>(), size_of::<usize>());
}
