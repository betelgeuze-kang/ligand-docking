use std::env;
use std::ffi::{OsStr, OsString};
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::Command;

use sha2::{Digest as _, Sha256};

const SOURCE_MANIFEST_RELATIVE_PATH: &str =
    "config/engine_v2_native_fixed64_cpu_profile_v6_sources.json";
const PROFILE_RELATIVE_PATH: &str = "config/engine_v2_native_fixed64_cpu_profile_v6.json";
const PACKAGED_SOURCE_MANIFEST_BYTES: &[u8] =
    include_bytes!("assets/engine_v2_native_fixed64_cpu_profile_v6_sources.json");
const PACKAGED_PROFILE_BYTES: &[u8] =
    include_bytes!("assets/engine_v2_native_fixed64_cpu_profile_v6.json");
const COMPILED_MANIFEST_ENV: &str = "BETELGEUZE_V6_COMPILED_SOURCE_MANIFEST_SHA256";
const COMPILED_SOURCE_COUNT_ENV: &str = "BETELGEUZE_V6_COMPILED_SOURCE_COUNT";
const COMPILED_PROFILE_ENV: &str = "BETELGEUZE_V6_COMPILED_PROFILE_SHA256";
const BUILD_COMMIT_ENV: &str = "BETELGEUZE_V6_BUILD_COMMIT_OID";
const BUILD_COMMIT_BOUND_ENV: &str = "BETELGEUZE_V6_BUILD_COMMIT_BOUND";
const BUILD_CONFIGURATION_BOUND_ENV: &str = "BETELGEUZE_V6_BUILD_CONFIGURATION_BOUND";
const BUILD_CONFIGURATION_SHA256_ENV: &str = "BETELGEUZE_V6_BUILD_CONFIGURATION_SHA256";
const VERIFIED_SOURCE_ROOT_ENV: &str = "BETELGEUZE_V6_VERIFIED_SOURCE_ROOT";
const NON_AUTHORITATIVE_PACKAGE_BUILD_ENV: &str = "BETELGEUZE_V6_NON_AUTHORITATIVE_PACKAGE_BUILD";
const QUALIFICATION_BUILD_ENV: &str = "BETELGEUZE_V6_QUALIFICATION_BUILD";
const UNBOUND_BUILD_COMMIT_OID: &str = "0000000000000000000000000000000000000000";
const UNBOUND_BUILD_CONFIGURATION_SHA256: &str =
    "0000000000000000000000000000000000000000000000000000000000000000";
const EXPECTED_BUILD_CONFIGURATION_SHA256: &str =
    "28b7b3d8533456d27539b8cfb0fb2c03e9afe68198b81a60839a9f5e9c271c9f";
const EXPECTED_RUSTC_SHA256: &str =
    "d32249a7c3bfcfc67b471460386e46323accae7125e344567a12d5664d99bb57";
const EXPECTED_CARGO_SHA256: &str =
    "9548937d530bf439ff1ba47a3b2bd26eeb9c3aff1961c20c01798613de922578";
const EXPECTED_CPP_PATH: &str = "/usr/bin/x86_64-linux-gnu-g++-11";
const EXPECTED_CPP_SHA256: &str =
    "2360901d864cf10bfd6296e261cb2c14053552a80377761ab07146ec9ec9a2c0";
const QUALIFICATION_RUSTC_WRAPPER_RELATIVE_PATH: &str =
    "tools/verify_engine_v2_native_fixed64_cpu_v6_rustc_wrapper.py";
const EXPECTED_RUSTC_WRAPPER_SHA256: &str =
    "97cbf0ae815235be44e23f1fce2c34391e1d7c037be7d8e923daf0ed2c956c45";
const EXPECTED_RUSTC_WRAPPER_INTERPRETER: &str = "/usr/bin/python3.10";
const EXPECTED_RUSTC_WRAPPER_INTERPRETER_SHA256: &str =
    "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86";

const FORBIDDEN_BUILD_ENVIRONMENT: &[&str] = &[
    "AR",
    "CC",
    "CFLAGS",
    "CPPFLAGS",
    "CXX",
    "CXXFLAGS",
    "LDFLAGS",
    "RANLIB",
    "RUSTC_BOOTSTRAP",
    "RUSTDOCFLAGS",
    "RUSTC_WORKSPACE_WRAPPER",
    "RUSTFLAGS",
    "CARGO_BUILD_RUSTC",
    "CARGO_BUILD_RUSTC_WRAPPER",
    "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
    "CARGO_BUILD_RUSTFLAGS",
    "CARGO_BUILD_TARGET",
    "CARGO_INCREMENTAL",
    "HOST_AR",
    "HOST_CC",
    "HOST_CFLAGS",
    "HOST_CXX",
    "HOST_CXXFLAGS",
    "TARGET_AR",
    "TARGET_CC",
    "TARGET_CFLAGS",
    "TARGET_CXX",
    "TARGET_CXXFLAGS",
    "AR_x86_64_unknown_linux_gnu",
    "CC_x86_64_unknown_linux_gnu",
    "CFLAGS_x86_64_unknown_linux_gnu",
    "CXX_x86_64_unknown_linux_gnu",
    "CXXFLAGS_x86_64_unknown_linux_gnu",
    "AR_x86_64-unknown-linux-gnu",
    "CC_x86_64-unknown-linux-gnu",
    "CFLAGS_x86_64-unknown-linux-gnu",
    "CXX_x86_64-unknown-linux-gnu",
    "CXXFLAGS_x86_64-unknown-linux-gnu",
    "BETELGEUZE_HIP_SAFE",
    "ROCM_PATH",
    "HIP_PATH",
    "BG_HIP_SAFE_ARCHITECTURES",
    "BG_HIP_DEVICE_LIB_PATH",
];

#[derive(Debug)]
struct SourceRow {
    byte_count: usize,
    path: String,
    sha256: String,
}

fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn exact_environment(name: &str, expected: &str) -> bool {
    env::var(name).ok().as_deref() == Some(expected)
}

fn environment_is_absent(name: &str) -> bool {
    env::var_os(name).is_none()
}

fn resolve_program(program: &OsStr) -> Option<PathBuf> {
    let candidate = PathBuf::from(program);
    let unresolved = if candidate.components().count() > 1 {
        candidate
    } else {
        env::var_os("PATH")
            .into_iter()
            .flat_map(|value| env::split_paths(&value).collect::<Vec<_>>())
            .map(|directory| directory.join(&candidate))
            .find(|path| path.is_file())?
    };
    unresolved.canonicalize().ok()
}

fn command_text(program: &OsStr, arguments: &[&str]) -> Option<String> {
    let output = Command::new(program).args(arguments).output().ok()?;
    if !output.status.success() || !output.stderr.is_empty() {
        return None;
    }
    String::from_utf8(output.stdout).ok()
}

fn executable_matches(program: &OsStr, expected_sha256: &str) -> bool {
    let Some(path) = resolve_program(program) else {
        return false;
    };
    fs::read(path)
        .ok()
        .is_some_and(|raw| sha256_hex(&raw) == expected_sha256)
}

fn opt_in_environment(name: &str) -> bool {
    println!("cargo:rerun-if-env-changed={name}");
    match env::var(name) {
        Ok(value) => {
            assert_eq!(value, "1", "{name} must equal 1 when present");
            true
        }
        Err(env::VarError::NotPresent) => false,
        Err(env::VarError::NotUnicode(_)) => panic!("{name} must be UTF-8"),
    }
}

fn qualification_output_directory_is_exact(source_root: &Path) -> bool {
    let Some(out_dir) = env::var_os("OUT_DIR").map(PathBuf::from) else {
        return false;
    };
    let Some(canonical_out_dir) = out_dir.canonicalize().ok() else {
        return false;
    };
    let expected_build_root = source_root.join("rust/target/qualification-v6/build");
    let Some(relative) = canonical_out_dir.strip_prefix(expected_build_root).ok() else {
        return false;
    };
    let components = relative
        .iter()
        .map(OsStr::as_encoded_bytes)
        .collect::<Vec<_>>();
    components.len() == 2
        && components[0].starts_with(b"betelgeuze-runtime-")
        && components[0]["betelgeuze-runtime-".len()..]
            .iter()
            .all(u8::is_ascii_hexdigit)
        && components[1] == b"out"
}

fn qualification_rustc_wrapper_is_exact(source_root: &Path) -> bool {
    let Some(wrapper) = env::var_os("RUSTC_WRAPPER") else {
        return false;
    };
    let expected = source_root.join(QUALIFICATION_RUSTC_WRAPPER_RELATIVE_PATH);
    let Some(expected_canonical) = expected.canonicalize().ok() else {
        return false;
    };
    let metadata = fs::symlink_metadata(&expected).ok();
    metadata
        .is_some_and(|value| value.file_type().is_file() && value.permissions().mode() & 0o111 != 0)
        && resolve_program(&wrapper).as_deref() == Some(expected_canonical.as_path())
        && executable_matches(&wrapper, EXPECTED_RUSTC_WRAPPER_SHA256)
        && resolve_program(OsStr::new(EXPECTED_RUSTC_WRAPPER_INTERPRETER)).as_deref()
            == Some(Path::new(EXPECTED_RUSTC_WRAPPER_INTERPRETER))
        && executable_matches(
            OsStr::new(EXPECTED_RUSTC_WRAPPER_INTERPRETER),
            EXPECTED_RUSTC_WRAPPER_INTERPRETER_SHA256,
        )
}

fn bind_build_configuration(source_root: &Path, non_authoritative_package: bool) -> (String, bool) {
    for name in FORBIDDEN_BUILD_ENVIRONMENT {
        println!("cargo:rerun-if-env-changed={name}");
    }
    for name in [
        "CARGO",
        "CARGO_CFG_PANIC",
        "CARGO_CFG_TARGET_FEATURE",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_FEATURE_HIP",
        "DEBUG",
        "HOST",
        "OPT_LEVEL",
        "OUT_DIR",
        "PROFILE",
        "RUSTC",
        "RUSTC_WRAPPER",
        "TARGET",
    ] {
        println!("cargo:rerun-if-env-changed={name}");
    }
    let requested = opt_in_environment(QUALIFICATION_BUILD_ENV);
    if !requested {
        return (UNBOUND_BUILD_CONFIGURATION_SHA256.to_owned(), false);
    }
    assert!(
        !non_authoritative_package,
        "v6 qualification and non-authoritative package build modes are mutually exclusive"
    );
    let encoded_rustflags_empty =
        env::var_os("CARGO_ENCODED_RUSTFLAGS").is_none_or(|value| value.is_empty());
    let no_dynamic_overrides = env::vars_os().all(|(name, value)| {
        let Some(name) = name.to_str() else {
            return false;
        };
        !name.starts_with("CARGO_PROFILE_")
            && !name.starts_with("CARGO_TARGET_")
            && !name.starts_with("CARGO_UNSTABLE_")
            && (name != "CARGO_FEATURE_HIP" || value.is_empty())
    });
    let rustc = env::var_os("RUSTC").unwrap_or_else(|| OsString::from("rustc"));
    let cargo = env::var_os("CARGO").unwrap_or_else(|| OsString::from("cargo"));
    let cpp = OsStr::new(EXPECTED_CPP_PATH);
    let rustc_identity = command_text(&rustc, &["-vV"]).is_some_and(|text| {
        text.contains("commit-hash: 254b59607d4417e9dffbc307138ae5c86280fe4c\n")
            && text.contains("host: x86_64-unknown-linux-gnu\n")
            && text.contains("release: 1.93.0\n")
            && text.contains("LLVM version: 21.1.8\n")
    });
    let cargo_identity = command_text(&cargo, &["-vV"]).is_some_and(|text| {
        text.contains("release: 1.93.0\n")
            && text.contains("commit-hash: 083ac5135f967fd9dc906ab057a2315861c7a80d\n")
            && text.contains("host: x86_64-unknown-linux-gnu\n")
    });
    let cpp_identity = resolve_program(cpp).as_deref() == Some(Path::new(EXPECTED_CPP_PATH))
        && executable_matches(cpp, EXPECTED_CPP_SHA256)
        && command_text(cpp, &["-dumpfullversion", "-dumpversion"]).as_deref() == Some("11.4.0\n")
        && command_text(cpp, &["-dumpmachine"]).as_deref() == Some("x86_64-linux-gnu\n");
    let exact = exact_environment("PROFILE", "release")
        && exact_environment("OPT_LEVEL", "3")
        && exact_environment("DEBUG", "false")
        && exact_environment("HOST", "x86_64-unknown-linux-gnu")
        && exact_environment("TARGET", "x86_64-unknown-linux-gnu")
        && exact_environment("CARGO_CFG_PANIC", "unwind")
        && exact_environment("CARGO_CFG_TARGET_FEATURE", "fxsr,sse,sse2")
        && encoded_rustflags_empty
        && FORBIDDEN_BUILD_ENVIRONMENT
            .iter()
            .all(|name| environment_is_absent(name))
        && no_dynamic_overrides
        && qualification_output_directory_is_exact(source_root)
        && executable_matches(&rustc, EXPECTED_RUSTC_SHA256)
        && executable_matches(&cargo, EXPECTED_CARGO_SHA256)
        && rustc_identity
        && cargo_identity
        && cpp_identity
        && qualification_rustc_wrapper_is_exact(source_root);
    assert!(
        exact,
        "v6 qualification build does not match the frozen compiler configuration"
    );
    (EXPECTED_BUILD_CONFIGURATION_SHA256.to_owned(), true)
}

fn parse_number_line(line: &str, prefix: &str, suffix: &str) -> usize {
    line.strip_prefix(prefix)
        .and_then(|value| value.strip_suffix(suffix))
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or_else(|| panic!("invalid v6 source manifest numeric line: {line}"))
}

fn parse_string_line(line: &str, prefix: &str, suffix: &str) -> String {
    let value = line
        .strip_prefix(prefix)
        .and_then(|value| value.strip_suffix(suffix))
        .unwrap_or_else(|| panic!("invalid v6 source manifest string line: {line}"));
    assert!(
        !value.is_empty()
            && value.is_ascii()
            && !value.contains('\\')
            && !value.contains('"')
            && !value.split('/').any(|component| component == ".."),
        "unsafe v6 source manifest value: {value}"
    );
    value.to_owned()
}

fn parse_source_manifest(raw: &[u8]) -> Vec<SourceRow> {
    let text = std::str::from_utf8(raw).expect("v6 source manifest must be UTF-8");
    let lines = text.lines().map(str::trim).collect::<Vec<_>>();
    let declared_count = lines
        .iter()
        .find(|line| line.starts_with("\"source_count\":"))
        .map(|line| parse_number_line(line, "\"source_count\": ", ""))
        .expect("v6 source manifest source_count is missing");
    let mut rows = Vec::with_capacity(declared_count);
    let mut index = 0;
    while index < lines.len() {
        if lines[index].starts_with("\"byte_count\":") {
            assert!(index + 2 < lines.len(), "truncated v6 source manifest row");
            rows.push(SourceRow {
                byte_count: parse_number_line(lines[index], "\"byte_count\": ", ","),
                path: parse_string_line(lines[index + 1], "\"path\": \"", "\","),
                sha256: parse_string_line(lines[index + 2], "\"sha256\": \"", "\""),
            });
            index += 3;
        } else {
            index += 1;
        }
    }
    assert_eq!(
        rows.len(),
        declared_count,
        "v6 source manifest count changed"
    );
    assert!(
        rows.windows(2).all(|pair| pair[0].path < pair[1].path),
        "v6 source manifest paths are not strictly sorted"
    );
    rows
}

fn discover_source_root(manifest_dir: &Path) -> Option<PathBuf> {
    println!("cargo:rerun-if-env-changed=BETELGEUZE_V6_SOURCE_ROOT");
    if let Some(declared) = env::var_os("BETELGEUZE_V6_SOURCE_ROOT") {
        let declared = PathBuf::from(declared);
        assert!(
            declared.is_absolute(),
            "BETELGEUZE_V6_SOURCE_ROOT is not absolute"
        );
        let canonical = declared
            .canonicalize()
            .expect("BETELGEUZE_V6_SOURCE_ROOT is unavailable");
        assert_eq!(
            declared, canonical,
            "BETELGEUZE_V6_SOURCE_ROOT is not canonical"
        );
        assert!(
            canonical.join(SOURCE_MANIFEST_RELATIVE_PATH).is_file()
                && canonical.join("rust/Cargo.toml").is_file(),
            "BETELGEUZE_V6_SOURCE_ROOT lacks the frozen source graph"
        );
        return Some(canonical);
    }
    manifest_dir.ancestors().find_map(|candidate| {
        let manifest = candidate.join(SOURCE_MANIFEST_RELATIVE_PATH);
        let workspace = candidate.join("rust/Cargo.toml");
        if manifest.is_file() && workspace.is_file() {
            candidate.canonicalize().ok()
        } else {
            None
        }
    })
}

fn git_output(source_root: &Path, arguments: &[&str]) -> Vec<u8> {
    let output = Command::new("git")
        .args(arguments)
        .current_dir(source_root)
        .env_remove("GIT_DIR")
        .env_remove("GIT_WORK_TREE")
        .env_remove("GIT_INDEX_FILE")
        .env_remove("GIT_OBJECT_DIRECTORY")
        .env_remove("GIT_ALTERNATE_OBJECT_DIRECTORIES")
        .output()
        .expect("git is required to bind the v6 build commit");
    assert!(
        output.status.success() && output.stderr.is_empty(),
        "v6 build git evidence failed closed"
    );
    output.stdout
}

fn git_path(source_root: &Path, git_relative: &str) -> PathBuf {
    let raw = git_output(source_root, &["rev-parse", "--git-path", git_relative]);
    let text = std::str::from_utf8(&raw)
        .expect("v6 Git metadata path must be UTF-8")
        .trim_end_matches('\n');
    assert!(
        !text.is_empty() && !text.contains('\r') && !text.contains('\n'),
        "v6 Git metadata path is invalid"
    );
    let path = PathBuf::from(text);
    if path.is_absolute() {
        path
    } else {
        source_root.join(path)
    }
}

fn emit_rerun_if_changed(path: &Path, label: &str) {
    let text = path
        .to_str()
        .unwrap_or_else(|| panic!("v6 {label} path must be UTF-8"));
    assert!(
        !text.contains('\r') && !text.contains('\n'),
        "v6 {label} path is invalid"
    );
    println!("cargo:rerun-if-changed={text}");
}

fn track_git_commit_inputs(source_root: &Path) {
    let head_path = git_path(source_root, "HEAD");
    let head_metadata =
        fs::symlink_metadata(&head_path).expect("v6 worktree HEAD metadata is unavailable");
    assert!(
        head_metadata.file_type().is_file() && !head_metadata.file_type().is_symlink(),
        "v6 worktree HEAD is not a regular file"
    );
    emit_rerun_if_changed(&head_path, "worktree HEAD");
    let head = fs::read_to_string(&head_path).expect("v6 worktree HEAD is unavailable");
    if let Some(reference) = head.strip_prefix("ref: ") {
        let reference = reference.trim_end_matches('\n').trim_end_matches('\r');
        assert!(
            reference.starts_with("refs/heads/")
                && reference.is_ascii()
                && !reference.contains("..")
                && !reference.contains('\\'),
            "v6 symbolic HEAD reference is invalid"
        );
        let reference_path = git_path(source_root, reference);
        let packed_refs_path = git_path(source_root, "packed-refs");
        if reference_path.is_file() {
            emit_rerun_if_changed(&reference_path, "symbolic HEAD reference");
        } else {
            assert!(
                packed_refs_path.is_file(),
                "v6 symbolic HEAD target is unavailable"
            );
        }
        if packed_refs_path.is_file() {
            emit_rerun_if_changed(&packed_refs_path, "packed refs");
        }
    }
}

fn committed_blob(source_root: &Path, commit_oid: &str, relative: &str) -> Vec<u8> {
    let object = format!("{commit_oid}:{relative}");
    git_output(source_root, &["cat-file", "blob", &object])
}

fn non_authoritative_package_build() -> bool {
    println!("cargo:rerun-if-env-changed={NON_AUTHORITATIVE_PACKAGE_BUILD_ENV}");
    match env::var(NON_AUTHORITATIVE_PACKAGE_BUILD_ENV) {
        Ok(value) => {
            assert_eq!(
                value, "1",
                "non-authoritative v6 package build opt-in must equal 1"
            );
            true
        }
        Err(env::VarError::NotPresent) => false,
        Err(env::VarError::NotUnicode(_)) => {
            panic!("non-authoritative v6 package build opt-in must be UTF-8")
        }
    }
}

fn bind_activation_snapshot(
    source_root: &Path,
    canonical_manifest: &[u8],
    non_authoritative_package: bool,
) -> (String, String, bool) {
    let canonical_profile_path = source_root.join(PROFILE_RELATIVE_PATH);
    println!(
        "cargo:rerun-if-changed={}",
        canonical_profile_path.display()
    );
    let canonical_profile =
        fs::read(&canonical_profile_path).expect("canonical v6 profile is unavailable");
    assert_eq!(
        canonical_profile, PACKAGED_PROFILE_BYTES,
        "packaged v6 activation profile drifted from the build checkout"
    );
    let profile_sha256 = sha256_hex(&canonical_profile);
    if non_authoritative_package {
        return (UNBOUND_BUILD_COMMIT_OID.to_owned(), profile_sha256, false);
    }
    track_git_commit_inputs(source_root);
    let raw_oid = git_output(source_root, &["rev-parse", "--verify", "HEAD"]);
    let commit_oid = std::str::from_utf8(&raw_oid)
        .expect("v6 build commit must be UTF-8")
        .trim_end_matches('\n');
    assert!(
        commit_oid.len() == 40
            && commit_oid
                .bytes()
                .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase()),
        "v6 build commit identity is invalid"
    );
    assert_eq!(
        canonical_manifest,
        committed_blob(source_root, commit_oid, SOURCE_MANIFEST_RELATIVE_PATH),
        "v6 source manifest differs from the exact build commit"
    );
    assert_eq!(
        canonical_profile,
        committed_blob(source_root, commit_oid, PROFILE_RELATIVE_PATH),
        "v6 activation profile differs from the exact build commit"
    );
    (commit_oid.to_owned(), profile_sha256, true)
}

fn bind_compiled_source_graph(source_root: &Path) -> (String, usize) {
    let canonical_manifest_path = source_root.join(SOURCE_MANIFEST_RELATIVE_PATH);
    println!(
        "cargo:rerun-if-changed={}",
        canonical_manifest_path.display()
    );
    let canonical_manifest =
        fs::read(&canonical_manifest_path).expect("canonical v6 source manifest is unavailable");
    assert_eq!(
        canonical_manifest, PACKAGED_SOURCE_MANIFEST_BYTES,
        "packaged v6 source manifest drifted from the build checkout"
    );
    let rows = parse_source_manifest(&canonical_manifest);
    for row in &rows {
        let path = source_root.join(&row.path);
        println!("cargo:rerun-if-changed={}", path.display());
        let metadata = fs::symlink_metadata(&path)
            .unwrap_or_else(|error| panic!("v6 source {} is unavailable: {error}", row.path));
        assert!(
            metadata.file_type().is_file() && !metadata.file_type().is_symlink(),
            "v6 source {} is not a regular file",
            row.path
        );
        let raw = fs::read(&path)
            .unwrap_or_else(|error| panic!("v6 source {} cannot be read: {error}", row.path));
        assert_eq!(
            raw.len(),
            row.byte_count,
            "v6 source {} byte count changed",
            row.path
        );
        assert_eq!(
            sha256_hex(&raw),
            row.sha256,
            "v6 source {} digest changed",
            row.path
        );
    }
    (sha256_hex(&canonical_manifest), rows.len())
}

fn main() {
    println!("cargo:rustc-check-cfg=cfg(betelgeuze_v6_qualification_build)");
    println!("cargo:rustc-check-cfg=cfg(betelgeuze_v6_effective_rust_flags_verified)");
    println!("cargo:rerun-if-changed=assets/engine_v2_native_fixed64_cpu_profile_v6_sources.json");
    println!("cargo:rerun-if-changed=assets/original-Cargo.toml");
    let manifest_dir =
        PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR is required"));
    let source_root = discover_source_root(&manifest_dir).expect(
        "v6 builds require the exact source checkout; set BETELGEUZE_V6_SOURCE_ROOT for packaged verification",
    );
    let (manifest_sha256, source_count) = bind_compiled_source_graph(&source_root);
    let canonical_manifest = fs::read(source_root.join(SOURCE_MANIFEST_RELATIVE_PATH))
        .expect("canonical v6 source manifest is unavailable");
    let non_authoritative_package = non_authoritative_package_build();
    let (build_configuration_sha256, build_configuration_bound) =
        bind_build_configuration(&source_root, non_authoritative_package);
    let (build_commit_oid, profile_sha256, build_commit_bound) =
        bind_activation_snapshot(&source_root, &canonical_manifest, non_authoritative_package);
    let source_root_text = source_root
        .to_str()
        .expect("v6 verified source root must be UTF-8");
    println!("cargo:rustc-env={COMPILED_MANIFEST_ENV}={manifest_sha256}");
    println!("cargo:rustc-env={COMPILED_SOURCE_COUNT_ENV}={source_count}");
    println!("cargo:rustc-env={COMPILED_PROFILE_ENV}={profile_sha256}");
    println!("cargo:rustc-env={BUILD_COMMIT_ENV}={build_commit_oid}");
    println!("cargo:rustc-env={BUILD_COMMIT_BOUND_ENV}={build_commit_bound}");
    if build_configuration_bound {
        println!("cargo:rustc-cfg=betelgeuze_v6_qualification_build");
    }
    println!("cargo:rustc-env={BUILD_CONFIGURATION_SHA256_ENV}={build_configuration_sha256}");
    println!("cargo:rustc-env={BUILD_CONFIGURATION_BOUND_ENV}={build_configuration_bound}");
    println!("cargo:rustc-env={VERIFIED_SOURCE_ROOT_ENV}={source_root_text}");
}
