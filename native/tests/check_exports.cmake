if(NOT DEFINED NM OR NOT DEFINED LIBRARY)
    message(FATAL_ERROR "NM and LIBRARY are required")
endif()

execute_process(
    COMMAND "${NM}" -D --defined-only "${LIBRARY}"
    RESULT_VARIABLE nm_result
    OUTPUT_VARIABLE nm_output
    ERROR_VARIABLE nm_error
)
if(NOT nm_result EQUAL 0)
    message(FATAL_ERROR "nm failed (${nm_result}): ${nm_error}")
endif()

string(REPLACE "\n" ";" nm_lines "${nm_output}")
set(v1_1_symbols
    bg_forcefield_soa_v1_init
    bg_force_soa_v1_init
    bg_energy_components_v1_init
    bg_forcefield_create
    bg_forcefield_destroy
    bg_forcefield_get_atom_count
    bg_context_evaluate
)
set(v1_3_symbols
    bg_distance_constraints_v1_init
    bg_simulation_options_v1_init
    bg_minimizer_options_v1_init
    bg_minimization_report_v1_init
    bg_dynamics_report_v1_init
    bg_simulation_create
    bg_simulation_destroy
    bg_simulation_get_particles
    bg_simulation_get_absolute_step
    bg_context_minimize
    bg_context_integrate
    bg_simulation_checkpoint_size
    bg_simulation_checkpoint_write
    bg_simulation_checkpoint_load
)
set(v1_5_symbols
    bg_docking_scorer_v1_context_soa_v1_init
    bg_docking_scorer_v1_candidate_batch_soa_v1_init
    bg_docking_scorer_v1_output_v1_init
    bg_docking_scorer_v1_create
    bg_docking_scorer_v1_destroy
    bg_docking_scorer_v1_get_backend
    bg_docking_scorer_v1_score_fixed64
)
set(v1_6_symbols
    bg_docking_pose_validity_context_soa_v1_init
    bg_docking_pose_validity_candidate_batch_soa_v1_init
    bg_docking_pose_validity_output_v1_init
    bg_docking_pose_validity_v1_create
    bg_docking_pose_validity_v1_destroy
    bg_docking_pose_validity_v1_get_backend
    bg_docking_pose_validity_v1_evaluate_fixed64
)
set(v1_7_symbols
    bg_docking_stable_top_k_input_v1_init
    bg_docking_stable_top_k_output_v1_init
    bg_docking_stable_top_k_v1_create
    bg_docking_stable_top_k_v1_destroy
    bg_docking_stable_top_k_v1_get_backend
    bg_docking_stable_top_k_v1_rank_fixed64
)
set(v1_8_symbols
    bg_docking_rmsd_cluster_input_v1_init
    bg_docking_rmsd_cluster_output_v1_init
    bg_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64
)
set(v1_9_symbols
    bg_docking_torsion_v7_context_soa_v1_init
    bg_docking_torsion_v7_candidate_batch_soa_v1_init
    bg_docking_torsion_v7_output_v1_init
    bg_docking_torsion_v7_create
    bg_docking_torsion_v7_destroy
    bg_docking_torsion_v7_get_backend
    bg_docking_torsion_v7_refine_fixed64
)
set(v1_10_symbols
    bg_docking_rigid_refinement_context_soa_v1_init
    bg_docking_rigid_refinement_candidate_batch_soa_v1_init
    bg_docking_rigid_refinement_output_v1_init
    bg_docking_rigid_refinement_create
    bg_docking_rigid_refinement_destroy
    bg_docking_rigid_refinement_get_backend
    bg_docking_rigid_refinement_fixed64
)
set(v1_11_symbols
    bg_docking_fixed64_downstream_v1_create
    bg_docking_fixed64_downstream_v1_destroy
    bg_docking_fixed64_downstream_v1_get_backend
    bg_docking_fixed64_downstream_v1_run
)
set(v1_12_symbols
    bg_docking_fixed64_refinement_input_v1_init
    bg_docking_fixed64_refinement_output_v1_init
    bg_docking_fixed64_refinement_pipeline_v1_create
    bg_docking_fixed64_refinement_pipeline_v1_destroy
    bg_docking_fixed64_refinement_pipeline_v1_get_backend
    bg_docking_fixed64_refinement_pipeline_v1_run
)
set(v1_13_symbols
    bg_docking_geometric_admission_context_soa_v1_init
    bg_docking_geometric_admission_candidate_batch_soa_v1_init
    bg_docking_geometric_admission_output_v1_init
    bg_docking_geometric_admission_v1_create
    bg_docking_geometric_admission_v1_destroy
    bg_docking_geometric_admission_v1_get_backend
    bg_docking_geometric_admission_v1_evaluate_fixed64
)
set(v1_14_symbols
    bg_docking_fixed64_allocation_input_v1_init
    bg_docking_fixed64_allocation_output_v1_init
    bg_docking_fixed64_allocation_v1_build
)
set(v1_15_symbols
    bg_docking_fixed64_so3_input_v1_init
    bg_docking_fixed64_so3_output_v1_init
    bg_docking_fixed64_so3_v1_generate
)
set(v1_16_symbols
    bg_docking_fixed64_indexed_so3_input_v1_init
    bg_docking_fixed64_indexed_so3_output_v1_init
    bg_docking_fixed64_indexed_so3_v1_place
)
set(v1_17_symbols
    bg_docking_fixed64_single_anchor_input_v1_init
    bg_docking_fixed64_single_anchor_output_v1_init
    bg_docking_fixed64_single_anchor_v1_place
)
set(v1_18_symbols
    bg_docking_fixed64_producer_input_v1_init
    bg_docking_fixed64_producer_output_v1_init
    bg_docking_fixed64_producer_v1_run
)
set(v1_19_symbols
    bg_docking_fixed64_producer_v1_profile_id
)
set(v1_20_symbols
    bg_docking_fixed64_pipeline_input_v1_init
    bg_docking_fixed64_pipeline_output_v1_init
    bg_docking_fixed64_pipeline_v1_create
    bg_docking_fixed64_pipeline_v1_destroy
    bg_docking_fixed64_pipeline_v1_get_backend
    bg_docking_fixed64_pipeline_v1_profile_id
    bg_docking_fixed64_pipeline_v1_run
)
set(v1_21_symbols
    bg_docking_fixed64_pipeline_input_v2_init
    bg_docking_fixed64_pipeline_output_v2_init
    bg_docking_fixed64_pipeline_v2_create
    bg_docking_fixed64_pipeline_v2_destroy
    bg_docking_fixed64_pipeline_v2_get_backend
    bg_docking_fixed64_pipeline_v2_profile_id
    bg_docking_fixed64_pipeline_v2_run
)
foreach(line IN LISTS nm_lines)
    if(line STREQUAL "")
        continue()
    endif()
    string(REGEX MATCH "[^ 	]+$" symbol "${line}")
    string(REGEX REPLACE "@@.*$" "" unversioned "${symbol}")
    if(NOT unversioned MATCHES "^bg_" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.0" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.1" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.3" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.5" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.6" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.7" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.8" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.9" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.10" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.11" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.12" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.13" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.14" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.15" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.16" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.17" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.18" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.19" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.20" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.21")
        message(FATAL_ERROR "unexpected exported symbol: ${symbol}")
    endif()
    if(unversioned MATCHES "^bg_")
        list(FIND v1_21_symbols "${unversioned}" v1_21_index)
        list(FIND v1_20_symbols "${unversioned}" v1_20_index)
        list(FIND v1_19_symbols "${unversioned}" v1_19_index)
        list(FIND v1_18_symbols "${unversioned}" v1_18_index)
        list(FIND v1_17_symbols "${unversioned}" v1_17_index)
        list(FIND v1_16_symbols "${unversioned}" v1_16_index)
        list(FIND v1_15_symbols "${unversioned}" v1_15_index)
        list(FIND v1_14_symbols "${unversioned}" v1_14_index)
        list(FIND v1_13_symbols "${unversioned}" v1_13_index)
        list(FIND v1_12_symbols "${unversioned}" v1_12_index)
        list(FIND v1_11_symbols "${unversioned}" v1_11_index)
        list(FIND v1_10_symbols "${unversioned}" v1_10_index)
        list(FIND v1_9_symbols "${unversioned}" v1_9_index)
        list(FIND v1_8_symbols "${unversioned}" v1_8_index)
        list(FIND v1_7_symbols "${unversioned}" v1_7_index)
        list(FIND v1_6_symbols "${unversioned}" v1_6_index)
        list(FIND v1_5_symbols "${unversioned}" v1_5_index)
        list(FIND v1_3_symbols "${unversioned}" v1_3_index)
        list(FIND v1_1_symbols "${unversioned}" v1_1_index)
        if(NOT v1_21_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.21")
        elseif(NOT v1_20_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.20")
        elseif(NOT v1_19_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.19")
        elseif(NOT v1_18_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.18")
        elseif(NOT v1_17_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.17")
        elseif(NOT v1_16_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.16")
        elseif(NOT v1_15_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.15")
        elseif(NOT v1_14_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.14")
        elseif(NOT v1_13_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.13")
        elseif(NOT v1_12_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.12")
        elseif(NOT v1_11_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.11")
        elseif(NOT v1_10_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.10")
        elseif(NOT v1_9_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.9")
        elseif(NOT v1_8_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.8")
        elseif(NOT v1_7_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.7")
        elseif(NOT v1_6_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.6")
        elseif(NOT v1_5_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.5")
        elseif(NOT v1_3_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.3")
        elseif(NOT v1_1_index EQUAL -1)
            set(expected_version "BETELGEUZE_ENGINE_1.1")
        else()
            set(expected_version "BETELGEUZE_ENGINE_1.0")
        endif()
        if(NOT symbol MATCHES "@@${expected_version}$")
            message(FATAL_ERROR
                "wrong symbol version for ${unversioned}: ${symbol}; "
                "expected ${expected_version}"
            )
        endif()
    endif()
endforeach()
