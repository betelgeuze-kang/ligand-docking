use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use sha2::{Digest as _, Sha256};

const SOURCE_MANIFEST_RELATIVE_PATH: &str =
    "config/engine_v2_native_fixed64_cpu_profile_v6_sources.json";
const PACKAGED_SOURCE_MANIFEST_BYTES: &[u8] =
    include_bytes!("assets/engine_v2_native_fixed64_cpu_profile_v6_sources.json");
const COMPILED_MANIFEST_ENV: &str = "BETELGEUZE_V6_COMPILED_SOURCE_MANIFEST_SHA256";
const COMPILED_SOURCE_COUNT_ENV: &str = "BETELGEUZE_V6_COMPILED_SOURCE_COUNT";
const VERIFIED_SOURCE_ROOT_ENV: &str = "BETELGEUZE_V6_VERIFIED_SOURCE_ROOT";

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
    let source_root_text = source_root
        .to_str()
        .expect("v6 verified source root must be UTF-8");
    println!("cargo:rustc-env={COMPILED_MANIFEST_ENV}={manifest_sha256}");
    println!("cargo:rustc-env={COMPILED_SOURCE_COUNT_ENV}={source_count}");
    println!("cargo:rustc-env={VERIFIED_SOURCE_ROOT_ENV}={source_root_text}");
}
