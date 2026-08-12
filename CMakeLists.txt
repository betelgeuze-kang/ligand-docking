cmake_minimum_required(VERSION 3.20)

project(betelgeuze_native_engine VERSION 1.14.0 LANGUAGES C CXX)

option(BG_ENABLE_HIP "Build the native ROCm/HIP compute backend" OFF)
if(BG_ENABLE_HIP)
    if(CMAKE_VERSION VERSION_LESS 3.21)
        message(FATAL_ERROR "BG_ENABLE_HIP requires CMake 3.21 or newer")
    endif()
    # Use CMake's first-class HIP language support.  Toolchain location and
    # CMAKE_HIP_ARCHITECTURES remain caller-selectable; no ROCm installation
    # path or GPU architecture is embedded in the project.
    enable_language(HIP)
endif()

include(CTest)
add_subdirectory(native)
