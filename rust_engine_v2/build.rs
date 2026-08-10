use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    verify_release_profile_contract(&manifest);
    let lock = manifest.join("Cargo.lock");
    let lock_sha256 = format!("{:x}", Sha256::digest(fs::read(&lock).unwrap()));
    let (source_closure_sha256, source_closure_file_count, source_paths) =
        source_closure(&manifest);
    let rustc = Command::new(std::env::var("RUSTC").unwrap_or_else(|_| "rustc".into()))
        .arg("--version")
        .output()
        .expect("rustc --version must run");
    let rustc_version = String::from_utf8(rustc.stdout).expect("rustc version is UTF-8");
    let target = std::env::var("TARGET").expect("Cargo TARGET is set");
    let profile = std::env::var("PROFILE").expect("Cargo PROFILE is set");
    let opt_level = std::env::var("OPT_LEVEL").expect("Cargo OPT_LEVEL is set");
    let debug = std::env::var("DEBUG").expect("Cargo DEBUG is set");
    let build_flags = if profile == "release" {
        format!(
            "profile={profile},codegen-units=1,debug={debug},lto=fat,opt-level={opt_level},panic=abort,strip=symbols"
        )
    } else {
        format!("profile={profile},debug={debug},opt-level={opt_level},development-build")
    };
    for path in source_paths {
        println!("cargo:rerun-if-changed={}", path.display());
    }
    println!("cargo:rerun-if-changed=src");
    println!("cargo:rerun-if-changed=../rust/betelgeuze-docking-search/src");
    println!("cargo:rustc-env=BETELGEUZE_CARGO_LOCK_SHA256={lock_sha256}");
    println!("cargo:rustc-env=BETELGEUZE_NATIVE_SOURCE_CLOSURE_SHA256={source_closure_sha256}");
    println!(
        "cargo:rustc-env=BETELGEUZE_NATIVE_SOURCE_CLOSURE_FILE_COUNT={source_closure_file_count}"
    );
    println!(
        "cargo:rustc-env=BETELGEUZE_RUSTC_VERSION={}",
        rustc_version.trim()
    );
    println!("cargo:rustc-env=BETELGEUZE_TARGET_TRIPLE={target}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_PROFILE={profile}");
    println!("cargo:rustc-env=BETELGEUZE_OPT_LEVEL={opt_level}");
    println!("cargo:rustc-env=BETELGEUZE_DEBUG={debug}");
    println!("cargo:rustc-env=BETELGEUZE_BUILD_FLAGS={build_flags}");
}

fn verify_release_profile_contract(manifest: &Path) {
    const RELEASE_PROFILE: &str = concat!(
        "[profile.release]\n",
        "codegen-units = 1\n",
        "lto = \"fat\"\n",
        "opt-level = 3\n",
        "panic = \"abort\"\n",
        "strip = \"symbols\"\n",
    );
    let cargo_toml = fs::read_to_string(manifest.join("Cargo.toml"))
        .expect("native Cargo.toml must be readable");
    if !cargo_toml.contains(RELEASE_PROFILE) {
        panic!("native release profile no longer matches the frozen wheel contract");
    }
}

fn source_closure(manifest: &Path) -> (String, usize, Vec<PathBuf>) {
    let repository = manifest
        .parent()
        .expect("native crate must be inside the repository");
    let dependency = repository.join("rust/betelgeuze-docking-search");
    let mut paths = vec![
        manifest.join("Cargo.toml"),
        manifest.join("Cargo.lock"),
        manifest.join("build.rs"),
        repository.join("rust/Cargo.toml"),
        dependency.join("Cargo.toml"),
        repository.join("LICENSE"),
    ];
    collect_regular_files(&manifest.join("src"), &mut paths);
    collect_regular_files(&dependency.join("src"), &mut paths);
    paths.sort_by(|left, right| {
        closure_label(repository, left).cmp(&closure_label(repository, right))
    });
    paths.dedup();

    let mut digest = Sha256::new();
    digest.update(b"betelgeuze.engine-v2.native-source-closure/v1\0");
    for path in &paths {
        let label = closure_label(repository, path);
        let bytes = read_regular_file(path);
        digest.update((label.len() as u64).to_be_bytes());
        digest.update(label.as_bytes());
        digest.update((bytes.len() as u64).to_be_bytes());
        digest.update(&bytes);
    }
    (format!("{:x}", digest.finalize()), paths.len(), paths)
}

fn collect_regular_files(root: &Path, output: &mut Vec<PathBuf>) {
    let root_metadata = fs::symlink_metadata(root).unwrap_or_else(|error| {
        panic!(
            "cannot identify native source directory {}: {error}",
            root.display()
        )
    });
    if root_metadata.file_type().is_symlink() || !root_metadata.is_dir() {
        panic!(
            "native source directory must be a non-symlink directory: {}",
            root.display()
        );
    }
    let mut entries: Vec<_> = fs::read_dir(root)
        .unwrap_or_else(|error| {
            panic!(
                "cannot read native source directory {}: {error}",
                root.display()
            )
        })
        .map(|entry| {
            entry
                .expect("native source directory entry must be readable")
                .path()
        })
        .collect();
    entries.sort();
    for path in entries {
        let metadata = fs::symlink_metadata(&path).unwrap_or_else(|error| {
            panic!("cannot identify native source {}: {error}", path.display())
        });
        if metadata.file_type().is_symlink() {
            panic!("native source closure rejects symlink: {}", path.display());
        }
        if metadata.is_dir() {
            collect_regular_files(&path, output);
        } else if metadata.is_file() {
            output.push(path);
        } else {
            panic!(
                "native source closure rejects non-regular entry: {}",
                path.display()
            );
        }
    }
}

fn read_regular_file(path: &Path) -> Vec<u8> {
    let metadata = fs::symlink_metadata(path).unwrap_or_else(|error| {
        panic!(
            "cannot identify native source closure {}: {error}",
            path.display()
        )
    });
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        panic!(
            "native source closure entry must be a non-symlink regular file: {}",
            path.display()
        );
    }
    fs::read(path).unwrap_or_else(|error| {
        panic!(
            "cannot read native source closure {}: {error}",
            path.display()
        )
    })
}

fn closure_label(repository: &Path, path: &Path) -> String {
    path.strip_prefix(repository)
        .expect("native source must remain inside repository")
        .to_string_lossy()
        .replace('\\', "/")
}
