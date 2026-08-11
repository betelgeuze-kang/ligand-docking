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
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.6")
        message(FATAL_ERROR "unexpected exported symbol: ${symbol}")
    endif()
    if(unversioned MATCHES "^bg_")
        list(FIND v1_6_symbols "${unversioned}" v1_6_index)
        list(FIND v1_5_symbols "${unversioned}" v1_5_index)
        list(FIND v1_3_symbols "${unversioned}" v1_3_index)
        list(FIND v1_1_symbols "${unversioned}" v1_1_index)
        if(NOT v1_6_index EQUAL -1)
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
