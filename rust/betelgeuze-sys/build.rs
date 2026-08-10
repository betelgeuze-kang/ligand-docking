use std::path::{Path, PathBuf};

fn track(path: &Path) {
    println!("cargo:rerun-if-changed={}", path.display());
}

fn main() {
    let manifest_dir = PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR is set by Cargo"),
    );
    let repository_root = manifest_dir
        .join("../..")
        .canonicalize()
        .expect("betelgeuze-sys must be built inside the repository");
    let include_dir = repository_root.join("include");
    let internal_header = repository_root.join("native/src/internal.hpp");
    let context_source = repository_root.join("native/src/context.cpp");
    let evaluator_source = repository_root.join("native/src/evaluator.cpp");
    let forcefield_source = repository_root.join("native/src/forcefield.cpp");
    let system_source = repository_root.join("native/src/system.cpp");
    let cpu_evaluator_header = repository_root.join("native/src/cpu/evaluator.hpp");
    let cpu_evaluator_source = repository_root.join("native/src/cpu/evaluator.cpp");
    let dynamics_header = repository_root.join("native/src/dynamics/dynamics.hpp");
    let dynamics_api_source = repository_root.join("native/src/dynamics/api.cpp");
    let dynamics_checkpoint_source = repository_root.join("native/src/dynamics/checkpoint.cpp");
    let dynamics_common_source = repository_root.join("native/src/dynamics/common.cpp");
    let dynamics_integrator_source = repository_root.join("native/src/dynamics/integrator.cpp");
    let dynamics_sha256_header = repository_root.join("native/src/dynamics/sha256.hpp");
    let dynamics_sha256_source = repository_root.join("native/src/dynamics/sha256.cpp");
    let hip_backend_header = repository_root.join("native/src/hip/backend.hpp");
    let hip_backend_source = repository_root.join("native/src/hip/backend.hip");
    let hip_planning_header = repository_root.join("native/src/hip/planning.hpp");
    let hip_stub_source = repository_root.join("native/src/hip/stub.cpp");
    let c_header_probe = manifest_dir.join("abi/header_c11.c");
    let cpp_layout_probe = manifest_dir.join("abi/layout_assertions.cpp");

    track(&include_dir.join("betelgeuze/engine.h"));
    track(&internal_header);
    track(&context_source);
    track(&evaluator_source);
    track(&forcefield_source);
    track(&system_source);
    track(&cpu_evaluator_header);
    track(&cpu_evaluator_source);
    track(&dynamics_header);
    track(&dynamics_api_source);
    track(&dynamics_checkpoint_source);
    track(&dynamics_common_source);
    track(&dynamics_integrator_source);
    track(&dynamics_sha256_header);
    track(&dynamics_sha256_source);
    track(&hip_backend_header);
    track(&hip_backend_source);
    track(&hip_planning_header);
    track(&hip_stub_source);
    track(&c_header_probe);
    track(&cpp_layout_probe);

    let mut native_build = cc::Build::new();
    native_build
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&context_source)
        .file(&evaluator_source)
        .file(&forcefield_source)
        .file(&system_source)
        .file(&cpu_evaluator_source)
        .file(&dynamics_api_source)
        .file(&dynamics_checkpoint_source)
        .file(&dynamics_common_source)
        .file(&dynamics_integrator_source)
        .file(&dynamics_sha256_source)
        .warnings(true)
        .warnings_into_errors(true);
    let hip_enabled = std::env::var_os("CARGO_FEATURE_HIP").is_some();
    if hip_enabled {
        println!("cargo:rerun-if-env-changed=HIP_PATH");
        println!("cargo:rerun-if-env-changed=ROCM_PATH");
        println!("cargo:rerun-if-env-changed=ROCM_DEVICE_LIB_PATH");
        println!("cargo:rerun-if-env-changed=BG_HIP_ARCHITECTURE");
        let rocm_path = std::env::var_os("HIP_PATH")
            .or_else(|| std::env::var_os("ROCM_PATH"))
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("/opt/rocm"));
        let hip_compiler = rocm_path.join("bin/hipcc");
        let architecture = std::env::var("BG_HIP_ARCHITECTURE").unwrap_or_else(|_| {
            panic!(
                "the HIP feature requires an explicit BG_HIP_ARCHITECTURE \
                 (for example gfx1030); hardware-derived native builds are \
                 intentionally forbidden"
            )
        });
        if architecture.trim().is_empty() {
            panic!("BG_HIP_ARCHITECTURE must not be empty");
        }
        native_build
            .compiler(&hip_compiler)
            .include(rocm_path.join("include"))
            .file(&hip_backend_source)
            .define("BG_ENABLE_HIP", "1")
            .flag(format!("--offload-arch={architecture}"));
        let device_libs = std::env::var_os("ROCM_DEVICE_LIB_PATH")
            .map(PathBuf::from)
            .or_else(|| {
                let installed = rocm_path.join("amdgcn/bitcode");
                installed.is_dir().then_some(installed)
            })
            .unwrap_or_else(|| {
                panic!(
                    "the HIP feature requires matching ROCm device libraries; \
                     install rocm-device-libs or set ROCM_DEVICE_LIB_PATH"
                )
            });
        track(&device_libs);
        native_build.flag(format!("--rocm-device-lib-path={}", device_libs.display()));
        println!(
            "cargo:rustc-link-search=native={}",
            rocm_path.join("lib").display()
        );
        println!(
            "cargo:rustc-link-search=native={}",
            rocm_path.join("lib64").display()
        );
        println!("cargo:rustc-link-lib=dylib=amdhip64");
    } else {
        native_build
            .file(&hip_stub_source)
            .define("BG_ENABLE_HIP", "0");
    }
    if native_build.get_compiler().is_like_msvc() {
        native_build.flag_if_supported("/fp:strict");
    } else {
        native_build
            .flag_if_supported("-fvisibility=hidden")
            .flag_if_supported("-ffp-contract=off")
            .flag_if_supported("-fno-fast-math");
    }
    native_build.compile("betelgeuze_engine");

    cc::Build::new()
        .include(&include_dir)
        .file(&c_header_probe)
        .flag_if_supported("-std=c11")
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_header_c11_probe");

    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&cpp_layout_probe)
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_cpp_layout_probe");
}
