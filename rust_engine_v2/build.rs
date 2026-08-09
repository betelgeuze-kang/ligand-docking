use sha2::{Digest, Sha256};
use std::fs;
use std::path::PathBuf;
use std::process::Command;

const FROZEN_RUSTC_VERSION: &str = "rustc 1.93.0 (254b59607 2026-01-19)";
const FROZEN_RUSTC_VERBOSE_SHA256: &str =
    "a8d93365194b081bd07ccb5c7db5c4dfc843a7f04b9b5895779a90bdb3880604";
const FROZEN_TARGET: &str = "x86_64-unknown-linux-gnu";

fn sha256_file(path: &PathBuf) -> String {
    format!("{:x}", Sha256::digest(fs::read(path).unwrap()))
}

fn main() {
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    let manifest_toml = manifest.join("Cargo.toml");
    let native_pyproject = manifest.join("pyproject.toml");
    let lock = manifest.join("Cargo.lock");
    let lib = manifest.join("src/lib.rs");
    let build_script = manifest.join("build.rs");
    let native_build_wrapper = manifest
        .parent()
        .expect("native manifest has a repository parent")
        .join("tools/build_engine_v2_native_wheel.py");
    let lock_sha256 = sha256_file(&lock);
    let lib_sha256 = sha256_file(&lib);
    let manifest_sha256 = sha256_file(&manifest_toml);
    let native_pyproject_sha256 = sha256_file(&native_pyproject);
    let build_script_sha256 = sha256_file(&build_script);
    let native_build_wrapper_sha256 = if native_build_wrapper.is_file() {
        sha256_file(&native_build_wrapper)
    } else {
        "unavailable".into()
    };
    let rustc_path = PathBuf::from(std::env::var("RUSTC").expect("Cargo RUSTC is set"))
        .canonicalize()
        .expect("rustc executable must resolve");
    let rustc_executable_sha256 = sha256_file(&rustc_path);
    let rustc = Command::new(&rustc_path)
        .arg("-vV")
        .output()
        .expect("rustc -vV must run");
    assert!(rustc.status.success(), "rustc -vV must succeed");
    let rustc_verbose = String::from_utf8(rustc.stdout).expect("rustc identity is UTF-8");
    let rustc_verbose = rustc_verbose.trim();
    let rustc_version = rustc_verbose.lines().next().unwrap_or_default();
    let rustc_verbose_sha256 = format!("{:x}", Sha256::digest(rustc_verbose.as_bytes()));
    assert_eq!(
        rustc_version, FROZEN_RUSTC_VERSION,
        "rustc version is not frozen"
    );
    assert_eq!(
        rustc_verbose_sha256, FROZEN_RUSTC_VERBOSE_SHA256,
        "rustc verbose identity is not frozen"
    );
    let expected_rustc_executable_sha256 =
        std::env::var("BETELGEUZE_EXPECTED_RUSTC_EXECUTABLE_SHA256").ok();
    let expected_rustc_verbose_sha256 =
        std::env::var("BETELGEUZE_EXPECTED_RUSTC_VERBOSE_SHA256").ok();
    let expected_native_build_wrapper_sha256 =
        std::env::var("BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256").ok();
    if let Some(expected) = &expected_rustc_executable_sha256 {
        assert_eq!(
            &rustc_executable_sha256, expected,
            "rustc executable changed after wrapper verification"
        );
    }
    if let Some(expected) = &expected_rustc_verbose_sha256 {
        assert_eq!(
            &rustc_verbose_sha256, expected,
            "rustc identity changed after wrapper verification"
        );
    }
    if let Some(expected) = &expected_native_build_wrapper_sha256 {
        assert_eq!(
            &native_build_wrapper_sha256, expected,
            "native build wrapper changed after wrapper verification"
        );
    }
    let target = std::env::var("TARGET").expect("Cargo TARGET is set");
    assert_eq!(target, FROZEN_TARGET, "native build target is not frozen");
    let host = std::env::var("HOST").expect("Cargo HOST is set");
    assert_eq!(host, FROZEN_TARGET, "native build host is not frozen");
    let profile = std::env::var("PROFILE").expect("Cargo PROFILE is set");
    let opt_level = std::env::var("OPT_LEVEL").expect("Cargo OPT_LEVEL is set");
    let debug = std::env::var("DEBUG").expect("Cargo DEBUG is set");
    let build_script_cfg_panic =
        std::env::var("CARGO_CFG_PANIC").unwrap_or_else(|_| "unknown".into());
    let target_arch = std::env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_else(|_| "unknown".into());
    let target_env = std::env::var("CARGO_CFG_TARGET_ENV").unwrap_or_else(|_| "unknown".into());
    let target_features =
        std::env::var("CARGO_CFG_TARGET_FEATURE").unwrap_or_else(|_| "none".into());
    let target_os = std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_else(|_| "unknown".into());
    let encoded_rustflags = std::env::var("CARGO_ENCODED_RUSTFLAGS").unwrap_or_default();
    let rustflags_sha256 = format!("{:x}", Sha256::digest(encoded_rustflags.as_bytes()));
    let rustflags_count = if encoded_rustflags.is_empty() {
        0
    } else {
        encoded_rustflags.split('\u{1f}').count()
    };
    let wrapper_control = if expected_rustc_executable_sha256.is_some()
        && expected_rustc_verbose_sha256.is_some()
        && expected_native_build_wrapper_sha256.is_some()
    {
        "verified_frozen_wrapper"
    } else {
        "direct_cargo_unattested"
    };
    let controlled_release_profile = [
        ("codegen-units", "CARGO_PROFILE_RELEASE_CODEGEN_UNITS", "1"),
        ("debug", "CARGO_PROFILE_RELEASE_DEBUG", "0"),
        (
            "debug-assertions",
            "CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS",
            "false",
        ),
        ("incremental", "CARGO_PROFILE_RELEASE_INCREMENTAL", "false"),
        ("lto", "CARGO_PROFILE_RELEASE_LTO", "fat"),
        ("opt-level", "CARGO_PROFILE_RELEASE_OPT_LEVEL", "3"),
        (
            "overflow-checks",
            "CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS",
            "false",
        ),
        ("panic", "CARGO_PROFILE_RELEASE_PANIC", "abort"),
        ("strip", "CARGO_PROFILE_RELEASE_STRIP", "symbols"),
    ];
    let release_profile_values: Vec<(&str, String)> = controlled_release_profile
        .iter()
        .map(|(field, name, _)| {
            (
                *field,
                std::env::var(name).unwrap_or_else(|_| "unattested".into()),
            )
        })
        .collect();
    if wrapper_control == "verified_frozen_wrapper" {
        assert_eq!(profile, "release", "wrapper build profile is not release");
        assert_eq!(opt_level, "3", "wrapper opt-level is not frozen");
        assert_eq!(debug, "false", "wrapper debug setting is not frozen");
        assert!(
            encoded_rustflags.is_empty(),
            "wrapper rustflags must be empty"
        );
        for ((field, _, expected), (_, actual)) in controlled_release_profile
            .iter()
            .zip(release_profile_values.iter())
        {
            assert_eq!(
                actual, expected,
                "wrapper release profile {field} is not frozen"
            );
        }
    }
    let release_profile_value = |field: &str| {
        release_profile_values
            .iter()
            .find(|(name, _)| *name == field)
            .map(|(_, value)| value.as_str())
            .unwrap_or("unattested")
    };
    let actual_build_flags = if wrapper_control == "verified_frozen_wrapper" {
        format!(
            "codegen-units={},lto={},opt-level={},panic={},strip={}",
            release_profile_value("codegen-units"),
            release_profile_value("lto"),
            release_profile_value("opt-level"),
            release_profile_value("panic"),
            release_profile_value("strip")
        )
    } else {
        format!(
            "profile={profile},opt-level={opt_level},debug={debug},release-profile=unattested,rustflags-sha256={rustflags_sha256}"
        )
    };
    println!("cargo:rerun-if-changed=Cargo.toml");
    println!("cargo:rerun-if-changed=pyproject.toml");
    println!("cargo:rerun-if-changed=Cargo.lock");
    println!("cargo:rerun-if-changed=src/lib.rs");
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=../tools/build_engine_v2_native_wheel.py");
    println!("cargo:rerun-if-env-changed=BETELGEUZE_EXPECTED_RUSTC_EXECUTABLE_SHA256");
    println!("cargo:rerun-if-env-changed=BETELGEUZE_EXPECTED_RUSTC_VERBOSE_SHA256");
    println!("cargo:rerun-if-env-changed=BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256");
    println!("cargo:rustc-env=BETELGEUZE_CARGO_MANIFEST_SHA256={manifest_sha256}");
    println!("cargo:rustc-env=BETELGEUZE_NATIVE_PYPROJECT_SHA256={native_pyproject_sha256}");
    println!("cargo:rustc-env=BETELGEUZE_CARGO_LOCK_SHA256={lock_sha256}");
    println!("cargo:rustc-env=BETELGEUZE_RUST_LIB_SHA256={lib_sha256}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_SCRIPT_SHA256={build_script_sha256}");
    println!(
        "cargo:rustc-env=BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256={native_build_wrapper_sha256}"
    );
    println!("cargo:rustc-env=BETELGEUZE_RUSTC_VERSION={}", rustc_version);
    println!("cargo:rustc-env=BETELGEUZE_RUSTC_VERBOSE_SHA256={rustc_verbose_sha256}");
    println!("cargo:rustc-env=BETELGEUZE_RUSTC_EXECUTABLE_SHA256={rustc_executable_sha256}");
    println!("cargo:rustc-env=BETELGEUZE_TARGET_TRIPLE={target}");
    println!("cargo:rustc-env=BETELGEUZE_HOST_TRIPLE={host}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_PROFILE={profile}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_OPT_LEVEL={opt_level}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_DEBUG={debug}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_SCRIPT_CFG_PANIC={build_script_cfg_panic}");
    println!(
        "cargo:rustc-env=BETELGEUZE_RELEASE_CODEGEN_UNITS={}",
        release_profile_value("codegen-units")
    );
    println!(
        "cargo:rustc-env=BETELGEUZE_RELEASE_DEBUG_ASSERTIONS={}",
        release_profile_value("debug-assertions")
    );
    println!(
        "cargo:rustc-env=BETELGEUZE_RELEASE_INCREMENTAL={}",
        release_profile_value("incremental")
    );
    println!(
        "cargo:rustc-env=BETELGEUZE_RELEASE_LTO={}",
        release_profile_value("lto")
    );
    println!(
        "cargo:rustc-env=BETELGEUZE_RELEASE_OVERFLOW_CHECKS={}",
        release_profile_value("overflow-checks")
    );
    println!(
        "cargo:rustc-env=BETELGEUZE_RELEASE_PANIC={}",
        release_profile_value("panic")
    );
    println!(
        "cargo:rustc-env=BETELGEUZE_RELEASE_STRIP={}",
        release_profile_value("strip")
    );
    println!("cargo:rustc-env=BETELGEUZE_TARGET_ARCH={target_arch}");
    println!("cargo:rustc-env=BETELGEUZE_TARGET_ENV={target_env}");
    println!("cargo:rustc-env=BETELGEUZE_TARGET_FEATURES={target_features}");
    println!("cargo:rustc-env=BETELGEUZE_TARGET_OS={target_os}");
    println!("cargo:rustc-env=BETELGEUZE_RUSTFLAGS_SHA256={rustflags_sha256}");
    println!("cargo:rustc-env=BETELGEUZE_RUSTFLAGS_COUNT={rustflags_count}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_WRAPPER_CONTROL={wrapper_control}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_FLAGS={actual_build_flags}");
}
