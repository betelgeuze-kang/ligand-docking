use sha2::{Digest, Sha256};
use std::fs;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    let manifest = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    let lock = manifest.join("Cargo.lock");
    let lock_sha256 = format!("{:x}", Sha256::digest(fs::read(&lock).unwrap()));
    let rustc = Command::new(std::env::var("RUSTC").unwrap_or_else(|_| "rustc".into()))
        .arg("--version")
        .output()
        .expect("rustc --version must run");
    let rustc_version = String::from_utf8(rustc.stdout).expect("rustc version is UTF-8");
    let target = std::env::var("TARGET").expect("Cargo TARGET is set");
    println!("cargo:rerun-if-changed=Cargo.lock");
    println!("cargo:rerun-if-changed=src/lib.rs");
    println!("cargo:rustc-env=BETELGEUZE_CARGO_LOCK_SHA256={lock_sha256}");
    println!(
        "cargo:rustc-env=BETELGEUZE_RUSTC_VERSION={}",
        rustc_version.trim()
    );
    println!("cargo:rustc-env=BETELGEUZE_TARGET_TRIPLE={target}");
    println!(
        "cargo:rustc-env=BETELGEUZE_BUILD_FLAGS=codegen-units=1,lto=fat,opt-level=3,panic=abort,strip=symbols"
    );
}
