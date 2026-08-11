use std::path::{Path, PathBuf};
use std::process::Command;

const QUALIFIED_ROCM_RELEASE_PREFIX: &str = "6.0.2-";

fn track(path: &Path) {
    println!("cargo:rerun-if-changed={}", path.display());
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
    repository_root: &Path,
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
    let legacy_root = repository_root
        .join("third_party")
        .canonicalize()
        .expect("repository third_party directory must resolve");
    assert!(
        !device_lib_path.starts_with(&legacy_root),
        "hip_safe rejects repository legacy ROCm device libraries"
    );
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
            repository_root.join("native/src/hip").display()
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
    let tensor_source = repository_root.join("native/src/tensor.cpp");
    let cpu_evaluator_header = repository_root.join("native/src/cpu/evaluator.hpp");
    let cpu_evaluator_source = repository_root.join("native/src/cpu/evaluator.cpp");
    let hip_provider_header = repository_root.join("native/src/hip/provider.h");
    let hip_provider_source = repository_root.join("native/src/hip/provider.hip");
    let hip_evaluator_header = repository_root.join("native/src/hip/evaluator.hpp");
    let hip_evaluator_source = repository_root.join("native/src/hip/evaluator.cpp");
    let rust_provider_header = repository_root.join("native/src/rust/provider.h");
    let rust_evaluator_header = repository_root.join("native/src/rust/evaluator.hpp");
    let rust_evaluator_source = repository_root.join("native/src/rust/evaluator.cpp");
    let c_header_probe = manifest_dir.join("abi/header_c11.c");
    let cpp_layout_probe = manifest_dir.join("abi/layout_assertions.cpp");

    track(&include_dir.join("betelgeuze/engine.h"));
    track(&internal_header);
    track(&context_source);
    track(&evaluator_source);
    track(&forcefield_source);
    track(&system_source);
    track(&tensor_source);
    track(&cpu_evaluator_header);
    track(&cpu_evaluator_source);
    track(&hip_provider_header);
    track(&hip_provider_source);
    track(&hip_evaluator_header);
    track(&hip_evaluator_source);
    track(&rust_provider_header);
    track(&rust_evaluator_header);
    track(&rust_evaluator_source);
    track(&c_header_probe);
    track(&cpp_layout_probe);

    let hip_safe_link =
        build_hip_safe_provider(&repository_root, &include_dir, &hip_provider_source);
    let mut native_build = cc::Build::new();
    native_build
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&context_source)
        .file(&evaluator_source)
        .file(&forcefield_source)
        .file(&system_source)
        .file(&tensor_source)
        .define("BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS", None)
        .file(&cpu_evaluator_source)
        .define(
            "BG_HAS_HIP_SAFE_PROVIDER",
            if hip_safe_link.is_some() { "1" } else { "0" },
        )
        .file(&hip_evaluator_source)
        .file(&rust_evaluator_source)
        .warnings(true)
        .warnings_into_errors(true);
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
