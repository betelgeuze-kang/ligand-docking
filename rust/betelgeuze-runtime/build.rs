use std::env;
use std::fs;
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
const VERIFIED_SOURCE_ROOT_ENV: &str = "BETELGEUZE_V6_VERIFIED_SOURCE_ROOT";
const NON_AUTHORITATIVE_PACKAGE_BUILD_ENV: &str = "BETELGEUZE_V6_NON_AUTHORITATIVE_PACKAGE_BUILD";
const UNBOUND_BUILD_COMMIT_OID: &str = "0000000000000000000000000000000000000000";

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
    let (build_commit_oid, profile_sha256, build_commit_bound) = bind_activation_snapshot(
        &source_root,
        &canonical_manifest,
        non_authoritative_package_build(),
    );
    let source_root_text = source_root
        .to_str()
        .expect("v6 verified source root must be UTF-8");
    println!("cargo:rustc-env={COMPILED_MANIFEST_ENV}={manifest_sha256}");
    println!("cargo:rustc-env={COMPILED_SOURCE_COUNT_ENV}={source_count}");
    println!("cargo:rustc-env={COMPILED_PROFILE_ENV}={profile_sha256}");
    println!("cargo:rustc-env={BUILD_COMMIT_ENV}={build_commit_oid}");
    println!("cargo:rustc-env={BUILD_COMMIT_BOUND_ENV}={build_commit_bound}");
    println!("cargo:rustc-env={VERIFIED_SOURCE_ROOT_ENV}={source_root_text}");
}
