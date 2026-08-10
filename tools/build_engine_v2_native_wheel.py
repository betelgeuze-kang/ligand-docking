#!/usr/bin/env python3
"""Build and verify the separate fail-closed Engine v2 Rust CPU wheel."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile


NATIVE_VERSION = "0.2.0rc6"
RUSTC_VERSION = "rustc 1.93.0 (254b59607 2026-01-19)"
FROZEN_TARGET_TRIPLE = "x86_64-unknown-linux-gnu"
FROZEN_RELEASE_PROFILE_ENV = {
    "CARGO_PROFILE_RELEASE_CODEGEN_UNITS": "1",
    "CARGO_PROFILE_RELEASE_DEBUG": "false",
    "CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS": "false",
    "CARGO_PROFILE_RELEASE_INCREMENTAL": "false",
    "CARGO_PROFILE_RELEASE_LTO": "fat",
    "CARGO_PROFILE_RELEASE_OPT_LEVEL": "3",
    "CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS": "false",
    "CARGO_PROFILE_RELEASE_PANIC": "abort",
    "CARGO_PROFILE_RELEASE_RPATH": "false",
    "CARGO_PROFILE_RELEASE_SPLIT_DEBUGINFO": "off",
    "CARGO_PROFILE_RELEASE_STRIP": "symbols",
}
DEFAULT_SOURCE_DATE_EPOCH = 1_735_689_600
_WHEEL_RE = re.compile(
    r"^betelgeuze_engine_v2_native-0\.2\.0rc6-cp3(?:10|11|12)-cp3(?:10|11|12)-"
    r"(?:manylinux_[0-9_]+|linux)_x86_64\.whl$"
)


def _verify_toolchain() -> Path:
    discovered = shutil.which("rustc")
    if discovered is None:
        raise RuntimeError("native wheel requires rustc on PATH")
    rustc = Path(discovered).absolute()
    completed = subprocess.run(
        (str(rustc), "--version"),
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip() != RUSTC_VERSION:
        raise RuntimeError("native wheel requires the frozen Rust 1.93.0 toolchain")
    return rustc


def _sanitized_build_environment(
    inherited: dict[str, str], *, rustc: Path
) -> dict[str, str]:
    environment = dict(inherited)
    exact_toolchain_overrides = {
        "RUSTC",
        "RUSTC_WRAPPER",
        "RUSTC_WORKSPACE_WRAPPER",
        "RUSTFLAGS",
        "RUSTDOCFLAGS",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_BUILD_RUSTC",
        "CARGO_BUILD_RUSTC_WRAPPER",
        "CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER",
        "CARGO_BUILD_RUSTFLAGS",
        "CARGO_BUILD_TARGET",
    }
    for key in tuple(environment):
        target_override = key.startswith("CARGO_TARGET_") and key != "CARGO_TARGET_DIR"
        if (
            key in exact_toolchain_overrides
            or key.startswith("CARGO_PROFILE_")
            or target_override
        ):
            environment.pop(key)
    environment.update(
        {
            "RUSTC": str(rustc),
            "CARGO_BUILD_TARGET": FROZEN_TARGET_TRIPLE,
            "CARGO_INCREMENTAL": "0",
            **FROZEN_RELEASE_PROFILE_ENV,
        }
    )
    return environment


def _verify_wheel(path: Path, *, compatibility: str | None = None) -> None:
    if _WHEEL_RE.fullmatch(path.name) is None:
        raise RuntimeError(f"unexpected native wheel name: {path.name}")
    if compatibility is not None:
        if (
            compatibility != "linux"
            and re.fullmatch(r"manylinux_[0-9_]+", compatibility) is None
        ):
            raise RuntimeError(
                f"unsupported native wheel compatibility: {compatibility}"
            )
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
    manifest = repository_root / "rust_engine_v2" / "Cargo.toml"
    lock = repository_root / "rust_engine_v2" / "Cargo.lock"
    if not manifest.is_file() or not lock.is_file():
        raise FileNotFoundError("rust_engine_v2 manifest or Cargo.lock is missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    if tuple(output_dir.glob("*.whl")):
        raise RuntimeError(
            "native wheel output directory must not contain prior wheels"
        )
    rustc = _verify_toolchain()
    environment = _sanitized_build_environment(dict(os.environ), rustc=rustc)
    environment.update(
        {
            "SOURCE_DATE_EPOCH": str(max(source_date_epoch, 315_532_800)),
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
    )
    subprocess.run(
        (
            sys.executable,
            "-m",
            "maturin",
            "build",
            "--manifest-path",
            str(manifest),
            "--release",
            "--locked",
            "--target",
            FROZEN_TARGET_TRIPLE,
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
    parser.add_argument(
        "--source-date-epoch", type=int, default=DEFAULT_SOURCE_DATE_EPOCH
    )
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
