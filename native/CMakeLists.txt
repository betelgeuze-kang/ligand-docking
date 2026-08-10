add_library(betelgeuze_engine SHARED
    src/context.cpp
    src/system.cpp
)

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
    VERSION 1.0.0
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
