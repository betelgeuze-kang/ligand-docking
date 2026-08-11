add_library(betelgeuze_engine SHARED
    src/context.cpp
    src/evaluator.cpp
    src/forcefield.cpp
    src/system.cpp
    src/tensor.cpp
    src/cpu/evaluator.cpp
    src/rust/evaluator.cpp
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
    "${PROJECT_SOURCE_DIR}/rust/cpu-kernel/src/*.rs")
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
target_compile_definitions(betelgeuze_engine PRIVATE BG_ENGINE_BUILD_SHARED)
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
    VERSION 1.1.0
    SOVERSION 1
)

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
        -Wall
        -Wextra
        -Wpedantic
        -Wconversion
        -Wsign-conversion
        -Werror
        -ffp-contract=off
        -fno-fast-math
    )
elseif(MSVC)
    target_compile_options(betelgeuze_engine PRIVATE /W4 /WX /fp:strict)
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
