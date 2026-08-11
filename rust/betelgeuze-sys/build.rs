use std::fs;
use std::path::{Path, PathBuf};

const VENDORED_FILES: &[&str] = &[
    "include/betelgeuze/engine.h",
    "native/src/internal.hpp",
    "native/src/context.cpp",
    "native/src/evaluator.cpp",
    "native/src/forcefield.cpp",
    "native/src/system.cpp",
    "native/src/cpu/evaluator.hpp",
    "native/src/cpu/evaluator.cpp",
    "native/src/rust/provider.h",
    "native/src/rust/evaluator.hpp",
    "native/src/rust/evaluator.cpp",
    "native/src/dynamics/dynamics.hpp",
    "native/src/dynamics/api.cpp",
    "native/src/dynamics/checkpoint.cpp",
    "native/src/dynamics/common.cpp",
    "native/src/dynamics/integrator.cpp",
    "native/src/dynamics/sha256.hpp",
    "native/src/dynamics/sha256.cpp",
    "native/src/hip/backend.hpp",
    "native/src/hip/backend.hip",
    "native/src/hip/planning.hpp",
    "native/src/hip/stub.cpp",
];

fn track(path: &Path) {
    println!("cargo:rerun-if-changed={}", path.display());
}

fn verify_workspace_vendor(manifest_dir: &Path) {
    let workspace_root = manifest_dir.join("../..");
    let workspace_manifest = workspace_root.join("rust/Cargo.toml");
    let checkout_manifest = workspace_root.join("rust/betelgeuze-sys/Cargo.toml");
    let current_manifest = manifest_dir.join("Cargo.toml");

    let is_workspace_checkout = match (
        checkout_manifest.canonicalize(),
        current_manifest.canonicalize(),
    ) {
        (Ok(checkout), Ok(current)) => workspace_manifest.is_file() && checkout == current,
        _ => false,
    };
    if !is_workspace_checkout {
        return;
    }

    for relative in VENDORED_FILES {
        let canonical = workspace_root.join(relative);
        let vendored = manifest_dir.join("vendor").join(relative);
        track(&canonical);
        let canonical_bytes = fs::read(&canonical).unwrap_or_else(|error| {
            panic!(
                "failed to read canonical native source {}: {error}",
                canonical.display()
            )
        });
        let vendored_bytes = fs::read(&vendored).unwrap_or_else(|error| {
            panic!(
                "failed to read vendored native source {}: {error}",
                vendored.display()
            )
        });
        if canonical_bytes != vendored_bytes {
            panic!(
                "vendored native source drifted from {}; copy it byte-for-byte to {}",
                canonical.display(),
                vendored.display()
            );
        }
    }
}

fn main() {
    let manifest_dir = PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR is set by Cargo"),
    );
    verify_workspace_vendor(&manifest_dir);

    let vendor_root = manifest_dir.join("vendor");
    for relative in VENDORED_FILES {
        let vendored = vendor_root.join(relative);
        track(&vendored);
        if !vendored.is_file() {
            panic!(
                "required vendored native source is missing: {}",
                vendored.display()
            );
        }
    }
    let include_dir = vendor_root.join("include");
    let context_source = vendor_root.join("native/src/context.cpp");
    let evaluator_source = vendor_root.join("native/src/evaluator.cpp");
    let forcefield_source = vendor_root.join("native/src/forcefield.cpp");
    let system_source = vendor_root.join("native/src/system.cpp");
    let cpu_evaluator_source = vendor_root.join("native/src/cpu/evaluator.cpp");
    let rust_evaluator_source = vendor_root.join("native/src/rust/evaluator.cpp");
    let dynamics_api_source = vendor_root.join("native/src/dynamics/api.cpp");
    let dynamics_checkpoint_source = vendor_root.join("native/src/dynamics/checkpoint.cpp");
    let dynamics_common_source = vendor_root.join("native/src/dynamics/common.cpp");
    let dynamics_integrator_source = vendor_root.join("native/src/dynamics/integrator.cpp");
    let dynamics_sha256_source = vendor_root.join("native/src/dynamics/sha256.cpp");
    let hip_backend_source = vendor_root.join("native/src/hip/backend.hip");
    let hip_stub_source = vendor_root.join("native/src/hip/stub.cpp");
    let c_header_probe = manifest_dir.join("abi/header_c11.c");
    let cpp_layout_probe = manifest_dir.join("abi/layout_assertions.cpp");
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
        .file(&rust_evaluator_source)
        .file(&dynamics_api_source)
        .file(&dynamics_checkpoint_source)
        .file(&dynamics_common_source)
        .file(&dynamics_integrator_source)
        .file(&dynamics_sha256_source)
        .define("BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS", None)
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
