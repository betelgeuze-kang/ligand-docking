use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const QUALIFIED_ROCM_RELEASE_PREFIX: &str = "6.0.2-";

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
    "native/src/docking/pose_validity.cpp",
    "native/src/docking/scorer_v1.cpp",
    "native/src/dynamics/dynamics.hpp",
    "native/src/dynamics/api.cpp",
    "native/src/dynamics/checkpoint.cpp",
    "native/src/dynamics/common.cpp",
    "native/src/dynamics/integrator.cpp",
    "native/src/dynamics/sha256.hpp",
    "native/src/dynamics/sha256.cpp",
    "native/src/hip/provider.h",
    "native/src/hip/provider.hip",
    "native/src/hip/docking_scorer.hip",
    "native/src/hip/docking_pose_validity.hip",
    "native/src/hip/evaluator.hpp",
    "native/src/hip/evaluator.cpp",
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

struct HipSafeLink {
    output_dir: PathBuf,
    rocm_root: PathBuf,
}

fn required_env_path(name: &str) -> PathBuf {
    let value = std::env::var_os(name).unwrap_or_else(|| panic!("{name} must be set"));
    let path = PathBuf::from(value);
    assert!(path.is_absolute(), "{name} must be an absolute path");
    path
}

fn build_hip_safe_provider(
    manifest_dir: &Path,
    include_dir: &Path,
    provider_source: &Path,
) -> Option<HipSafeLink> {
    println!("cargo:rerun-if-env-changed=BETELGEUZE_HIP_SAFE");
    println!("cargo:rerun-if-env-changed=ROCM_PATH");
    println!("cargo:rerun-if-env-changed=HIP_PATH");
    println!("cargo:rerun-if-env-changed=BG_HIP_SAFE_ARCHITECTURES");
    println!("cargo:rerun-if-env-changed=BG_HIP_DEVICE_LIB_PATH");
    let enabled = match std::env::var("BETELGEUZE_HIP_SAFE") {
        Err(std::env::VarError::NotPresent) => false,
        Ok(value) if value == "0" => false,
        Ok(value) if value == "1" => true,
        Ok(_) | Err(std::env::VarError::NotUnicode(_)) => {
            panic!("BETELGEUZE_HIP_SAFE must be exactly 0 or 1")
        }
    };
    if !enabled {
        return None;
    }

    let rocm_root = std::env::var_os("ROCM_PATH")
        .or_else(|| std::env::var_os("HIP_PATH"))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/opt/rocm"));
    assert!(rocm_root.is_absolute(), "ROCM_PATH must be absolute");
    let release = std::fs::read_to_string(rocm_root.join(".info/version"))
        .expect("ROCM_PATH must contain .info/version");
    assert!(
        release.trim().starts_with(QUALIFIED_ROCM_RELEASE_PREFIX),
        "hip_safe is qualified only for ROCm 6.0.2"
    );
    let hipcc = rocm_root.join("bin/hipcc");
    assert!(hipcc.is_file(), "hipcc is absent at {}", hipcc.display());
    let device_lib_path = required_env_path("BG_HIP_DEVICE_LIB_PATH")
        .canonicalize()
        .expect("BG_HIP_DEVICE_LIB_PATH must resolve");
    if let Ok(legacy_root) = manifest_dir.join("../../third_party").canonicalize() {
        assert!(
            !device_lib_path.starts_with(&legacy_root),
            "hip_safe rejects repository legacy ROCm device libraries"
        );
    }
    assert!(
        device_lib_path.join("ocml.bc").is_file() && device_lib_path.join("ockl.bc").is_file(),
        "BG_HIP_DEVICE_LIB_PATH lacks ocml.bc or ockl.bc"
    );
    let architecture_source =
        std::env::var("BG_HIP_SAFE_ARCHITECTURES").unwrap_or_else(|_| "gfx1030".to_owned());
    let architectures: Vec<&str> = architecture_source
        .split([',', ';'])
        .filter(|value| !value.is_empty())
        .collect();
    assert!(!architectures.is_empty(), "HIP architecture set is empty");
    assert!(
        architectures.iter().all(|value| {
            value.starts_with("gfx")
                && value.len() > 3
                && value
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
        }),
        "HIP architectures must start with gfx and contain only ASCII alphanumeric characters and underscore"
    );
    let architecture_csv = architectures.join(",");
    let output_dir = PathBuf::from(std::env::var_os("OUT_DIR").expect("OUT_DIR is set by Cargo"));
    let object = output_dir.join("hip_safe_provider.o");
    let archive = output_dir.join("libbetelgeuze_hip_safe_provider.a");

    let mut compiler = Command::new(&hipcc);
    compiler
        .arg("-c")
        .arg(provider_source)
        .arg("-o")
        .arg(&object)
        .args([
            "-std=c++17",
            "-O2",
            "-fPIC",
            "-fno-fast-math",
            "-ffp-contract=off",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
        ])
        .arg(format!(
            "-DBG_HIP_SAFE_QUALIFIED_ARCHITECTURES=\"{architecture_csv}\""
        ))
        .arg(format!("--rocm-path={}", rocm_root.display()))
        .arg(format!(
            "--rocm-device-lib-path={}",
            device_lib_path.display()
        ))
        .arg(format!("-I{}", include_dir.display()))
        .arg(format!(
            "-I{}",
            provider_source
                .parent()
                .expect("hip_safe provider source has a parent")
                .display()
        ));
    for architecture in &architectures {
        compiler.arg(format!("--offload-arch={architecture}"));
    }
    let compile_status = compiler.status().expect("hipcc must launch");
    assert!(
        compile_status.success(),
        "hip_safe provider compilation failed"
    );

    let archiver = std::env::var_os("AR").unwrap_or_else(|| "ar".into());
    let archive_status = Command::new(archiver)
        .arg("rcs")
        .arg(&archive)
        .arg(&object)
        .status()
        .expect("HIP provider archiver must launch");
    assert!(archive_status.success(), "hip_safe provider archive failed");
    Some(HipSafeLink {
        output_dir,
        rocm_root,
    })
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
    let docking_scorer_source = vendor_root.join("native/src/docking/scorer_v1.cpp");
    let docking_pose_validity_source = vendor_root.join("native/src/docking/pose_validity.cpp");
    let dynamics_api_source = vendor_root.join("native/src/dynamics/api.cpp");
    let dynamics_checkpoint_source = vendor_root.join("native/src/dynamics/checkpoint.cpp");
    let dynamics_common_source = vendor_root.join("native/src/dynamics/common.cpp");
    let dynamics_integrator_source = vendor_root.join("native/src/dynamics/integrator.cpp");
    let dynamics_sha256_source = vendor_root.join("native/src/dynamics/sha256.cpp");
    let hip_provider_source = vendor_root.join("native/src/hip/provider.hip");
    let hip_evaluator_source = vendor_root.join("native/src/hip/evaluator.cpp");
    let hip_backend_source = vendor_root.join("native/src/hip/backend.hip");
    let hip_stub_source = vendor_root.join("native/src/hip/stub.cpp");
    let c_header_probe = manifest_dir.join("abi/header_c11.c");
    let cpp_layout_probe = manifest_dir.join("abi/layout_assertions.cpp");
    track(&c_header_probe);
    track(&cpp_layout_probe);

    let hip_safe_link = build_hip_safe_provider(&manifest_dir, &include_dir, &hip_provider_source);
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
        .define(
            "BG_HAS_HIP_SAFE_PROVIDER",
            if hip_safe_link.is_some() { "1" } else { "0" },
        )
        .file(&hip_evaluator_source)
        .file(&rust_evaluator_source)
        .file(&docking_pose_validity_source)
        .file(&docking_scorer_source)
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
    if let Some(link) = hip_safe_link {
        println!(
            "cargo:rustc-link-search=native={}",
            link.output_dir.display()
        );
        println!("cargo:rustc-link-lib=static=betelgeuze_hip_safe_provider");
        println!(
            "cargo:rustc-link-search=native={}/lib",
            link.rocm_root.display()
        );
        println!(
            "cargo:rustc-link-search=native={}/lib64",
            link.rocm_root.display()
        );
        println!("cargo:rustc-link-lib=dylib=amdhip64");
    }

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
