use std::process::Command;
use std::path::PathBuf;

fn main() {
    let rocm_path = "/opt/rocm-6.0.2";
    let out_dir = std::env::var("OUT_DIR").unwrap();
    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap();

    let device_lib_path = std::env::var("ROCM_DEVICE_LIB_PATH").ok().or_else(|| {
        let candidate = PathBuf::from(&manifest_dir)
            .join("../third_party/rocm_device_libs_pkg/extracted/opt/rocm-5.7.1/amdgcn/bitcode");
        if candidate.exists() {
            Some(candidate.to_string_lossy().to_string())
        } else {
            None
        }
    });

    println!("cargo:rerun-if-changed=src/nonbonded_kernel.hip");
    println!("cargo:rerun-if-changed=src/lib.rs");
    println!("cargo:rerun-if-changed=../third_party/rocm_device_libs_pkg/extracted/opt/rocm-5.7.1/amdgcn/bitcode");

    let mut hip_cmd = Command::new(format!("{}/bin/hipcc", rocm_path));
    hip_cmd.args(&[
            "-c", "src/nonbonded_kernel.hip",
            "-o", &format!("{}/nonbonded_kernel.o", out_dir),
            "--offload-arch=gfx1030",
            "-O3", "-ffast-math", "-munsafe-fp-atomics",
            "-fPIC",
            &format!("-I{}/include", rocm_path),
            &format!("--rocm-path={}", rocm_path),
        ]);
    if let Some(path) = device_lib_path.as_ref() {
        hip_cmd.arg(format!("--rocm-device-lib-path={}", path));
    }
    let hip_status = hip_cmd.status().expect("HIP 커널 컴파일 실패");
    if !hip_status.success() {
        panic!("HIP 커널 컴파일 실패: hipcc exit={}", hip_status);
    }

    let ar_status = Command::new("ar")
        .args(&[
            "rcs",
            &format!("{}/libnonbonded_kernel.a", out_dir),
            &format!("{}/nonbonded_kernel.o", out_dir),
        ])
        .status()
        .expect("정적 라이브러리 생성 실패");
    if !ar_status.success() {
        panic!("정적 라이브러리 생성 실패: ar exit={}", ar_status);
    }
    
    println!("cargo:rustc-link-search=native={}", out_dir);
    println!("cargo:rustc-link-lib=static=nonbonded_kernel");
    println!("cargo:rustc-link-search=native={}/lib", rocm_path);
    println!("cargo:rustc-link-lib=dylib=amdhip64");
    println!("cargo:rustc-link-lib=dylib=hiprtc");
}
