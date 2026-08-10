if(BG_ENABLE_HIP)
    set(BG_ENGINE_BACKEND_SOURCE src/hip/backend.hip)
else()
    set(BG_ENGINE_BACKEND_SOURCE src/hip/stub.cpp)
endif()

add_library(betelgeuze_engine SHARED
    src/context.cpp
    src/evaluator.cpp
    src/forcefield.cpp
    src/system.cpp
    src/cpu/evaluator.cpp
    ${BG_ENGINE_BACKEND_SOURCE}
)

target_compile_features(betelgeuze_engine PUBLIC cxx_std_17)
target_compile_definitions(betelgeuze_engine PRIVATE
    BG_ENGINE_BUILD_SHARED
    BG_ENABLE_HIP=$<BOOL:${BG_ENABLE_HIP}>
)
target_include_directories(betelgeuze_engine
    PUBLIC
        $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)
set_target_properties(betelgeuze_engine PROPERTIES
    CXX_EXTENSIONS OFF
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
    OUTPUT_NAME betelgeuze_engine
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
)
if(BG_ENABLE_HIP)
    set_target_properties(betelgeuze_engine PROPERTIES
        HIP_STANDARD 17
        HIP_STANDARD_REQUIRED YES
        HIP_EXTENSIONS OFF
    )
endif()

if(UNIX AND NOT APPLE AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_link_options(betelgeuze_engine PRIVATE
        "LINKER:--version-script=${CMAKE_CURRENT_SOURCE_DIR}/betelgeuze_engine.map"
    )
    set_property(TARGET betelgeuze_engine APPEND PROPERTY
        LINK_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/betelgeuze_engine.map
    )
endif()

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(betelgeuze_engine PRIVATE
        "$<$<COMPILE_LANGUAGE:CXX>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wsign-conversion;-Werror;-ffp-contract=off;-fno-fast-math>"
    )
elseif(MSVC)
    target_compile_options(betelgeuze_engine PRIVATE
        "$<$<COMPILE_LANGUAGE:CXX>:/W4;/WX;/fp:strict>"
    )
endif()

if(BG_ENABLE_HIP)
    # Match the CPU evaluator's strict binary64 contract.  Architecture
    # selection intentionally comes from CMAKE_HIP_ARCHITECTURES/toolchains.
    target_compile_options(betelgeuze_engine PRIVATE
        "$<$<COMPILE_LANGUAGE:HIP>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wsign-conversion;-Werror;-ffp-contract=off;-fno-fast-math>"
    )
endif()

include(GNUInstallDirs)
install(TARGETS betelgeuze_engine
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
install(
    FILES ${PROJECT_SOURCE_DIR}/include/betelgeuze/engine.h
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/betelgeuze
)

if(BUILD_TESTING)
    add_executable(betelgeuze_engine_c_smoke tests/c_smoke.c)
    target_link_libraries(betelgeuze_engine_c_smoke PRIVATE betelgeuze_engine)
    target_compile_definitions(betelgeuze_engine_c_smoke PRIVATE
        BG_TEST_HIP_ENABLED=$<BOOL:${BG_ENABLE_HIP}>
    )
    set_target_properties(betelgeuze_engine_c_smoke PROPERTIES LINKER_LANGUAGE CXX)
    set_target_properties(betelgeuze_engine_c_smoke PROPERTIES
        C_STANDARD 11
        C_STANDARD_REQUIRED YES
        C_EXTENSIONS NO
    )
    if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(betelgeuze_engine_c_smoke PRIVATE
            -Wall
            -Wextra
            -Wpedantic
            -Werror
            -UNDEBUG
        )
    elseif(MSVC)
        target_compile_options(betelgeuze_engine_c_smoke PRIVATE /UNDEBUG)
    endif()
    add_test(NAME betelgeuze_engine_c_smoke COMMAND betelgeuze_engine_c_smoke)

    add_executable(betelgeuze_engine_cpp_smoke tests/cpp_smoke.cpp)
    target_link_libraries(betelgeuze_engine_cpp_smoke PRIVATE betelgeuze_engine)
    target_compile_features(betelgeuze_engine_cpp_smoke PRIVATE cxx_std_17)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(betelgeuze_engine_cpp_smoke PRIVATE
            -Wall
            -Wextra
            -Wpedantic
            -Werror
            -UNDEBUG
        )
    elseif(MSVC)
        target_compile_options(betelgeuze_engine_cpp_smoke PRIVATE /UNDEBUG)
    endif()
    add_test(NAME betelgeuze_engine_cpp_smoke COMMAND betelgeuze_engine_cpp_smoke)

    add_executable(
        betelgeuze_engine_cpu_evaluator
        tests/cpu_evaluator.cpp
    )
    target_link_libraries(
        betelgeuze_engine_cpu_evaluator
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_cpu_evaluator
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(betelgeuze_engine_cpu_evaluator PRIVATE
            -Wall
            -Wextra
            -Wpedantic
            -Wconversion
            -Wsign-conversion
            -Werror
            -UNDEBUG
            -ffp-contract=off
            -fno-fast-math
        )
    elseif(MSVC)
        target_compile_options(
            betelgeuze_engine_cpu_evaluator
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_cpu_evaluator
        COMMAND betelgeuze_engine_cpu_evaluator
    )

    if(BG_ENABLE_HIP)
        foreach(BG_HIP_TEST IN ITEMS hip_evaluator hip_error_rows)
            if(BG_HIP_TEST STREQUAL "hip_error_rows")
                # This test calls the HIP runtime directly.  Compiling it as a
                # HIP translation unit obtains runtime headers/linkage from
                # CMake's HIP language without an installation-specific path.
                set_source_files_properties(
                    tests/${BG_HIP_TEST}.cpp
                    PROPERTIES LANGUAGE HIP
                )
            endif()
            add_executable(
                betelgeuze_engine_${BG_HIP_TEST}
                tests/${BG_HIP_TEST}.cpp
            )
            target_link_libraries(
                betelgeuze_engine_${BG_HIP_TEST}
                PRIVATE betelgeuze_engine
            )
            target_include_directories(
                betelgeuze_engine_${BG_HIP_TEST}
                PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src
            )
            target_compile_features(
                betelgeuze_engine_${BG_HIP_TEST}
                PRIVATE cxx_std_17
            )
            set_target_properties(
                betelgeuze_engine_${BG_HIP_TEST}
                PROPERTIES
                    HIP_STANDARD 17
                    HIP_STANDARD_REQUIRED YES
                    HIP_EXTENSIONS OFF
            )
            if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
                target_compile_options(
                    betelgeuze_engine_${BG_HIP_TEST}
                    PRIVATE
                        "$<$<COMPILE_LANGUAGE:CXX>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wsign-conversion;-Werror;-UNDEBUG;-ffp-contract=off;-fno-fast-math>"
                )
            elseif(MSVC)
                target_compile_options(
                    betelgeuze_engine_${BG_HIP_TEST}
                    PRIVATE
                        "$<$<COMPILE_LANGUAGE:CXX>:/W4;/WX;/UNDEBUG;/fp:strict>"
                )
            endif()
            target_compile_options(
                betelgeuze_engine_${BG_HIP_TEST}
                PRIVATE
                    "$<$<COMPILE_LANGUAGE:HIP>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wsign-conversion;-Werror;-UNDEBUG;-ffp-contract=off;-fno-fast-math>"
            )
            add_test(
                NAME betelgeuze_engine_${BG_HIP_TEST}
                COMMAND betelgeuze_engine_${BG_HIP_TEST}
            )
            set_tests_properties(
                betelgeuze_engine_${BG_HIP_TEST}
                PROPERTIES
                    SKIP_RETURN_CODE 77
                    RESOURCE_LOCK betelgeuze_hip_device_0
            )
        endforeach()

        # Internal tests need hidden HIP diagnostics or test-only allocator
        # controls.  Give each an isolated engine copy so those hooks never
        # become part of the shared library's exported product surface.
        function(bg_add_hip_internal_engine_test TEST_NAME)
            set(BG_HIP_INTERNAL_TARGET betelgeuze_engine_${TEST_NAME})
            add_executable(
                ${BG_HIP_INTERNAL_TARGET}
                tests/${TEST_NAME}.cpp
                src/context.cpp
                src/evaluator.cpp
                src/forcefield.cpp
                src/system.cpp
                src/cpu/evaluator.cpp
                src/hip/backend.hip
            )
            target_compile_definitions(
                ${BG_HIP_INTERNAL_TARGET}
                PRIVATE BG_ENABLE_HIP=1
            )
            target_include_directories(
                ${BG_HIP_INTERNAL_TARGET}
                PRIVATE
                    ${PROJECT_SOURCE_DIR}/include
                    ${CMAKE_CURRENT_SOURCE_DIR}/src
            )
            target_compile_features(
                ${BG_HIP_INTERNAL_TARGET}
                PRIVATE cxx_std_17
            )
            set_target_properties(
                ${BG_HIP_INTERNAL_TARGET}
                PROPERTIES
                    CXX_EXTENSIONS OFF
                    HIP_STANDARD 17
                    HIP_STANDARD_REQUIRED YES
                    HIP_EXTENSIONS OFF
            )
            if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
                target_compile_options(
                    ${BG_HIP_INTERNAL_TARGET}
                    PRIVATE
                        "$<$<COMPILE_LANGUAGE:CXX>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wsign-conversion;-Werror;-UNDEBUG;-ffp-contract=off;-fno-fast-math>"
                )
            elseif(MSVC)
                target_compile_options(
                    ${BG_HIP_INTERNAL_TARGET}
                    PRIVATE
                        "$<$<COMPILE_LANGUAGE:CXX>:/W4;/WX;/UNDEBUG;/fp:strict>"
                )
            endif()
            target_compile_options(
                ${BG_HIP_INTERNAL_TARGET}
                PRIVATE
                    "$<$<COMPILE_LANGUAGE:HIP>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wsign-conversion;-Werror;-UNDEBUG;-ffp-contract=off;-fno-fast-math>"
            )
            add_test(
                NAME ${BG_HIP_INTERNAL_TARGET}
                COMMAND ${BG_HIP_INTERNAL_TARGET}
            )
            set_tests_properties(
                ${BG_HIP_INTERNAL_TARGET}
                PROPERTIES
                    SKIP_RETURN_CODE 77
                    RESOURCE_LOCK betelgeuze_hip_device_0
            )
        endfunction()

        bg_add_hip_internal_engine_test(hip_fault_transactionality)
        target_compile_definitions(
            betelgeuze_engine_hip_fault_transactionality
            PRIVATE BG_HIP_TESTING=1
        )
        bg_add_hip_internal_engine_test(hip_pipeline_stats)
    endif()

    if(UNIX AND NOT APPLE AND CMAKE_NM)
        add_test(
            NAME betelgeuze_engine_export_allowlist
            COMMAND ${CMAKE_COMMAND}
                -DNM=${CMAKE_NM}
                -DLIBRARY=$<TARGET_FILE:betelgeuze_engine>
                -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/check_exports.cmake
        )
    endif()
endif()
