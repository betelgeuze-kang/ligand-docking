#!/usr/bin/env python3
"""Build a fail-closed Engine v2 native wheel from a frozen CPU or HIP profile."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Iterator, Mapping
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 release lane
    import tomli as tomllib


NATIVE_VERSION = "0.2.0rc6"
CPU_PROFILE_ID = "cpu-manylinux_2_28-gcc14"
HIP_GFX1030_PROFILE_ID = "hip-gfx1030-rocm602"
RUSTC_VERSION = "rustc 1.93.0 (254b59607 2026-01-19)"
RUSTC_VERBOSE_VERSION = """rustc 1.93.0 (254b59607 2026-01-19)
binary: rustc
commit-hash: 254b59607d4417e9dffbc307138ae5c86280fe4c
commit-date: 2026-01-19
host: x86_64-unknown-linux-gnu
release: 1.93.0
LLVM version: 21.1.8"""
FROZEN_TARGET = "x86_64-unknown-linux-gnu"
DEFAULT_SOURCE_DATE_EPOCH = 1_735_689_600
_MAX_CARGO_CONFIG_BYTES = 1_048_576
_FROZEN_RELEASE_PROFILE: dict[str, object] = {
    "codegen-units": 1,
    "lto": "fat",
    "opt-level": 3,
    "panic": "abort",
    "strip": "symbols",
}
_DIRECT_BUILD_OVERRIDE_NAMES = frozenset(
    {
        "CARGO",
        "CARGO_BUILD_RUSTC",
        "CARGO_BUILD_RUSTC_WRAPPER",
        "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
        "CARGO_BUILD_RUSTFLAGS",
        "CARGO_BUILD_TARGET",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_INCREMENTAL",
        "CRATE_CC_NO_DEFAULTS",
        "BETELGEUZE_EXPECTED_RUSTC_EXECUTABLE_SHA256",
        "BETELGEUZE_EXPECTED_RUSTC_VERBOSE_SHA256",
        "BETELGEUZE_EXPECTED_NATIVE_BUILD_PROFILE_ID",
        "BETELGEUZE_EXPECTED_NATIVE_CARGO_FEATURES",
        "BETELGEUZE_EXPECTED_NATIVE_TOOLCHAIN_SHA256",
        "BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256",
        "BETELGEUZE_HIP_SAFE",
        "BG_HIP_ARCHITECTURE",
        "BG_HIP_DEVICE_LIB_PATH",
        "BG_HIP_SAFE_ARCHITECTURES",
        "CC",
        "CFLAGS",
        "CPP",
        "CPPFLAGS",
        "CXX",
        "CXXFLAGS",
        "AR",
        "AS",
        "BINDGEN_EXTRA_CLANG_ARGS",
        "LD",
        "LDFLAGS",
        "HIP_CLANG_PATH",
        "HIP_COMPILER",
        "HIP_PATH",
        "HIP_PLATFORM",
        "HIP_RUNTIME",
        "HIP_USE_PERL_SCRIPTS",
        "HIPCC_COMPILE_FLAGS_APPEND",
        "HIPCC_LINK_FLAGS_APPEND",
        "PYO3_CONFIG_FILE",
        "PYO3_CROSS",
        "PYO3_CROSS_LIB_DIR",
        "PYO3_CROSS_PYTHON_VERSION",
        "PYO3_PYTHON",
        "RANLIB",
        "RUSTC",
        "RUSTC_BOOTSTRAP",
        "RUSTC_WRAPPER",
        "RUSTC_WORKSPACE_WRAPPER",
        "RUSTDOC",
        "RUSTDOCFLAGS",
        "RUSTFLAGS",
        "RUSTUP_TOOLCHAIN",
        "ROCM_DEVICE_LIB_PATH",
        "ROCM_PATH",
        "STRIP",
    }
)
_DIRECT_BUILD_OVERRIDE_PREFIXES = (
    "AR_",
    "CARGO_PROFILE_",
    "CARGO_TARGET_",
    "CARGO_UNSTABLE_",
    "CC_",
    "CFLAGS_",
    "CPP_",
    "CPPFLAGS_",
    "CXX_",
    "CXXFLAGS_",
    "LD_",
    "LDFLAGS_",
    "PYO3_",
    "RANLIB_",
)
_NATIVE_TOOL_OVERRIDE_SUFFIXES = (
    "_AR",
    "_CC",
    "_CFLAGS",
    "_CPP",
    "_CPPFLAGS",
    "_CXX",
    "_CXXFLAGS",
    "_LD",
    "_LDFLAGS",
    "_RANLIB",
)
_SANITIZED_BUILD_ENV_NAMES = frozenset(
    {
        "C_INCLUDE_PATH",
        "CPATH",
        "CPLUS_INCLUDE_PATH",
        "DYLD_LIBRARY_PATH",
        "LIBRARY_PATH",
        "LD_LIBRARY_PATH",
        "OBJC_INCLUDE_PATH",
        "CONDA_PREFIX",
        "PYTHONHOME",
        "PYTHONOPTIMIZE",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "COMPILER_PATH",
        "GCC_EXEC_PREFIX",
        "HIPCC_COMPILE_FLAGS_APPEND",
        "HIPCC_LINK_FLAGS_APPEND",
    }
)
_WHEEL_RE = re.compile(
    r"^betelgeuze_engine_v2_native-0\.2\.0rc6-cp3(?:10|11|12)-cp3(?:10|11|12)-"
    r"(?:manylinux_[0-9_]+|linux)_x86_64\.whl$"
)


@dataclass(frozen=True)
class FrozenRustToolchain:
    rustc_executable: Path
    rustc_executable_sha256: str
    rustc_verbose_sha256: str
    cargo_executable: Path


@dataclass(frozen=True)
class FrozenFileSpec:
    label: str
    path: Path
    resolved_path: Path
    sha256: str
    executable: bool = True


@dataclass(frozen=True)
class FrozenNativeToolchain:
    profile_id: str
    compatibility: str
    cc: Path
    cxx: Path
    ar: Path
    ranlib: Path
    ld: Path
    linker: Path
    assembler: Path
    strip: Path
    path_entries: tuple[Path, ...]
    cargo_features: tuple[str, ...]
    toolchain_sha256: str
    extra_environment: tuple[tuple[str, str], ...] = ()


_CPU_FILE_SPECS = (
    FrozenFileSpec(
        "cc",
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/gcc"),
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/gcc"),
        "d4348a0af561fe42f74abf8aa1f0625b0b4883356a628d5d7709441d10cab567",
    ),
    FrozenFileSpec(
        "cxx",
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/g++"),
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/g++"),
        "3842b223ab362f59c9609294d350d237da47d0b8346335ba8e8fc2061fdde99e",
    ),
    FrozenFileSpec(
        "ar",
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/ar"),
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/ar"),
        "6cffe00cfcfc46ef910670695d92a7dfc31e0563ee046bfec4c57c3eda8caf29",
    ),
    FrozenFileSpec(
        "ranlib",
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/ranlib"),
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/ranlib"),
        "84955eaa92c5f78b18747087af3a567ed53229f655b03917f2e8c3f535240beb",
    ),
    FrozenFileSpec(
        "linker",
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/ld"),
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/ld.bfd"),
        "0736b7c8d6721520bfbc31071d67c3ec20e2d1b4a77852d1a4ae0b12c38517cf",
    ),
    FrozenFileSpec(
        "assembler",
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/as"),
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/as"),
        "2b46778dc288ee60b29528142916c1b593790bd46965ee1366c0baa69285245c",
    ),
    FrozenFileSpec(
        "strip",
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/strip"),
        Path("/opt/rh/gcc-toolset-14/root/usr/bin/strip"),
        "8174a58f43a39269e507a4f547c77c25e17ad8b7db1a8a79d15fc7a61dbd2b4b",
    ),
)

_HIP_HOST_FILE_SPECS = (
    FrozenFileSpec(
        "cc",
        Path("/usr/bin/x86_64-linux-gnu-gcc-11"),
        Path("/usr/bin/x86_64-linux-gnu-gcc-11"),
        "821af3c74506283c179ca413bb33e6b528805a4dd8a5c09df125e5ad560a9e89",
    ),
    FrozenFileSpec(
        "cxx",
        Path("/usr/bin/x86_64-linux-gnu-g++-11"),
        Path("/usr/bin/x86_64-linux-gnu-g++-11"),
        "2360901d864cf10bfd6296e261cb2c14053552a80377761ab07146ec9ec9a2c0",
    ),
    FrozenFileSpec(
        "ar",
        Path("/usr/bin/x86_64-linux-gnu-ar"),
        Path("/usr/bin/x86_64-linux-gnu-ar"),
        "5b394f8752fde1776992d405d76034d5017b24b9b922bedaeeaff8cc344ef044",
    ),
    FrozenFileSpec(
        "ranlib",
        Path("/usr/bin/x86_64-linux-gnu-ranlib"),
        Path("/usr/bin/x86_64-linux-gnu-ranlib"),
        "95e470c76f1fb0383ef5c10cfdf10127aefab07dad924fe94933ec8be8a5a9fb",
    ),
    FrozenFileSpec(
        "linker",
        Path("/usr/bin/x86_64-linux-gnu-ld.bfd"),
        Path("/usr/bin/x86_64-linux-gnu-ld.bfd"),
        "58937fc20c21e147883b4fdaa0fc7438a8e8f2bb886cfcaa4896100ca91139e7",
    ),
    FrozenFileSpec(
        "assembler",
        Path("/usr/bin/x86_64-linux-gnu-as"),
        Path("/usr/bin/x86_64-linux-gnu-as"),
        "4e6b50c3faaa834150db32be778fd7d9440a4e1f5fa8beb8a72277b12159d689",
    ),
    FrozenFileSpec(
        "strip",
        Path("/usr/bin/x86_64-linux-gnu-strip"),
        Path("/usr/bin/x86_64-linux-gnu-strip"),
        "001150abd7bbfaf605f2b091a2a3db7d00aa05aba1b6c62dc7cbb416336e23c7",
    ),
)

_ROCM_ROOT = Path("/opt/rocm-6.0.2")
_ROCM_FILE_SPECS = (
    FrozenFileSpec(
        "hipcc",
        _ROCM_ROOT / "bin/hipcc",
        _ROCM_ROOT / "bin/hipcc",
        "0a133b0bb538abd5e8b31b3502680ace1562fe4151fca964b2e032c691ecd14e",
    ),
    FrozenFileSpec(
        "hipcc_perl_driver",
        _ROCM_ROOT / "bin/hipcc.pl",
        _ROCM_ROOT / "bin/hipcc.pl",
        "81e41fd947461e437983acdfe6322077cfbe558743008195a8b0cf2db08ff72e",
    ),
    FrozenFileSpec(
        "hipvars_perl_module",
        _ROCM_ROOT / "bin/hipvars.pm",
        _ROCM_ROOT / "bin/hipvars.pm",
        "072db4dcf0c6ca854972ba834acf025dd2221d0450188c3e45472e87c3777279",
        executable=False,
    ),
    FrozenFileSpec(
        "hipconfig",
        _ROCM_ROOT / "bin/hipconfig",
        _ROCM_ROOT / "bin/hipconfig",
        "51c5154066724ab7fc412517b83dde23c21c5cea5763fb8b89493767152912de",
    ),
    FrozenFileSpec(
        "clang",
        _ROCM_ROOT / "llvm/bin/clang++",
        _ROCM_ROOT / "lib/llvm/bin/clang-17",
        "4966277f9c58f01932fb136826aaf510b466c32651bf7a9e045a3277a6626149",
    ),
    FrozenFileSpec(
        "clang_driver_config",
        _ROCM_ROOT / "lib/llvm/bin/clang++.cfg",
        _ROCM_ROOT / "lib/llvm/bin/clang++.cfg",
        "e795800978f7e1ad08f20c0b3d51b97fe34c17204f6a0a71cac55de593524e40",
        executable=False,
    ),
    FrozenFileSpec(
        "rocm_driver_config",
        _ROCM_ROOT / "lib/llvm/bin/rocm.cfg",
        _ROCM_ROOT / "lib/llvm/bin/rocm.cfg",
        "f727028429d05c7b24050d54d06f7a92ec8a785b13ac4e664ab609073bcb0fe5",
        executable=False,
    ),
    FrozenFileSpec(
        "clang_offload_bundler",
        _ROCM_ROOT / "llvm/bin/clang-offload-bundler",
        _ROCM_ROOT / "lib/llvm/bin/clang-offload-bundler",
        "e2dd634b6a868dab88c307263ec69f2c132bb2c4e5590dbf8c17db1c5330a849",
    ),
    FrozenFileSpec(
        "clang_offload_packager",
        _ROCM_ROOT / "llvm/bin/clang-offload-packager",
        _ROCM_ROOT / "lib/llvm/bin/clang-offload-packager",
        "b8e45742301276c0abd964d0635ae72ece9298d0633555a71d76afceda4d11fa",
    ),
    FrozenFileSpec(
        "lld",
        _ROCM_ROOT / "llvm/bin/ld.lld",
        _ROCM_ROOT / "lib/llvm/bin/lld",
        "1a69605a3732bc876876ee8744dd5e05ca198e5e142f7ae663672f007748f4ad",
    ),
    FrozenFileSpec(
        "llvm_link",
        _ROCM_ROOT / "llvm/bin/llvm-link",
        _ROCM_ROOT / "lib/llvm/bin/llvm-link",
        "8a397bea78e669702fa62a747f4681a6c6046da1b2212cf100676c2938840b44",
    ),
    FrozenFileSpec(
        "llc",
        _ROCM_ROOT / "llvm/bin/llc",
        _ROCM_ROOT / "lib/llvm/bin/llc",
        "61dbc5ac48b8e0c73708d18eb813f3871d9d23a4a06f1fe158968954cfd84f25",
    ),
    FrozenFileSpec(
        "opt",
        _ROCM_ROOT / "llvm/bin/opt",
        _ROCM_ROOT / "lib/llvm/bin/opt",
        "a7e1eadc45c182176bd22465f2b0d566843e1b3cb36382fdde0dfa4a971aaeca",
    ),
    FrozenFileSpec(
        "amdhip64",
        _ROCM_ROOT / "lib/libamdhip64.so.6.0.60002",
        _ROCM_ROOT / "lib/libamdhip64.so.6.0.60002",
        "3210b3126e1bab3fbfe4eaaf5110562026494ab93a973daf03dbc1e603a8fceb",
        executable=False,
    ),
    FrozenFileSpec(
        "rocm_version",
        _ROCM_ROOT / ".info/version",
        _ROCM_ROOT / ".info/version",
        "4f5a23984a3bece6255e8f81cb940f7253c18948a673c5ec17fcf9828496cbac",
        executable=False,
    ),
    FrozenFileSpec(
        "perl",
        Path("/usr/bin/perl"),
        Path("/usr/bin/perl"),
        "a50d7f5b571f379d94c8d7f9ffa21a82a5839df7930e2cebb4487d9d77717358",
    ),
)

_ROCM_INCLUDE_SHA256 = "877bc7bbd9d97e4b94a28be34981b88d80428fc8d935dc14e75d873841a67c44"
_ROCM_INCLUDE_FILE_COUNT = 2_132
_ROCM_CLANG_INCLUDE_SHA256 = (
    "fc07eee01077025fc646197ddd61330d99efe54c467ea105a1f22f7c2887da40"
)
_ROCM_CLANG_INCLUDE_FILE_COUNT = 207
_ROCM_DEVICE_LIB_SHA256 = "82dedc002a0f2e2e9c72d08783d8e03737f86ceb8521c9a1810b6298ff2c75d8"
_ROCM_DEVICE_LIB_FILE_COUNT = 57


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_frozen_files(specifications: tuple[FrozenFileSpec, ...]) -> None:
    for specification in specifications:
        try:
            resolved = specification.path.resolve(strict=True)
        except OSError as error:
            raise RuntimeError(
                f"frozen native tool is unavailable: {specification.label}"
            ) from error
        if resolved != specification.resolved_path:
            raise RuntimeError(
                f"frozen native tool path changed: {specification.label}"
            )
        if not resolved.is_file():
            raise RuntimeError(
                f"frozen native tool is not a regular file: {specification.label}"
            )
        if specification.executable and not os.access(resolved, os.X_OK):
            raise RuntimeError(
                f"frozen native tool is not executable: {specification.label}"
            )
        if _sha256_path(resolved) != specification.sha256:
            raise RuntimeError(
                f"frozen native tool digest changed: {specification.label}"
            )


def _directory_closure_sha256(root: Path, domain: bytes) -> tuple[str, int]:
    try:
        root = root.resolve(strict=True)
    except OSError as error:
        raise RuntimeError(f"native toolchain closure is unavailable: {root}") from error
    if not root.is_dir():
        raise RuntimeError(f"native toolchain closure is not a directory: {root}")
    digest = hashlib.sha256()
    digest.update(domain + b"\0")
    count = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise RuntimeError(f"native toolchain closure has a non-regular entry: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"native toolchain closure has a non-regular entry: {path}")
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(b"F")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        count += 1
    return digest.hexdigest(), count


def _toolchain_manifest_sha256(
    *,
    profile_id: str,
    compatibility: str,
    cargo_features: tuple[str, ...],
    specifications: tuple[FrozenFileSpec, ...],
    closures: tuple[tuple[str, str, int], ...] = (),
) -> str:
    payload = {
        "schema_id": "betelgeuze.engine_v2_native_toolchain/1.0.0",
        "profile_id": profile_id,
        "compatibility": compatibility,
        "cargo_features": list(cargo_features),
        "files": [
            {
                "label": specification.label,
                "path": str(specification.path),
                "resolved_path": str(specification.resolved_path),
                "sha256": specification.sha256,
            }
            for specification in specifications
        ],
        "closures": [
            {"label": label, "sha256": sha256, "file_count": count}
            for label, sha256, count in closures
        ],
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def _require_closure(
    root: Path,
    *,
    domain: bytes,
    expected_sha256: str,
    expected_count: int,
    label: str,
) -> tuple[str, str, int]:
    observed_sha256, observed_count = _directory_closure_sha256(root, domain)
    if observed_count != expected_count or observed_sha256 != expected_sha256:
        raise RuntimeError(f"frozen native {label} closure changed")
    return label, observed_sha256, observed_count


def _verify_native_toolchain(
    profile_id: str,
    *,
    compatibility: str,
    rocm_root: Path | None,
    rocm_device_lib_path: Path | None,
) -> FrozenNativeToolchain:
    if profile_id == CPU_PROFILE_ID:
        if compatibility != "manylinux_2_28":
            raise RuntimeError("CPU native profile requires manylinux_2_28 compatibility")
        if rocm_root is not None or rocm_device_lib_path is not None:
            raise RuntimeError("CPU native profile rejects ROCm inputs")
        _verify_frozen_files(_CPU_FILE_SPECS)
        manifest_sha256 = _toolchain_manifest_sha256(
            profile_id=profile_id,
            compatibility=compatibility,
            cargo_features=("extension-module",),
            specifications=_CPU_FILE_SPECS,
        )
        tools = {specification.label: specification.path for specification in _CPU_FILE_SPECS}
        tool_directory = _CPU_FILE_SPECS[0].path.parent
        return FrozenNativeToolchain(
            profile_id=profile_id,
            compatibility=compatibility,
            cc=tools["cc"],
            cxx=tools["cxx"],
            ar=tools["ar"],
            ranlib=tools["ranlib"],
            ld=tools["linker"],
            linker=tools["cc"],
            assembler=tools["assembler"],
            strip=tools["strip"],
            path_entries=(tool_directory, Path("/usr/bin"), Path("/bin")),
            cargo_features=("extension-module",),
            toolchain_sha256=manifest_sha256,
        )

    if profile_id != HIP_GFX1030_PROFILE_ID:
        raise RuntimeError(f"unsupported native build profile: {profile_id}")
    if compatibility != "linux":
        raise RuntimeError("HIP gfx1030 native profile requires linux compatibility")
    if rocm_root is None or rocm_device_lib_path is None:
        raise RuntimeError("HIP gfx1030 native profile requires ROCm and device-lib paths")
    try:
        observed_rocm_root = rocm_root.resolve(strict=True)
        device_lib_path = rocm_device_lib_path.resolve(strict=True)
    except OSError as error:
        raise RuntimeError("HIP gfx1030 ROCm inputs must resolve") from error
    if observed_rocm_root != _ROCM_ROOT:
        raise RuntimeError("HIP gfx1030 native profile requires exact ROCm 6.0.2 root")
    _verify_frozen_files(_HIP_HOST_FILE_SPECS + _ROCM_FILE_SPECS)
    closures = (
        _require_closure(
            _ROCM_ROOT / "include",
            domain=b"betelgeuze.engine-v2.rocm-include/v1",
            expected_sha256=_ROCM_INCLUDE_SHA256,
            expected_count=_ROCM_INCLUDE_FILE_COUNT,
            label="rocm_include",
        ),
        _require_closure(
            _ROCM_ROOT / "lib/llvm/lib/clang/17.0.0/include",
            domain=b"betelgeuze.engine-v2.rocm-clang-resource-include/v1",
            expected_sha256=_ROCM_CLANG_INCLUDE_SHA256,
            expected_count=_ROCM_CLANG_INCLUDE_FILE_COUNT,
            label="rocm_clang_resource_include",
        ),
        _require_closure(
            device_lib_path,
            domain=b"betelgeuze.engine-v2.rocm-device-libs/v1",
            expected_sha256=_ROCM_DEVICE_LIB_SHA256,
            expected_count=_ROCM_DEVICE_LIB_FILE_COUNT,
            label="rocm_device_libs",
        ),
    )
    specifications = _HIP_HOST_FILE_SPECS + _ROCM_FILE_SPECS
    manifest_sha256 = _toolchain_manifest_sha256(
        profile_id=profile_id,
        compatibility=compatibility,
        cargo_features=("extension-module", "hip"),
        specifications=specifications,
        closures=closures,
    )
    tools = {specification.label: specification.path for specification in _HIP_HOST_FILE_SPECS}
    return FrozenNativeToolchain(
        profile_id=profile_id,
        compatibility=compatibility,
        cc=tools["cc"],
        cxx=tools["cxx"],
        ar=tools["ar"],
        ranlib=tools["ranlib"],
        ld=tools["linker"],
        linker=tools["cc"],
        assembler=tools["assembler"],
        strip=tools["strip"],
        path_entries=(
            _ROCM_ROOT / "bin",
            _ROCM_ROOT / "llvm/bin",
            Path("/usr/bin"),
            Path("/bin"),
        ),
        cargo_features=("extension-module", "hip"),
        toolchain_sha256=manifest_sha256,
        extra_environment=(
            ("BETELGEUZE_HIP_SAFE", "1"),
            ("BG_HIP_ARCHITECTURE", "gfx1030"),
            ("BG_HIP_DEVICE_LIB_PATH", str(device_lib_path)),
            ("BG_HIP_SAFE_ARCHITECTURES", "gfx1030"),
            ("HIP_CLANG_PATH", str(_ROCM_ROOT / "llvm/bin")),
            ("HIP_COMPILER", "clang"),
            ("HIP_PATH", str(_ROCM_ROOT)),
            ("HIP_PLATFORM", "amd"),
            ("HIP_RUNTIME", "rocclr"),
            ("HIP_USE_PERL_SCRIPTS", "1"),
            ("ROCM_DEVICE_LIB_PATH", str(device_lib_path)),
            ("ROCM_PATH", str(_ROCM_ROOT)),
        ),
    )


def _run_text(command: tuple[str, ...]) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _verify_toolchain() -> FrozenRustToolchain:
    rustc_launcher = shutil.which("rustc")
    if rustc_launcher is None:
        raise RuntimeError("native wheel requires rustc on PATH")
    # Keep the launcher basename intact: rustup dispatches based on argv[0], so
    # resolving its `rustc` symlink into the `rustup` binary changes behavior.
    launcher = str(Path(rustc_launcher).absolute())
    if _run_text((launcher, "--version")) != RUSTC_VERSION:
        raise RuntimeError("native wheel requires the frozen Rust 1.93.0 toolchain")
    verbose = _run_text((launcher, "-vV"))
    if verbose != RUSTC_VERBOSE_VERSION:
        raise RuntimeError("native wheel rustc verbose identity is not frozen")
    sysroot = Path(_run_text((launcher, "--print", "sysroot"))).resolve(strict=True)
    rustc = (sysroot / "bin" / "rustc").resolve(strict=True)
    cargo = (sysroot / "bin" / "cargo").resolve(strict=True)
    if not rustc.is_file() or not os.access(rustc, os.X_OK):
        raise RuntimeError("frozen rustc executable is missing or not executable")
    if not cargo.is_file() or not os.access(cargo, os.X_OK):
        raise RuntimeError("frozen cargo executable is missing or not executable")
    if _run_text((str(rustc), "-vV")) != RUSTC_VERBOSE_VERSION:
        raise RuntimeError("sysroot rustc does not match the frozen launcher identity")
    if not _run_text((str(cargo), "--version")).startswith("cargo 1.93.0 "):
        raise RuntimeError("native wheel requires Cargo 1.93.0")
    return FrozenRustToolchain(
        rustc_executable=rustc,
        rustc_executable_sha256=_sha256_path(rustc),
        rustc_verbose_sha256=hashlib.sha256(verbose.encode("utf-8")).hexdigest(),
        cargo_executable=cargo,
    )


def _is_direct_build_override(name: str) -> bool:
    if name in {"CARGO_TARGET_DIR", "LD_LIBRARY_PATH"}:
        return False
    return (
        name in _DIRECT_BUILD_OVERRIDE_NAMES
        or name.startswith(_DIRECT_BUILD_OVERRIDE_PREFIXES)
        or (
            name.startswith(("HOST_", "TARGET_"))
            and name.endswith(_NATIVE_TOOL_OVERRIDE_SUFFIXES)
        )
    )


def _reject_direct_build_overrides(environment: Mapping[str, str]) -> None:
    overrides = sorted(
        name
        for name, value in environment.items()
        if value.strip() and _is_direct_build_override(name)
    )
    if overrides:
        raise RuntimeError(
            "untrusted native build override(s) are not permitted: "
            + ", ".join(overrides)
        )


def _cargo_config_paths(
    repository_root: Path, environment: Mapping[str, str]
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    # Cargo searches .cargo directories from its working directory through its
    # ancestors.  The manifest-local directory is included defensively because
    # changing the invocation cwd must not silently activate a new config.
    roots = (repository_root / "rust_engine_v2", repository_root, *repository_root.parents)
    for root in roots:
        candidates.extend((root / ".cargo/config.toml", root / ".cargo/config"))
    cargo_home_text = environment.get("CARGO_HOME", "").strip()
    if cargo_home_text:
        cargo_home = Path(cargo_home_text).expanduser()
    else:
        home_text = environment.get("HOME", "").strip()
        cargo_home = (Path(home_text).expanduser() if home_text else Path.home()) / ".cargo"
    candidates.extend((cargo_home / "config.toml", cargo_home / "config"))
    return tuple(dict.fromkeys(path.resolve(strict=False) for path in candidates))


def _config_env_name_is_build_override(name: object) -> bool:
    if not isinstance(name, str):
        return False
    normalized = name.upper()
    return (
        _is_direct_build_override(normalized)
        or normalized in _SANITIZED_BUILD_ENV_NAMES
        or normalized in {"HOME", "PATH"}
    )


def _dangerous_cargo_config_keys(payload: object) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ("root",)
    dangerous: list[str] = []
    build = payload.get("build")
    if isinstance(build, dict):
        for key in (
            "incremental",
            "rustc",
            "rustc-wrapper",
            "rustc-workspace-wrapper",
            "rustflags",
            "target",
        ):
            if key in build:
                dangerous.append(f"build.{key}")
    for table_name in ("host", "target"):
        table = payload.get(table_name)
        if not isinstance(table, dict):
            continue
        for selector, values in table.items():
            if not isinstance(values, dict):
                continue
            for key in ("linker", "rustflags"):
                if key in values:
                    dangerous.append(f"{table_name}.{selector}.{key}")
    profile = payload.get("profile")
    if isinstance(profile, dict) and profile:
        dangerous.append("profile")
    for key in ("include", "paths", "patch", "replace"):
        if key in payload:
            dangerous.append(key)
    configured_env = payload.get("env")
    if isinstance(configured_env, dict):
        dangerous.extend(
            f"env.{name}"
            for name in configured_env
            if _config_env_name_is_build_override(name)
        )
    unstable = payload.get("unstable")
    if isinstance(unstable, dict):
        for key in ("build-std", "build-std-features", "host-config", "target-applies-to-host"):
            if key in unstable:
                dangerous.append(f"unstable.{key}")
    return tuple(sorted(set(dangerous)))


def _verify_cargo_configs(
    repository_root: Path, environment: Mapping[str, str]
) -> None:
    for path in _cargo_config_paths(repository_root, environment):
        if not path.exists():
            continue
        if not path.is_file() or path.stat().st_size > _MAX_CARGO_CONFIG_BYTES:
            raise RuntimeError(f"Cargo config is not a bounded regular file: {path}")
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
            raise RuntimeError(f"Cargo config cannot be verified: {path}") from error
        dangerous = _dangerous_cargo_config_keys(payload)
        if dangerous:
            raise RuntimeError(
                f"Cargo config may alter the frozen native build ({path}): "
                + ", ".join(dangerous)
            )


def _verify_manifest_profile(manifest: Path) -> None:
    try:
        payload = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise RuntimeError("native Cargo.toml cannot be verified") from error
    package = payload.get("package")
    release = payload.get("profile", {}).get("release")
    if not isinstance(package, dict) or package.get("rust-version") != "1.93":
        raise RuntimeError("native Cargo.toml must pin rust-version 1.93")
    if release != _FROZEN_RELEASE_PROFILE:
        raise RuntimeError("native Cargo.toml release profile is not frozen")


def _frozen_build_environment(
    base_environment: Mapping[str, str],
    toolchain: FrozenRustToolchain,
    native_toolchain: FrozenNativeToolchain,
) -> dict[str, str]:
    _reject_direct_build_overrides(base_environment)
    python_executable = Path(sys.executable).resolve(strict=True)
    if not python_executable.is_file() or not os.access(python_executable, os.X_OK):
        raise RuntimeError("native wheel Python executable is unavailable")
    environment = dict(base_environment)
    for name in tuple(environment):
        if _is_direct_build_override(name) or name in _SANITIZED_BUILD_ENV_NAMES:
            environment.pop(name)
    environment.update(
        {
            "CARGO": str(toolchain.cargo_executable),
            "CARGO_BUILD_RUSTC": str(toolchain.rustc_executable),
            "CARGO_BUILD_RUSTC_WRAPPER": "",
            "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER": "",
            "CARGO_BUILD_RUSTFLAGS": "",
            "CARGO_BUILD_TARGET": FROZEN_TARGET,
            "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER": str(
                native_toolchain.linker
            ),
            "CARGO_ENCODED_RUSTFLAGS": "",
            "CARGO_INCREMENTAL": "0",
            "CARGO_PROFILE_RELEASE_CODEGEN_UNITS": "1",
            "CARGO_PROFILE_RELEASE_DEBUG": "0",
            "CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS": "false",
            "CARGO_PROFILE_RELEASE_INCREMENTAL": "false",
            "CARGO_PROFILE_RELEASE_LTO": "fat",
            "CARGO_PROFILE_RELEASE_OPT_LEVEL": "3",
            "CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS": "false",
            "CARGO_PROFILE_RELEASE_PANIC": "abort",
            "CARGO_PROFILE_RELEASE_STRIP": "symbols",
            "RUSTC": str(toolchain.rustc_executable),
            "RUSTC_WRAPPER": "",
            "RUSTC_WORKSPACE_WRAPPER": "",
            "RUSTFLAGS": "",
            "CC": str(native_toolchain.cc),
            "CXX": str(native_toolchain.cxx),
            "AR": str(native_toolchain.ar),
            "RANLIB": str(native_toolchain.ranlib),
            "LD": str(native_toolchain.ld),
            "AS": str(native_toolchain.assembler),
            "STRIP": str(native_toolchain.strip),
            "PATH": os.pathsep.join(
                dict.fromkeys(
                    (
                        str(toolchain.rustc_executable.parent),
                        str(python_executable.parent),
                        *(str(path) for path in native_toolchain.path_entries),
                    )
                )
            ),
            "PYO3_PYTHON": str(python_executable),
            "BETELGEUZE_EXPECTED_RUSTC_EXECUTABLE_SHA256": (
                toolchain.rustc_executable_sha256
            ),
            "BETELGEUZE_EXPECTED_RUSTC_VERBOSE_SHA256": toolchain.rustc_verbose_sha256,
            "BETELGEUZE_EXPECTED_NATIVE_BUILD_PROFILE_ID": (
                native_toolchain.profile_id
            ),
            "BETELGEUZE_EXPECTED_NATIVE_CARGO_FEATURES": ",".join(
                native_toolchain.cargo_features
            ),
            "BETELGEUZE_EXPECTED_NATIVE_TOOLCHAIN_SHA256": (
                native_toolchain.toolchain_sha256
            ),
            "BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256": _sha256_path(
                Path(__file__).resolve(strict=True)
            ),
        }
    )
    environment.update(dict(native_toolchain.extra_environment))
    return environment


@contextmanager
def _isolated_cargo_target_directory(
    base_environment: Mapping[str, str],
) -> Iterator[Path]:
    configured = base_environment.get("CARGO_TARGET_DIR", "").strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            raise RuntimeError("CARGO_TARGET_DIR must be an absolute path")
        if path.is_symlink():
            raise RuntimeError("CARGO_TARGET_DIR must not be a symlink")
        if path.exists():
            if not path.is_dir() or any(path.iterdir()):
                raise RuntimeError("CARGO_TARGET_DIR must be an empty directory")
        else:
            try:
                path.mkdir(mode=0o700)
            except OSError as error:
                raise RuntimeError("CARGO_TARGET_DIR cannot be created safely") from error
        yield path.resolve(strict=True)
        return
    with tempfile.TemporaryDirectory(prefix="betelgeuze-native-target-") as temporary:
        yield Path(temporary).resolve(strict=True)


def _validate_compatibility(compatibility: str) -> str:
    if compatibility != "linux" and re.fullmatch(
        r"manylinux_[0-9_]+", compatibility
    ) is None:
        raise RuntimeError(f"unsupported native wheel compatibility: {compatibility}")
    return compatibility


def _verify_wheel(path: Path, *, compatibility: str | None = None) -> None:
    if _WHEEL_RE.fullmatch(path.name) is None:
        raise RuntimeError(f"unexpected native wheel name: {path.name}")
    if compatibility is not None:
        compatibility = _validate_compatibility(compatibility)
        if not path.name.endswith(f"-{compatibility}_x86_64.whl"):
            raise RuntimeError(
                "native wheel platform tag does not match the requested compatibility"
            )
    with zipfile.ZipFile(path) as archive:
        files = tuple(name for name in archive.namelist() if not name.endswith("/"))
    extensions = tuple(
        name
        for name in files
        if name.startswith("betelgeuze_engine_v2_native") and name.endswith(".so")
    )
    if len(extensions) != 1:
        raise RuntimeError("native wheel must contain exactly one extension module")
    if any(name.startswith("betelgeuze_engine_v2/") for name in files):
        raise RuntimeError("native wheel must not bundle the Python Engine v2 package")
    if not any(name.endswith(".dist-info/METADATA") for name in files):
        raise RuntimeError("native wheel metadata is missing")


def _maturin_build_command(
    *,
    manifest: Path,
    output_dir: Path,
    compatibility: str,
    native_toolchain: FrozenNativeToolchain,
) -> tuple[str, ...]:
    command = [
        sys.executable,
        "-m",
        "maturin",
        "build",
        "--manifest-path",
        str(manifest),
        "--release",
        "--target",
        FROZEN_TARGET,
        "--locked",
        "--no-default-features",
    ]
    if native_toolchain.cargo_features:
        command.extend(("--features", ",".join(native_toolchain.cargo_features)))
    command.extend(("--compatibility", compatibility, "--out", str(output_dir.resolve())))
    return tuple(command)


def build_native_wheel(
    repository_root: Path,
    output_dir: Path,
    *,
    backend_profile: str = CPU_PROFILE_ID,
    compatibility: str | None = None,
    rocm_root: Path | None = None,
    rocm_device_lib_path: Path | None = None,
    source_date_epoch: int = DEFAULT_SOURCE_DATE_EPOCH,
) -> Path:
    if compatibility is None:
        compatibility = (
            "manylinux_2_28" if backend_profile == CPU_PROFILE_ID else "linux"
        )
    compatibility = _validate_compatibility(compatibility)
    manifest = repository_root / "rust_engine_v2" / "Cargo.toml"
    lock = repository_root / "rust_engine_v2" / "Cargo.lock"
    if not manifest.is_file() or not lock.is_file():
        raise FileNotFoundError("rust_engine_v2 manifest or Cargo.lock is missing")
    caller_environment = dict(os.environ)
    _reject_direct_build_overrides(caller_environment)
    _verify_cargo_configs(repository_root, caller_environment)
    _verify_manifest_profile(manifest)
    toolchain = _verify_toolchain()
    native_toolchain = _verify_native_toolchain(
        backend_profile,
        compatibility=compatibility,
        rocm_root=rocm_root,
        rocm_device_lib_path=rocm_device_lib_path,
    )
    environment = _frozen_build_environment(
        caller_environment, toolchain, native_toolchain
    )
    with _isolated_cargo_target_directory(caller_environment) as target_directory:
        environment.update(
            {
                "SOURCE_DATE_EPOCH": str(max(source_date_epoch, 315_532_800)),
                "PYTHONHASHSEED": "0",
                "TZ": "UTC",
                "LC_ALL": "C.UTF-8",
                "LANG": "C.UTF-8",
                "CARGO_INCREMENTAL": "0",
                "CARGO_TARGET_DIR": str(target_directory),
            }
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        if tuple(output_dir.glob("*.whl")):
            raise RuntimeError("native wheel output directory must not contain prior wheels")
        subprocess.run(
            _maturin_build_command(
                manifest=manifest,
                output_dir=output_dir,
                compatibility=compatibility,
                native_toolchain=native_toolchain,
            ),
            cwd=repository_root,
            check=True,
            env=environment,
        )
    wheels = tuple(sorted(output_dir.glob("*.whl")))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one native wheel, observed {len(wheels)}")
    _verify_wheel(wheels[0], compatibility=compatibility)
    return wheels[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--backend-profile",
        choices=(CPU_PROFILE_ID, HIP_GFX1030_PROFILE_ID),
        default=CPU_PROFILE_ID,
    )
    parser.add_argument("--compatibility")
    parser.add_argument("--rocm-root")
    parser.add_argument("--rocm-device-lib-path")
    parser.add_argument("--source-date-epoch", type=int, default=DEFAULT_SOURCE_DATE_EPOCH)
    arguments = parser.parse_args()
    wheel = build_native_wheel(
        Path(arguments.repository_root).resolve(),
        Path(arguments.output_dir).resolve(),
        backend_profile=arguments.backend_profile,
        compatibility=arguments.compatibility,
        rocm_root=(Path(arguments.rocm_root) if arguments.rocm_root else None),
        rocm_device_lib_path=(
            Path(arguments.rocm_device_lib_path)
            if arguments.rocm_device_lib_path
            else None
        ),
        source_date_epoch=arguments.source_date_epoch,
    )
    print(wheel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
