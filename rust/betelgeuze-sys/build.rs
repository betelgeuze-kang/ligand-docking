use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

const QUALIFIED_ROCM_RELEASE_PREFIX: &str = "6.0.2-";
const QUALIFICATION_BUILD_ENV: &str = "BETELGEUZE_V7_QUALIFICATION_BUILD";
const QUALIFICATION_RUSTC_WRAPPER_RELATIVE_PATH: &str =
    "tools/verify_engine_v2_native_fixed64_cpu_v7_rustc_wrapper.py";
const QUALIFICATION_CPP_COMPILER: &str = "/usr/bin/x86_64-linux-gnu-g++-11";
const QUALIFICATION_CPP_FLAGS: &[&str] = &[
    "-std=c++17",
    "-O3",
    "-m64",
    "-fPIC",
    "-ffunction-sections",
    "-fdata-sections",
    "-fvisibility=hidden",
    "-ffp-contract=off",
    "-fno-fast-math",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
];
const QUALIFICATION_FORBIDDEN_ENVIRONMENT: &[&str] = &[
    "AR",
    "CC",
    "CFLAGS",
    "CPPFLAGS",
    "CXX",
    "CXXFLAGS",
    "LDFLAGS",
    "RANLIB",
    "RUSTFLAGS",
    "RUSTC_WORKSPACE_WRAPPER",
    "CARGO_BUILD_RUSTFLAGS",
    "CARGO_INCREMENTAL",
    "HOST_CC",
    "HOST_CFLAGS",
    "HOST_CXX",
    "HOST_CXXFLAGS",
    "TARGET_CC",
    "TARGET_CFLAGS",
    "TARGET_CXX",
    "TARGET_CXXFLAGS",
    "CC_x86_64_unknown_linux_gnu",
    "CFLAGS_x86_64_unknown_linux_gnu",
    "CXX_x86_64_unknown_linux_gnu",
    "CXXFLAGS_x86_64_unknown_linux_gnu",
    "BETELGEUZE_HIP_SAFE",
    "ROCM_PATH",
    "HIP_PATH",
    "BG_HIP_SAFE_ARCHITECTURES",
    "BG_HIP_DEVICE_LIB_PATH",
];

const VENDORED_FILES: &[&str] = &[
    "include/betelgeuze/engine.h",
    "include/betelgeuze/direct_ewald.h",
    "include/betelgeuze/direct_ewald_composite.h",
    "include/betelgeuze/direct_ewald_composite_dynamics.h",
    "include/betelgeuze/particle_mesh_ewald.h",
    "include/betelgeuze/particle_mesh_reciprocal.h",
    "native/src/internal.hpp",
    "native/src/context.cpp",
    "native/src/composite/direct_ewald.cpp",
    "native/src/composite/evaluator.hpp",
    "native/src/composite/direct_ewald_composite_dynamics.hpp",
    "native/src/composite/direct_ewald_composite_dynamics.cpp",
    "native/src/composite/direct_ewald_composite_checkpoint.cpp",
    "native/src/composite/particle_mesh_ewald.cpp",
    "native/src/ewald/api.cpp",
    "native/src/ewald/cpp_evaluator.cpp",
    "native/src/ewald/cpp_evaluator.hpp",
    "native/src/ewald/model.hpp",
    "native/src/ewald/rust_evaluator.cpp",
    "native/src/ewald/rust_evaluator.hpp",
    "native/src/ewald/rust_provider.h",
    "native/src/particle_mesh_reciprocal/api.cpp",
    "native/src/particle_mesh_reciprocal/cpp_evaluator.cpp",
    "native/src/particle_mesh_reciprocal/cpp_evaluator.hpp",
    "native/src/particle_mesh_reciprocal/model.hpp",
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp",
    "native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
    "native/src/particle_mesh_reciprocal/rust_provider.h",
    "native/src/evaluator.cpp",
    "native/src/forcefield.cpp",
    "native/src/system.cpp",
    "native/src/cpu/evaluator.hpp",
    "native/src/cpu/neighbor_pair.hpp",
    "native/src/cpu/evaluator.cpp",
    "native/src/rust/provider.h",
    "native/src/rust/evaluator.hpp",
    "native/src/rust/evaluator.cpp",
    "native/src/docking/fixed64_allocation.cpp",
    "native/src/docking/fixed64_so3.cpp",
    "native/src/docking/fixed64_so3_reference.hpp",
    "native/src/docking/fixed64_indexed_so3_provider.h",
    "native/src/docking/fixed64_indexed_so3.cpp",
    "native/src/docking/fixed64_pipeline.cpp",
    "native/src/docking/fixed64_producer.cpp",
    "native/src/docking/fixed64_single_anchor_provider.h",
    "native/src/docking/fixed64_single_anchor.cpp",
    "native/src/docking/fixed64_downstream.cpp",
    "native/src/docking/fixed64_refinement_pipeline.cpp",
    "native/src/docking/geometric_admission.cpp",
    "native/src/docking/pose_validity.cpp",
    "native/src/docking/rigid_refinement.cpp",
    "native/src/docking/scorer_v1.cpp",
    "native/src/docking/stable_top_k.cpp",
    "native/src/docking/torsion_v7.cpp",
    "native/src/dynamics/dynamics.hpp",
    "native/src/dynamics/api.cpp",
    "native/src/dynamics/checkpoint.cpp",
    "native/src/dynamics/common.cpp",
    "native/src/dynamics/integrator.cpp",
    "native/src/dynamics/sha256.hpp",
    "native/src/dynamics/sha256.cpp",
    "native/src/hip/provider.h",
    "native/src/hip/provider.hip",
    "native/src/hip/docking_fixed64_so3.hip",
    "native/src/hip/docking_fixed64_single_anchor.hip",
    "native/src/hip/docking_geometric_admission.hip",
    "native/src/hip/docking_scorer.hip",
    "native/src/hip/docking_pose_validity.hip",
    "native/src/hip/docking_stable_top_k.hip",
    "native/src/hip/docking_rigid_refinement.hip",
    "native/src/hip/docking_torsion_v7.hip",
    "native/src/hip/evaluator.hpp",
    "native/src/hip/evaluator.cpp",
    "native/src/hip/backend.hpp",
    "native/src/hip/backend.hip",
    "native/src/hip/planning.hpp",
    "native/src/hip/stub.cpp",
];

fn qualification_build_requested() -> bool {
    println!("cargo:rerun-if-env-changed={QUALIFICATION_BUILD_ENV}");
    println!("cargo:rerun-if-env-changed=RUSTC_WRAPPER");
    for name in QUALIFICATION_FORBIDDEN_ENVIRONMENT {
        println!("cargo:rerun-if-env-changed={name}");
    }
    let requested = match std::env::var(QUALIFICATION_BUILD_ENV) {
        Ok(value) => {
            assert_eq!(value, "1", "{QUALIFICATION_BUILD_ENV} must equal 1");
            true
        }
        Err(std::env::VarError::NotPresent) => false,
        Err(std::env::VarError::NotUnicode(_)) => {
            panic!("{QUALIFICATION_BUILD_ENV} must be UTF-8")
        }
    };
    if !requested {
        return false;
    }
    let manifest_dir = PathBuf::from(
        std::env::var_os("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR is set by Cargo"),
    );
    let workspace_root = manifest_dir
        .join("..")
        .canonicalize()
        .expect("v7 native qualification workspace root must resolve");
    let out_dir = PathBuf::from(std::env::var_os("OUT_DIR").expect("OUT_DIR is set by Cargo"))
        .canonicalize()
        .expect("v7 native qualification OUT_DIR must resolve");
    let expected_build_root = workspace_root.join("target/qualification-v7/build");
    let expected_wrapper = workspace_root
        .parent()
        .expect("v7 native qualification repository root must exist")
        .join(QUALIFICATION_RUSTC_WRAPPER_RELATIVE_PATH)
        .canonicalize()
        .expect("v7 native qualification rustc wrapper must resolve");
    let wrapper_is_exact = std::env::var_os("RUSTC_WRAPPER")
        .map(PathBuf::from)
        .and_then(|path| path.canonicalize().ok())
        .as_deref()
        == Some(expected_wrapper.as_path());
    let output_is_exact = out_dir
        .strip_prefix(expected_build_root)
        .ok()
        .map(|relative| relative.iter().collect::<Vec<_>>())
        .is_some_and(|components| {
            components.len() == 2
                && components[0]
                    .as_encoded_bytes()
                    .starts_with(b"betelgeuze-sys-")
                && components[0].as_encoded_bytes()["betelgeuze-sys-".len()..]
                    .iter()
                    .all(u8::is_ascii_hexdigit)
                && components[1] == "out"
        });
    let no_target_environment_override = std::env::vars_os().all(|(name, _)| {
        name.to_str()
            .is_some_and(|name| !name.starts_with("CARGO_TARGET_"))
    });
    let checks = [
        (
            "build-script profile",
            std::env::var("PROFILE").ok().as_deref() == Some("release"),
        ),
        (
            "optimization level",
            std::env::var("OPT_LEVEL").ok().as_deref() == Some("3"),
        ),
        (
            "debug info",
            std::env::var("DEBUG").ok().as_deref() == Some("false"),
        ),
        (
            "host triple",
            std::env::var("HOST").ok().as_deref() == Some("x86_64-unknown-linux-gnu"),
        ),
        (
            "target triple",
            std::env::var("TARGET").ok().as_deref() == Some("x86_64-unknown-linux-gnu"),
        ),
        (
            "build-script panic mode",
            std::env::var("CARGO_CFG_PANIC").ok().as_deref() == Some("unwind"),
        ),
        (
            "target features",
            std::env::var("CARGO_CFG_TARGET_FEATURE").ok().as_deref() == Some("fxsr,sse,sse2"),
        ),
        (
            "HIP feature absence",
            std::env::var_os("CARGO_FEATURE_HIP").is_none(),
        ),
        (
            "Rust flag absence",
            std::env::var_os("CARGO_ENCODED_RUSTFLAGS").is_none_or(|value| value.is_empty()),
        ),
        ("rustc wrapper", wrapper_is_exact),
        (
            "compiler override absence",
            QUALIFICATION_FORBIDDEN_ENVIRONMENT
                .iter()
                .all(|name| std::env::var_os(name).is_none()),
        ),
        ("target override absence", no_target_environment_override),
        ("qualification output directory", output_is_exact),
    ];
    let failures = checks
        .into_iter()
        .filter_map(|(label, passed)| (!passed).then_some(label))
        .collect::<Vec<_>>();
    assert!(
        failures.is_empty(),
        "v7 native qualification compiler configuration changed: {}",
        failures.join(", ")
    );
    true
}

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
    let qualification_build = qualification_build_requested();

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
    let direct_ewald_composite_source = vendor_root.join("native/src/composite/direct_ewald.cpp");
    let direct_ewald_composite_dynamics_source =
        vendor_root.join("native/src/composite/direct_ewald_composite_dynamics.cpp");
    let direct_ewald_composite_checkpoint_source =
        vendor_root.join("native/src/composite/direct_ewald_composite_checkpoint.cpp");
    let particle_mesh_ewald_source =
        vendor_root.join("native/src/composite/particle_mesh_ewald.cpp");
    let direct_ewald_api_source = vendor_root.join("native/src/ewald/api.cpp");
    let direct_ewald_cpp_evaluator_source = vendor_root.join("native/src/ewald/cpp_evaluator.cpp");
    let direct_ewald_rust_evaluator_source =
        vendor_root.join("native/src/ewald/rust_evaluator.cpp");
    let particle_mesh_reciprocal_api_source =
        vendor_root.join("native/src/particle_mesh_reciprocal/api.cpp");
    let particle_mesh_reciprocal_cpp_evaluator_source =
        vendor_root.join("native/src/particle_mesh_reciprocal/cpp_evaluator.cpp");
    let particle_mesh_reciprocal_rust_evaluator_source =
        vendor_root.join("native/src/particle_mesh_reciprocal/rust_evaluator.cpp");
    let evaluator_source = vendor_root.join("native/src/evaluator.cpp");
    let forcefield_source = vendor_root.join("native/src/forcefield.cpp");
    let system_source = vendor_root.join("native/src/system.cpp");
    let cpu_evaluator_source = vendor_root.join("native/src/cpu/evaluator.cpp");
    let rust_evaluator_source = vendor_root.join("native/src/rust/evaluator.cpp");
    let docking_fixed64_allocation_source =
        vendor_root.join("native/src/docking/fixed64_allocation.cpp");
    let docking_fixed64_so3_source = vendor_root.join("native/src/docking/fixed64_so3.cpp");
    let docking_fixed64_indexed_so3_source =
        vendor_root.join("native/src/docking/fixed64_indexed_so3.cpp");
    let docking_fixed64_pipeline_source =
        vendor_root.join("native/src/docking/fixed64_pipeline.cpp");
    let docking_fixed64_producer_source =
        vendor_root.join("native/src/docking/fixed64_producer.cpp");
    let docking_fixed64_single_anchor_source =
        vendor_root.join("native/src/docking/fixed64_single_anchor.cpp");
    let docking_fixed64_downstream_source =
        vendor_root.join("native/src/docking/fixed64_downstream.cpp");
    let docking_fixed64_refinement_pipeline_source =
        vendor_root.join("native/src/docking/fixed64_refinement_pipeline.cpp");
    let docking_geometric_admission_source =
        vendor_root.join("native/src/docking/geometric_admission.cpp");
    let docking_scorer_source = vendor_root.join("native/src/docking/scorer_v1.cpp");
    let docking_pose_validity_source = vendor_root.join("native/src/docking/pose_validity.cpp");
    let docking_rigid_refinement_source =
        vendor_root.join("native/src/docking/rigid_refinement.cpp");
    let docking_stable_top_k_source = vendor_root.join("native/src/docking/stable_top_k.cpp");
    let docking_torsion_v7_source = vendor_root.join("native/src/docking/torsion_v7.cpp");
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
    let direct_ewald_c_header_probe = manifest_dir.join("abi/direct_ewald_header_c11.c");
    let direct_ewald_cpp_layout_probe = manifest_dir.join("abi/direct_ewald_layout_assertions.cpp");
    let particle_mesh_reciprocal_c_header_probe =
        manifest_dir.join("abi/particle_mesh_reciprocal_header_c11.c");
    let particle_mesh_reciprocal_cpp_layout_probe =
        manifest_dir.join("abi/particle_mesh_reciprocal_layout_assertions.cpp");
    let particle_mesh_ewald_c_header_probe =
        manifest_dir.join("abi/particle_mesh_ewald_header_c11.c");
    let particle_mesh_ewald_cpp_layout_probe =
        manifest_dir.join("abi/particle_mesh_ewald_layout_assertions.cpp");
    let composite_c_header_probe = manifest_dir.join("abi/composite_header_c11.c");
    let composite_cpp_layout_probe = manifest_dir.join("abi/composite_layout_assertions.cpp");
    let composite_dynamics_c_header_probe =
        manifest_dir.join("abi/direct_ewald_composite_dynamics_header_c11.c");
    let composite_dynamics_cpp_layout_probe =
        manifest_dir.join("abi/direct_ewald_composite_dynamics_layout_assertions.cpp");
    track(&c_header_probe);
    track(&cpp_layout_probe);
    track(&direct_ewald_c_header_probe);
    track(&direct_ewald_cpp_layout_probe);
    track(&particle_mesh_reciprocal_c_header_probe);
    track(&particle_mesh_reciprocal_cpp_layout_probe);
    track(&particle_mesh_ewald_c_header_probe);
    track(&particle_mesh_ewald_cpp_layout_probe);
    track(&composite_c_header_probe);
    track(&composite_cpp_layout_probe);
    track(&composite_dynamics_c_header_probe);
    track(&composite_dynamics_cpp_layout_probe);

    let hip_safe_link = build_hip_safe_provider(&manifest_dir, &include_dir, &hip_provider_source);
    assert!(
        !qualification_build || hip_safe_link.is_none(),
        "v7 CPU qualification build cannot link hip_safe"
    );
    let mut native_build = cc::Build::new();
    native_build
        .cpp(true)
        .include(&include_dir)
        .file(&context_source)
        .file(&direct_ewald_composite_source)
        .file(&direct_ewald_composite_dynamics_source)
        .file(&direct_ewald_composite_checkpoint_source)
        .file(&particle_mesh_ewald_source)
        .file(&direct_ewald_api_source)
        .file(&direct_ewald_cpp_evaluator_source)
        .file(&direct_ewald_rust_evaluator_source)
        .file(&particle_mesh_reciprocal_api_source)
        .file(&particle_mesh_reciprocal_cpp_evaluator_source)
        .file(&particle_mesh_reciprocal_rust_evaluator_source)
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
        .file(&docking_fixed64_allocation_source)
        .file(&docking_fixed64_so3_source)
        .file(&docking_fixed64_indexed_so3_source)
        .file(&docking_fixed64_pipeline_source)
        .file(&docking_fixed64_producer_source)
        .file(&docking_fixed64_single_anchor_source)
        .file(&docking_fixed64_downstream_source)
        .file(&docking_fixed64_refinement_pipeline_source)
        .file(&docking_geometric_admission_source)
        .file(&docking_pose_validity_source)
        .file(&docking_rigid_refinement_source)
        .file(&docking_scorer_source)
        .file(&docking_stable_top_k_source)
        .file(&docking_torsion_v7_source)
        .file(&dynamics_api_source)
        .file(&dynamics_checkpoint_source)
        .file(&dynamics_common_source)
        .file(&dynamics_integrator_source)
        .file(&dynamics_sha256_source)
        .define("BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS", None)
        .define(
            "BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS",
            None,
        )
        .define(
            "BG_DISABLE_PARTICLE_MESH_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS",
            None,
        );
    if qualification_build {
        native_build
            .compiler(QUALIFICATION_CPP_COMPILER)
            .no_default_flags(true);
        for flag in QUALIFICATION_CPP_FLAGS {
            native_build.flag(flag);
        }
    } else {
        native_build
            .std("c++17")
            .warnings(true)
            .warnings_into_errors(true);
    }
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
    if qualification_build {
        assert!(
            !native_build.get_compiler().is_like_msvc(),
            "v7 CPU qualification compiler must be GNU C++"
        );
    } else if native_build.get_compiler().is_like_msvc() {
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
        .include(&include_dir)
        .file(&direct_ewald_c_header_probe)
        .flag_if_supported("-std=c11")
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_direct_ewald_header_c11_probe");

    cc::Build::new()
        .include(&include_dir)
        .file(&particle_mesh_reciprocal_c_header_probe)
        .flag_if_supported("-std=c11")
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_particle_mesh_reciprocal_header_c11_probe");

    cc::Build::new()
        .include(&include_dir)
        .file(&particle_mesh_ewald_c_header_probe)
        .flag_if_supported("-std=c11")
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_particle_mesh_ewald_header_c11_probe");

    cc::Build::new()
        .include(&include_dir)
        .file(&composite_c_header_probe)
        .flag_if_supported("-std=c11")
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_composite_header_c11_probe");

    cc::Build::new()
        .include(&include_dir)
        .file(&composite_dynamics_c_header_probe)
        .flag_if_supported("-std=c11")
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_composite_dynamics_header_c11_probe");

    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&cpp_layout_probe)
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_cpp_layout_probe");

    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&direct_ewald_cpp_layout_probe)
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_direct_ewald_cpp_layout_probe");

    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&particle_mesh_reciprocal_cpp_layout_probe)
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_particle_mesh_reciprocal_cpp_layout_probe");

    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&particle_mesh_ewald_cpp_layout_probe)
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_particle_mesh_ewald_cpp_layout_probe");

    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&composite_cpp_layout_probe)
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_composite_cpp_layout_probe");

    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&composite_dynamics_cpp_layout_probe)
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_sys_composite_dynamics_cpp_layout_probe");
}
