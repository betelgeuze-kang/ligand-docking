use std::path::{Path, PathBuf};

fn track(path: &Path) {
    println!("cargo:rerun-if-changed={}", path.display());
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
    let system_source = repository_root.join("native/src/system.cpp");
    let c_header_probe = manifest_dir.join("abi/header_c11.c");
    let cpp_layout_probe = manifest_dir.join("abi/layout_assertions.cpp");

    track(&include_dir.join("betelgeuze/engine.h"));
    track(&internal_header);
    track(&context_source);
    track(&system_source);
    track(&c_header_probe);
    track(&cpp_layout_probe);

    cc::Build::new()
        .cpp(true)
        .std("c++17")
        .include(&include_dir)
        .file(&context_source)
        .file(&system_source)
        .flag_if_supported("-fvisibility=hidden")
        .warnings(true)
        .warnings_into_errors(true)
        .compile("betelgeuze_engine");

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
