#!/usr/bin/env python3
"""Build and verify the separate fail-closed Engine v2 Rust CPU wheel."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
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
        "BETELGEUZE_EXPECTED_RUSTC_EXECUTABLE_SHA256",
        "BETELGEUZE_EXPECTED_RUSTC_VERBOSE_SHA256",
        "BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256",
        "CC",
        "CFLAGS",
        "CPP",
        "CPPFLAGS",
        "CXX",
        "CXXFLAGS",
        "AR",
        "BINDGEN_EXTRA_CLANG_ARGS",
        "LD",
        "LDFLAGS",
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
    }
)
_DIRECT_BUILD_OVERRIDE_PREFIXES = (
    "CARGO_PROFILE_",
    "CARGO_TARGET_",
    "CARGO_UNSTABLE_",
    "PYO3_",
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


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    if name == "CARGO_TARGET_DIR":
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
    base_environment: Mapping[str, str], toolchain: FrozenRustToolchain
) -> dict[str, str]:
    _reject_direct_build_overrides(base_environment)
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
            "BETELGEUZE_EXPECTED_RUSTC_EXECUTABLE_SHA256": (
                toolchain.rustc_executable_sha256
            ),
            "BETELGEUZE_EXPECTED_RUSTC_VERBOSE_SHA256": toolchain.rustc_verbose_sha256,
            "BETELGEUZE_NATIVE_BUILD_WRAPPER_SHA256": _sha256_path(
                Path(__file__).resolve(strict=True)
            ),
        }
    )
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


def build_native_wheel(
    repository_root: Path,
    output_dir: Path,
    *,
    compatibility: str = "manylinux_2_28",
    source_date_epoch: int = DEFAULT_SOURCE_DATE_EPOCH,
) -> Path:
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
    environment = _frozen_build_environment(caller_environment, toolchain)
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
            (
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
                "--compatibility",
                compatibility,
                "--out",
                str(output_dir.resolve()),
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
    parser.add_argument("--compatibility", default="manylinux_2_28")
    parser.add_argument("--source-date-epoch", type=int, default=DEFAULT_SOURCE_DATE_EPOCH)
    arguments = parser.parse_args()
    wheel = build_native_wheel(
        Path(arguments.repository_root).resolve(),
        Path(arguments.output_dir).resolve(),
        compatibility=arguments.compatibility,
        source_date_epoch=arguments.source_date_epoch,
    )
    print(wheel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
