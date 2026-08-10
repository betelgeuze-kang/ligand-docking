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
foreach(line IN LISTS nm_lines)
    if(line STREQUAL "")
        continue()
    endif()
    string(REGEX MATCH "[^ 	]+$" symbol "${line}")
    string(REGEX REPLACE "@@.*$" "" unversioned "${symbol}")
    if(NOT unversioned MATCHES "^bg_" AND
       NOT unversioned STREQUAL "BETELGEUZE_ENGINE_1.0")
        message(FATAL_ERROR "unexpected exported symbol: ${symbol}")
    endif()
endforeach()
