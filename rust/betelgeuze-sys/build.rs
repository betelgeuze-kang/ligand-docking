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
    let evaluator_source = repository_root.join("native/src/evaluator.cpp");
    let forcefield_source = repository_root.join("native/src/forcefield.cpp");
    let system_source = repository_root.join("native/src/system.cpp");
    let tensor_source = repository_root.join("native/src/tensor.cpp");
    let cpu_evaluator_header = repository_root.join("native/src/cpu/evaluator.hpp");
    let cpu_evaluator_source = repository_root.join("native/src/cpu/evaluator.cpp");
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
    track(&rust_provider_header);
    track(&rust_evaluator_header);
    track(&rust_evaluator_source);
    track(&c_header_probe);
    track(&cpp_layout_probe);

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
