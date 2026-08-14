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
    src/hip/evaluator.cpp
    src/rust/evaluator.cpp
    src/docking/fixed64_allocation.cpp
    src/docking/fixed64_indexed_so3.cpp
    src/docking/fixed64_pipeline.cpp
    src/docking/fixed64_producer.cpp
    src/docking/fixed64_single_anchor.cpp
    src/docking/fixed64_so3.cpp
    src/docking/fixed64_downstream.cpp
    src/docking/fixed64_refinement_pipeline.cpp
    src/docking/geometric_admission.cpp
    src/docking/pose_validity.cpp
    src/docking/rigid_refinement.cpp
    src/docking/scorer_v1.cpp
    src/docking/stable_top_k.cpp
    src/docking/torsion_v7.cpp
    src/dynamics/api.cpp
    src/dynamics/checkpoint.cpp
    src/dynamics/common.cpp
    src/dynamics/integrator.cpp
    src/dynamics/sha256.cpp
    ${BG_ENGINE_BACKEND_SOURCE}
)

find_program(CARGO_EXECUTABLE cargo REQUIRED)
set(BG_RUST_CPU_TARGET_DIR
    "${CMAKE_CURRENT_BINARY_DIR}/rust-cpu-provider-target")
if(WIN32)
    set(BG_RUST_CPU_STATIC_LIBRARY
        "${BG_RUST_CPU_TARGET_DIR}/release/betelgeuze_cpu_kernel.lib")
else()
    set(BG_RUST_CPU_STATIC_LIBRARY
        "${BG_RUST_CPU_TARGET_DIR}/release/libbetelgeuze_cpu_kernel.a")
endif()
file(GLOB_RECURSE BG_RUST_CPU_SOURCES CONFIGURE_DEPENDS
    "${PROJECT_SOURCE_DIR}/rust/cpu-kernel/src/*.rs"
    "${PROJECT_SOURCE_DIR}/rust/betelgeuze-docking-search/src/*.rs")
add_custom_command(
    OUTPUT "${BG_RUST_CPU_STATIC_LIBRARY}"
    COMMAND ${CMAKE_COMMAND} -E env
        "CARGO_TARGET_DIR=${BG_RUST_CPU_TARGET_DIR}"
        "RUSTFLAGS=-C target-feature=-fma -C relocation-model=pic"
        ${CARGO_EXECUTABLE} build
        --manifest-path "${PROJECT_SOURCE_DIR}/rust/Cargo.toml"
        --package betelgeuze-cpu-kernel
        --release
        --locked
    DEPENDS
        "${PROJECT_SOURCE_DIR}/rust/Cargo.toml"
        "${PROJECT_SOURCE_DIR}/rust/Cargo.lock"
        "${PROJECT_SOURCE_DIR}/rust/cpu-kernel/Cargo.toml"
        "${PROJECT_SOURCE_DIR}/rust/betelgeuze-docking-search/Cargo.toml"
        ${BG_RUST_CPU_SOURCES}
    COMMENT "Building deterministic Rust CPU provider"
    VERBATIM
)
add_custom_target(
    betelgeuze_rust_cpu_provider_build
    DEPENDS "${BG_RUST_CPU_STATIC_LIBRARY}"
)
add_library(betelgeuze_rust_cpu_provider STATIC IMPORTED GLOBAL)
set_target_properties(betelgeuze_rust_cpu_provider PROPERTIES
    IMPORTED_LOCATION "${BG_RUST_CPU_STATIC_LIBRARY}"
)
add_dependencies(
    betelgeuze_rust_cpu_provider
    betelgeuze_rust_cpu_provider_build
)
add_dependencies(betelgeuze_engine betelgeuze_rust_cpu_provider_build)
target_link_libraries(betelgeuze_engine PRIVATE betelgeuze_rust_cpu_provider)

set(BG_ENABLE_HIP_SAFE "AUTO" CACHE STRING
    "Build the deterministic HIP provider: AUTO, ON, or OFF")
set_property(CACHE BG_ENABLE_HIP_SAFE PROPERTY STRINGS AUTO ON OFF)
set(BG_HIP_SAFE_ARCHITECTURES "gfx1030" CACHE STRING
    "Semicolon-separated AMD GPU targets compiled into hip_safe")
set(BG_HIP_DEVICE_LIB_PATH "" CACHE PATH
    "ROCm device-library bitcode directory used by hip_safe")
string(TOUPPER "${BG_ENABLE_HIP_SAFE}" BG_ENABLE_HIP_SAFE_NORMALIZED)
if(NOT BG_ENABLE_HIP_SAFE_NORMALIZED MATCHES "^(AUTO|ON|OFF)$")
    message(FATAL_ERROR "BG_ENABLE_HIP_SAFE must be AUTO, ON, or OFF")
endif()

set(_BG_ROCM_HINTS)
if(DEFINED ENV{ROCM_PATH} AND NOT "$ENV{ROCM_PATH}" STREQUAL "")
    list(APPEND _BG_ROCM_HINTS "$ENV{ROCM_PATH}")
endif()
if(DEFINED ENV{HIP_PATH} AND NOT "$ENV{HIP_PATH}" STREQUAL "")
    list(APPEND _BG_ROCM_HINTS "$ENV{HIP_PATH}")
endif()
list(APPEND _BG_ROCM_HINTS "/opt/rocm")
set(_BG_HIPCC_HINTS)
set(_BG_HIP_LIBRARY_HINTS)
foreach(_BG_ROCM_HINT IN LISTS _BG_ROCM_HINTS)
    list(APPEND _BG_HIPCC_HINTS "${_BG_ROCM_HINT}/bin")
    list(APPEND _BG_HIP_LIBRARY_HINTS
        "${_BG_ROCM_HINT}/lib"
        "${_BG_ROCM_HINT}/lib64")
endforeach()
find_program(BG_HIPCC_EXECUTABLE NAMES hipcc HINTS ${_BG_HIPCC_HINTS})
find_library(BG_AMDHIP64_LIBRARY NAMES amdhip64 HINTS ${_BG_HIP_LIBRARY_HINTS})

if(BG_HIPCC_EXECUTABLE)
    get_filename_component(_BG_HIPCC_BIN_DIR
        "${BG_HIPCC_EXECUTABLE}" DIRECTORY)
    get_filename_component(BG_HIP_ROCM_ROOT
        "${_BG_HIPCC_BIN_DIR}" DIRECTORY)
endif()
set(BG_HIP_SAFE_ROCM_RELEASE_MATCH FALSE)
if(BG_HIP_ROCM_ROOT AND
   EXISTS "${BG_HIP_ROCM_ROOT}/.info/version")
    file(READ "${BG_HIP_ROCM_ROOT}/.info/version"
        BG_HIP_ROCM_RELEASE_OBSERVED)
    string(STRIP "${BG_HIP_ROCM_RELEASE_OBSERVED}"
        BG_HIP_ROCM_RELEASE_OBSERVED)
    if(BG_HIP_ROCM_RELEASE_OBSERVED MATCHES "^6\\.0\\.2-")
        set(BG_HIP_SAFE_ROCM_RELEASE_MATCH TRUE)
    endif()
endif()
if(NOT BG_HIP_DEVICE_LIB_PATH STREQUAL "" AND
   NOT IS_ABSOLUTE "${BG_HIP_DEVICE_LIB_PATH}")
    message(FATAL_ERROR "BG_HIP_DEVICE_LIB_PATH must be absolute")
endif()
if(NOT BG_HIP_DEVICE_LIB_PATH STREQUAL "" AND
   EXISTS "${BG_HIP_DEVICE_LIB_PATH}")
    file(REAL_PATH "${BG_HIP_DEVICE_LIB_PATH}"
        BG_HIP_DEVICE_LIB_PATH_REAL)
    file(REAL_PATH "${PROJECT_SOURCE_DIR}/third_party"
        BG_LEGACY_THIRD_PARTY_ROOT_REAL)
    string(FIND
        "${BG_HIP_DEVICE_LIB_PATH_REAL}/"
        "${BG_LEGACY_THIRD_PARTY_ROOT_REAL}/"
        BG_HIP_DEVICE_LIB_LEGACY_PREFIX)
    if(BG_HIP_DEVICE_LIB_LEGACY_PREFIX EQUAL 0)
        message(FATAL_ERROR
            "hip_safe rejects repository legacy ROCm device libraries")
    endif()
endif()
if(BG_HIP_DEVICE_LIB_PATH STREQUAL "" AND BG_HIP_ROCM_ROOT)
    file(GLOB _BG_HIP_DEVICE_LIB_CANDIDATES LIST_DIRECTORIES TRUE
        "${BG_HIP_ROCM_ROOT}/lib/llvm/lib/clang/*/lib/amdgcn"
        "${BG_HIP_ROCM_ROOT}/amdgcn/bitcode")
    foreach(_BG_HIP_DEVICE_LIB_CANDIDATE
            IN LISTS _BG_HIP_DEVICE_LIB_CANDIDATES)
        if(EXISTS "${_BG_HIP_DEVICE_LIB_CANDIDATE}/ocml.bc" AND
           EXISTS "${_BG_HIP_DEVICE_LIB_CANDIDATE}/ockl.bc")
            set(BG_HIP_DEVICE_LIB_PATH
                "${_BG_HIP_DEVICE_LIB_CANDIDATE}")
            break()
        endif()
    endforeach()
endif()
set(BG_HIP_DEVICE_LIBS_FOUND FALSE)
if(NOT BG_HIP_DEVICE_LIB_PATH STREQUAL "" AND
   EXISTS "${BG_HIP_DEVICE_LIB_PATH}/ocml.bc" AND
   EXISTS "${BG_HIP_DEVICE_LIB_PATH}/ockl.bc")
    set(BG_HIP_DEVICE_LIBS_FOUND TRUE)
endif()

set(BG_HIP_SAFE_COMPILED FALSE)
if(NOT BG_ENABLE_HIP_SAFE_NORMALIZED STREQUAL "OFF" AND
   BG_HIPCC_EXECUTABLE AND BG_AMDHIP64_LIBRARY AND
   BG_HIP_DEVICE_LIBS_FOUND AND BG_HIP_SAFE_ROCM_RELEASE_MATCH)
    set(BG_HIP_SAFE_COMPILED TRUE)
elseif(BG_ENABLE_HIP_SAFE_NORMALIZED STREQUAL "ON")
    message(FATAL_ERROR
        "BG_ENABLE_HIP_SAFE=ON requires ROCm 6.0.2, hipcc, libamdhip64, and matching ROCm device libraries")
endif()

if(BG_HIP_SAFE_COMPILED)
    if(BG_HIP_SAFE_ARCHITECTURES STREQUAL "")
        message(FATAL_ERROR
            "BG_HIP_SAFE_ARCHITECTURES must identify at least one GPU target")
    endif()
    set(BG_HIP_SAFE_ARCH_FLAGS)
    foreach(BG_HIP_SAFE_ARCH IN LISTS BG_HIP_SAFE_ARCHITECTURES)
        if(NOT BG_HIP_SAFE_ARCH MATCHES "^gfx[0-9A-Za-z_]+$")
            message(FATAL_ERROR
                "hip_safe architecture identifiers must match gfx[0-9A-Za-z_]+")
        endif()
        list(APPEND BG_HIP_SAFE_ARCH_FLAGS
            "--offload-arch=${BG_HIP_SAFE_ARCH}")
    endforeach()
    string(REPLACE ";" "," BG_HIP_SAFE_ARCHITECTURES_CSV
        "${BG_HIP_SAFE_ARCHITECTURES}")
    set(BG_HIP_SAFE_OBJECT
        "${CMAKE_CURRENT_BINARY_DIR}/hip-safe-provider.o")
    set(BG_HIP_SAFE_STATIC_LIBRARY
        "${CMAKE_CURRENT_BINARY_DIR}/libbetelgeuze_hip_safe_provider.a")
    add_custom_command(
        OUTPUT "${BG_HIP_SAFE_OBJECT}"
        COMMAND ${BG_HIPCC_EXECUTABLE}
            -c "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/provider.hip"
            -o "${BG_HIP_SAFE_OBJECT}"
            -std=c++17
            -O2
            -fPIC
            -fno-fast-math
            -ffp-contract=off
            -Wall
            -Wextra
            -Wpedantic
            -Werror
            ${BG_HIP_SAFE_ARCH_FLAGS}
            "-DBG_HIP_SAFE_QUALIFIED_ARCHITECTURES=\"${BG_HIP_SAFE_ARCHITECTURES_CSV}\""
            "--rocm-path=${BG_HIP_ROCM_ROOT}"
            "--rocm-device-lib-path=${BG_HIP_DEVICE_LIB_PATH}"
            "-I${PROJECT_SOURCE_DIR}/include"
            "-I${CMAKE_CURRENT_SOURCE_DIR}/src/hip"
        DEPENDS
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/provider.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/docking_fixed64_so3.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/docking_fixed64_single_anchor.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/docking_geometric_admission.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/docking_scorer.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/docking_pose_validity.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/docking_stable_top_k.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/docking_rigid_refinement.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/docking_torsion_v7.hip"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/hip/provider.h"
            "${PROJECT_SOURCE_DIR}/include/betelgeuze/engine.h"
        COMMENT "Building deterministic hip_safe provider"
        VERBATIM
    )
    add_custom_command(
        OUTPUT "${BG_HIP_SAFE_STATIC_LIBRARY}"
        COMMAND ${CMAKE_AR} rcs
            "${BG_HIP_SAFE_STATIC_LIBRARY}"
            "${BG_HIP_SAFE_OBJECT}"
        DEPENDS "${BG_HIP_SAFE_OBJECT}"
        COMMENT "Archiving deterministic hip_safe provider"
        VERBATIM
    )
    add_custom_target(
        betelgeuze_hip_safe_provider_build
        DEPENDS "${BG_HIP_SAFE_STATIC_LIBRARY}"
    )
    add_library(betelgeuze_hip_safe_provider STATIC IMPORTED GLOBAL)
    set_target_properties(betelgeuze_hip_safe_provider PROPERTIES
        IMPORTED_LOCATION "${BG_HIP_SAFE_STATIC_LIBRARY}"
    )
    add_dependencies(
        betelgeuze_hip_safe_provider
        betelgeuze_hip_safe_provider_build
    )
    add_dependencies(betelgeuze_engine betelgeuze_hip_safe_provider_build)
    target_compile_definitions(
        betelgeuze_engine PRIVATE BG_HAS_HIP_SAFE_PROVIDER=1)
    target_link_libraries(
        betelgeuze_engine
        PRIVATE betelgeuze_hip_safe_provider "${BG_AMDHIP64_LIBRARY}")
    message(STATUS
        "hip_safe enabled for architectures: ${BG_HIP_SAFE_ARCHITECTURES}")
else()
    target_compile_definitions(
        betelgeuze_engine PRIVATE BG_HAS_HIP_SAFE_PROVIDER=0)
    message(STATUS "hip_safe disabled; fail-closed stub will be linked")
endif()

if(UNIX)
    find_package(Threads REQUIRED)
    target_link_libraries(
        betelgeuze_engine
        PRIVATE Threads::Threads ${CMAKE_DL_LIBS} m
    )
    if(NOT APPLE)
        target_link_libraries(betelgeuze_engine PRIVATE rt util)
    endif()
endif()

target_compile_features(betelgeuze_engine PUBLIC cxx_std_17)
target_compile_definitions(betelgeuze_engine PRIVATE
    BG_ENGINE_BUILD_SHARED
    BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
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
        betelgeuze_engine_docking_fixed64_allocation
        tests/docking_fixed64_allocation.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_fixed64_allocation
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_fixed64_allocation
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_fixed64_allocation
            PRIVATE
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
            betelgeuze_engine_docking_fixed64_allocation
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_fixed64_allocation
        COMMAND betelgeuze_engine_docking_fixed64_allocation
    )

    add_executable(
        betelgeuze_engine_docking_fixed64_so3
        tests/docking_fixed64_so3.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_fixed64_so3
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_fixed64_so3
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_fixed64_so3
            PRIVATE
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
            betelgeuze_engine_docking_fixed64_so3
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_fixed64_so3
        COMMAND betelgeuze_engine_docking_fixed64_so3
    )

    add_executable(
        betelgeuze_engine_docking_fixed64_indexed_so3
        tests/docking_fixed64_indexed_so3.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_fixed64_indexed_so3
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_fixed64_indexed_so3
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_fixed64_indexed_so3
            PRIVATE
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
            betelgeuze_engine_docking_fixed64_indexed_so3
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_fixed64_indexed_so3
        COMMAND betelgeuze_engine_docking_fixed64_indexed_so3
    )

    add_executable(
        betelgeuze_engine_docking_fixed64_single_anchor
        tests/docking_fixed64_single_anchor.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_fixed64_single_anchor
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_fixed64_single_anchor
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_fixed64_single_anchor
            PRIVATE
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
            betelgeuze_engine_docking_fixed64_single_anchor
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_fixed64_single_anchor
        COMMAND betelgeuze_engine_docking_fixed64_single_anchor
    )

    add_executable(
        betelgeuze_engine_docking_fixed64_producer
        tests/docking_fixed64_producer.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_fixed64_producer
        PRIVATE betelgeuze_engine
    )
    target_include_directories(
        betelgeuze_engine_docking_fixed64_producer
        PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src
    )
    target_compile_features(
        betelgeuze_engine_docking_fixed64_producer
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_fixed64_producer
            PRIVATE
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
            betelgeuze_engine_docking_fixed64_producer
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_fixed64_producer
        COMMAND betelgeuze_engine_docking_fixed64_producer
    )
    add_test(
        NAME betelgeuze_engine_docking_fixed64_complete_pipeline
        COMMAND betelgeuze_engine_docking_fixed64_producer
            --complete-pipeline
    )

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

    add_executable(
        betelgeuze_engine_docking_geometric_admission
        tests/docking_geometric_admission.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_geometric_admission
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_geometric_admission
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_geometric_admission
            PRIVATE
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
            betelgeuze_engine_docking_geometric_admission
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_geometric_admission
        COMMAND betelgeuze_engine_docking_geometric_admission
    )

    add_executable(
        betelgeuze_engine_docking_scorer_v1
        tests/docking_scorer_v1.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_scorer_v1
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_scorer_v1
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(betelgeuze_engine_docking_scorer_v1 PRIVATE
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
            betelgeuze_engine_docking_scorer_v1
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_scorer_v1
        COMMAND betelgeuze_engine_docking_scorer_v1
    )

    add_executable(
        betelgeuze_engine_docking_pose_validity
        tests/docking_pose_validity.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_pose_validity
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_pose_validity
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_pose_validity
            PRIVATE
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
            betelgeuze_engine_docking_pose_validity
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_pose_validity
        COMMAND betelgeuze_engine_docking_pose_validity
    )

    add_executable(
        betelgeuze_engine_docking_stable_top_k
        tests/docking_stable_top_k.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_stable_top_k
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_stable_top_k
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_stable_top_k
            PRIVATE
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
            betelgeuze_engine_docking_stable_top_k
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_stable_top_k
        COMMAND betelgeuze_engine_docking_stable_top_k
    )

    add_executable(
        betelgeuze_engine_docking_fixed64_downstream
        tests/docking_fixed64_downstream.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_fixed64_downstream
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_fixed64_downstream
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_fixed64_downstream
            PRIVATE
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
            betelgeuze_engine_docking_fixed64_downstream
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_fixed64_downstream
        COMMAND betelgeuze_engine_docking_fixed64_downstream
    )

    add_executable(
        betelgeuze_engine_docking_fixed64_refinement_pipeline
        tests/docking_fixed64_refinement_pipeline.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_fixed64_refinement_pipeline
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_fixed64_refinement_pipeline
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_fixed64_refinement_pipeline
            PRIVATE
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
            betelgeuze_engine_docking_fixed64_refinement_pipeline
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_fixed64_refinement_pipeline
        COMMAND betelgeuze_engine_docking_fixed64_refinement_pipeline
    )

    add_executable(
        betelgeuze_engine_docking_torsion_v7
        tests/docking_torsion_v7.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_torsion_v7
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_torsion_v7
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_torsion_v7
            PRIVATE
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
            betelgeuze_engine_docking_torsion_v7
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_torsion_v7
        COMMAND betelgeuze_engine_docking_torsion_v7
    )

    add_executable(
        betelgeuze_engine_docking_rigid_refinement
        tests/docking_rigid_refinement.cpp
    )
    target_link_libraries(
        betelgeuze_engine_docking_rigid_refinement
        PRIVATE betelgeuze_engine
    )
    target_compile_features(
        betelgeuze_engine_docking_rigid_refinement
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            betelgeuze_engine_docking_rigid_refinement
            PRIVATE
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
            betelgeuze_engine_docking_rigid_refinement
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_docking_rigid_refinement
        COMMAND betelgeuze_engine_docking_rigid_refinement
    )

    add_executable(
        betelgeuze_engine_dynamics
        tests/dynamics.cpp
    )
    target_link_libraries(
        betelgeuze_engine_dynamics
        PRIVATE betelgeuze_engine
    )
    target_compile_definitions(betelgeuze_engine_dynamics PRIVATE
        BG_TEST_HIP_ENABLED=$<BOOL:${BG_ENABLE_HIP}>
    )
    target_compile_features(
        betelgeuze_engine_dynamics
        PRIVATE cxx_std_17
    )
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(betelgeuze_engine_dynamics PRIVATE
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
            betelgeuze_engine_dynamics
            PRIVATE /W4 /WX /UNDEBUG /fp:strict
        )
    endif()
    add_test(
        NAME betelgeuze_engine_dynamics
        COMMAND betelgeuze_engine_dynamics
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
                src/hip/evaluator.cpp
                src/hip/backend.hip
                src/rust/evaluator.cpp
            )
            target_compile_definitions(
                ${BG_HIP_INTERNAL_TARGET}
                PRIVATE
                    BG_ENABLE_HIP=1
                    BG_HAS_HIP_SAFE_PROVIDER=0
                    BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
            )
            target_link_libraries(
                ${BG_HIP_INTERNAL_TARGET}
                PRIVATE betelgeuze_rust_cpu_provider
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
