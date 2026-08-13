#!/usr/bin/env python3
"""Verify the frozen, non-consuming native fixed64 CPU profile v5."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from typing import NoReturn


SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_cpu_profile/5.0.0"
PROFILE_ID = "engine_v2_native_fixed64_cpu_synthetic_v5"
PROFILE_RELATIVE_PATH = Path("config/engine_v2_native_fixed64_cpu_profile_v5.json")
QUALIFICATION_SOURCE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/src/qualification.rs"
)
DOCKING_SOURCE_RELATIVE_PATH = Path("rust/betelgeuze-runtime/src/docking.rs")
NATIVE_PIPELINE_SOURCE_RELATIVE_PATH = Path("native/src/docking/fixed64_pipeline.cpp")
PROBE_SOURCE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v5.rs"
)
ACTIVATION_TEST_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/tests/fixed64_cpu_probe_v5_activation.rs"
)
NATIVE_VENDOR_CANONICAL_SOURCE_RELATIVE_PATHS = tuple(
    Path(value)
    for value in (
        "include/betelgeuze/engine.h",
        "native/src/internal.hpp",
        "native/src/context.cpp",
        "native/src/evaluator.cpp",
        "native/src/forcefield.cpp",
        "native/src/system.cpp",
        "native/src/cpu/evaluator.hpp",
        "native/src/cpu/evaluator.cpp",
        "native/src/rust/provider.h",
        "native/src/rust/evaluator.hpp",
        "native/src/rust/evaluator.cpp",
        "native/src/docking/fixed64_allocation.cpp",
        "native/src/docking/fixed64_so3.cpp",
        "native/src/docking/fixed64_so3_reference.hpp",
        "native/src/docking/fixed64_indexed_so3_provider.h",
        "native/src/docking/fixed64_indexed_so3.cpp",
        "native/src/docking/fixed64_pipeline.cpp",
        "native/src/docking/fixed64_producer.cpp",
        "native/src/docking/fixed64_single_anchor_provider.h",
        "native/src/docking/fixed64_single_anchor.cpp",
        "native/src/docking/fixed64_downstream.cpp",
        "native/src/docking/fixed64_refinement_pipeline.cpp",
        "native/src/docking/geometric_admission.cpp",
        "native/src/docking/pose_validity.cpp",
        "native/src/docking/rigid_refinement.cpp",
        "native/src/docking/scorer_v1.cpp",
        "native/src/docking/stable_top_k.cpp",
        "native/src/docking/torsion_v7.cpp",
        "native/src/dynamics/dynamics.hpp",
        "native/src/dynamics/api.cpp",
        "native/src/dynamics/checkpoint.cpp",
        "native/src/dynamics/common.cpp",
        "native/src/dynamics/integrator.cpp",
        "native/src/dynamics/sha256.hpp",
        "native/src/dynamics/sha256.cpp",
        "native/src/hip/provider.h",
        "native/src/hip/provider.hip",
        "native/src/hip/docking_fixed64_so3.hip",
        "native/src/hip/docking_fixed64_single_anchor.hip",
        "native/src/hip/docking_geometric_admission.hip",
        "native/src/hip/docking_scorer.hip",
        "native/src/hip/docking_pose_validity.hip",
        "native/src/hip/docking_stable_top_k.hip",
        "native/src/hip/docking_rigid_refinement.hip",
        "native/src/hip/docking_torsion_v7.hip",
        "native/src/hip/evaluator.hpp",
        "native/src/hip/evaluator.cpp",
        "native/src/hip/backend.hpp",
        "native/src/hip/backend.hip",
        "native/src/hip/planning.hpp",
        "native/src/hip/stub.cpp",
    )
)
NATIVE_VENDOR_COPY_SOURCE_RELATIVE_PATHS = tuple(
    Path("rust/betelgeuze-sys/vendor") / path
    for path in NATIVE_VENDOR_CANONICAL_SOURCE_RELATIVE_PATHS
)
RUST_COMPILED_SOURCE_TREE_ROOT_RELATIVE_PATHS = (
    Path("rust/betelgeuze-docking-search/src"),
    Path("rust/betelgeuze-docking-search/tests"),
    Path("rust/betelgeuze-runtime/src"),
    Path("rust/betelgeuze-runtime/tests"),
    Path("rust/betelgeuze-sys/src"),
    Path("rust/betelgeuze-sys/tests"),
    Path("rust/cpu-kernel/src"),
    Path("rust/reference-dynamics/src"),
    Path("rust/reference-dynamics/tests"),
    Path("rust/reference-physics/src"),
    Path("rust/reference-physics/tests"),
)
RUST_PACKAGE_ROOT_RELATIVE_PATHS = (
    Path("rust/betelgeuze-docking-search"),
    Path("rust/betelgeuze-runtime"),
    Path("rust/betelgeuze-sys"),
    Path("rust/cpu-kernel"),
    Path("rust/reference-dynamics"),
    Path("rust/reference-physics"),
)
RUST_BOUND_BUILD_SCRIPT_RELATIVE_PATHS = (Path("rust/betelgeuze-sys/build.rs"),)
RUST_BOUND_EMBEDDED_INPUT_BINDINGS = (
    (
        "rust/betelgeuze-runtime/tests/cpu_oracle_parity.rs",
        "include_str",
        "rust/betelgeuze-runtime/Cargo.toml",
    ),
    (
        "rust/betelgeuze-runtime/tests/dynamics_oracle_parity.rs",
        "include_str",
        "rust/betelgeuze-runtime/Cargo.toml",
    ),
    (
        "rust/reference-dynamics/tests/frozen_fixtures.rs",
        "include_str",
        "rust/reference-dynamics/fixtures/dynamics_v1.tsv",
    ),
    (
        "rust/reference-dynamics/tests/properties.rs",
        "include_str",
        "rust/reference-dynamics/fixtures/dynamics_v1.tsv",
    ),
    (
        "rust/reference-physics/tests/frozen_fixtures.rs",
        "include_str",
        "rust/reference-physics/fixtures/exact_energy_v1.tsv",
    ),
)
RUST_BOUND_CARGO_TARGET_SOURCE_RELATIVE_PATHS = tuple(
    Path(value)
    for value in (
        "rust/betelgeuze-docking-search/src/lib.rs",
        "rust/betelgeuze-docking-search/tests/fixed64_allocation.rs",
        "rust/betelgeuze-docking-search/tests/fixed64_geometric_admission.rs",
        "rust/betelgeuze-docking-search/tests/fixed64_placement.rs",
        "rust/betelgeuze-docking-search/tests/fixed64_producer.rs",
        "rust/betelgeuze-docking-search/tests/fixed64_scorer_v1.rs",
        "rust/betelgeuze-docking-search/tests/search_contract.rs",
        "rust/betelgeuze-docking-search/tests/short_range.rs",
        "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v5.rs",
        "rust/betelgeuze-runtime/src/lib.rs",
        "rust/betelgeuze-runtime/tests/cpu_oracle_parity.rs",
        "rust/betelgeuze-runtime/tests/docking_fixed64_pipeline.rs",
        "rust/betelgeuze-runtime/tests/dynamics_oracle_parity.rs",
        "rust/betelgeuze-runtime/tests/fixed64_cpu_probe_v5_activation.rs",
        "rust/betelgeuze-runtime/tests/runtime.rs",
        "rust/betelgeuze-sys/build.rs",
        "rust/betelgeuze-sys/src/lib.rs",
        "rust/betelgeuze-sys/tests/layout.rs",
        "rust/betelgeuze-sys/tests/raw_smoke.rs",
        "rust/cpu-kernel/src/lib.rs",
        "rust/reference-dynamics/src/lib.rs",
        "rust/reference-dynamics/tests/frozen_fixtures.rs",
        "rust/reference-dynamics/tests/properties.rs",
        "rust/reference-physics/src/lib.rs",
        "rust/reference-physics/tests/frozen_fixtures.rs",
        "rust/reference-physics/tests/properties.rs",
    )
)
RUST_BOUND_LOCAL_DEPENDENCY_BINDINGS = (
    (
        "betelgeuze-cpu-kernel",
        "betelgeuze-docking-search",
        "normal",
        "",
        "rust/betelgeuze-docking-search",
        (),
        True,
        False,
        "",
    ),
    (
        "betelgeuze-runtime",
        "betelgeuze-docking-search",
        "normal",
        "",
        "rust/betelgeuze-docking-search",
        (),
        True,
        False,
        "",
    ),
    (
        "betelgeuze-runtime",
        "betelgeuze-reference-dynamics",
        "dev",
        "",
        "rust/reference-dynamics",
        (),
        True,
        False,
        "",
    ),
    (
        "betelgeuze-runtime",
        "betelgeuze-reference-physics",
        "dev",
        "",
        "rust/reference-physics",
        (),
        True,
        False,
        "",
    ),
    (
        "betelgeuze-runtime",
        "betelgeuze-sys",
        "normal",
        "",
        "rust/betelgeuze-sys",
        (),
        True,
        False,
        "",
    ),
    (
        "betelgeuze-sys",
        "betelgeuze-cpu-kernel",
        "normal",
        "",
        "rust/cpu-kernel",
        (),
        True,
        False,
        "",
    ),
)
RUST_BOUND_CARGO_MANIFEST_TABLE_BINDINGS = (
    (
        "rust/Cargo.toml",
        ("[workspace]", "[workspace.package]"),
    ),
    (
        "rust/betelgeuze-docking-search/Cargo.toml",
        ("[package]", "[dependencies]", "[lints.rust]"),
    ),
    (
        "rust/betelgeuze-runtime/Cargo.toml",
        (
            "[package]",
            "[features]",
            "[dependencies]",
            "[dev-dependencies]",
        ),
    ),
    (
        "rust/betelgeuze-sys/Cargo.toml",
        (
            "[package]",
            "[features]",
            "[dependencies]",
            "[build-dependencies]",
        ),
    ),
    (
        "rust/cpu-kernel/Cargo.toml",
        ("[package]", "[lib]", "[dependencies]", "[lints.rust]"),
    ),
    (
        "rust/reference-dynamics/Cargo.toml",
        ("[package]", "[dependencies]", "[lints.rust]"),
    ),
    (
        "rust/reference-physics/Cargo.toml",
        ("[package]", "[dependencies]", "[lints.rust]"),
    ),
)
REPOSITORY_CARGO_CONFIG_RELATIVE_PATHS = (
    Path(".cargo/config"),
    Path(".cargo/config.toml"),
    Path("rust/.cargo/config"),
    Path("rust/.cargo/config.toml"),
)
REPOSITORY_RUST_TOOLCHAIN_OVERRIDE_RELATIVE_PATHS = (
    Path("rust-toolchain"),
    Path("rust-toolchain.toml"),
    Path("rust/rust-toolchain"),
    Path("rust/rust-toolchain.toml"),
)
NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS = (
    *NATIVE_VENDOR_CANONICAL_SOURCE_RELATIVE_PATHS,
    *NATIVE_VENDOR_COPY_SOURCE_RELATIVE_PATHS,
    Path("rust/Cargo.lock"),
    Path("rust/Cargo.toml"),
    Path("rust/betelgeuze-sys/abi/header_c11.c"),
    Path("rust/betelgeuze-sys/abi/layout_assertions.cpp"),
    Path("rust/betelgeuze-sys/Cargo.toml"),
    Path("rust/betelgeuze-sys/build.rs"),
    Path("rust/betelgeuze-sys/src/lib.rs"),
    Path("rust/betelgeuze-sys/tests/layout.rs"),
    Path("rust/betelgeuze-sys/tests/raw_smoke.rs"),
    Path("rust/betelgeuze-runtime/Cargo.toml"),
    Path("rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v5.rs"),
    Path("rust/betelgeuze-runtime/src/docking.rs"),
    Path("rust/betelgeuze-runtime/src/dynamics.rs"),
    Path("rust/betelgeuze-runtime/src/forcefield.rs"),
    Path("rust/betelgeuze-runtime/src/lib.rs"),
    Path("rust/betelgeuze-runtime/src/qualification.rs"),
    Path("rust/betelgeuze-runtime/tests/cpu_oracle_parity.rs"),
    Path("rust/betelgeuze-runtime/tests/docking_fixed64_pipeline.rs"),
    Path("rust/betelgeuze-runtime/tests/dynamics_oracle_parity.rs"),
    ACTIVATION_TEST_RELATIVE_PATH,
    Path("rust/betelgeuze-runtime/tests/runtime.rs"),
    Path("rust/cpu-kernel/Cargo.toml"),
    Path("rust/cpu-kernel/src/docking_fixed64_allocation.rs"),
    Path("rust/cpu-kernel/src/docking_fixed64_indexed_so3.rs"),
    Path("rust/cpu-kernel/src/docking_fixed64_single_anchor.rs"),
    Path("rust/cpu-kernel/src/docking_fixed64_so3.rs"),
    Path("rust/cpu-kernel/src/docking_rigid_refinement.rs"),
    Path("rust/cpu-kernel/src/docking_torsion_v7.rs"),
    Path("rust/cpu-kernel/src/kernel.rs"),
    Path("rust/cpu-kernel/src/lib.rs"),
    Path("rust/betelgeuze-docking-search/Cargo.toml"),
    Path("rust/betelgeuze-docking-search/src/anchors.rs"),
    Path("rust/betelgeuze-docking-search/src/cluster.rs"),
    Path("rust/betelgeuze-docking-search/src/error.rs"),
    Path("rust/betelgeuze-docking-search/src/fixed64.rs"),
    Path("rust/betelgeuze-docking-search/src/fixed64_cluster.rs"),
    Path("rust/betelgeuze-docking-search/src/fixed64_pipeline.rs"),
    Path("rust/betelgeuze-docking-search/src/fixed64_placement.rs"),
    Path("rust/betelgeuze-docking-search/src/fixed64_producer.rs"),
    Path("rust/betelgeuze-docking-search/src/fixed64_ranking.rs"),
    Path("rust/betelgeuze-docking-search/src/fixed64_single_anchor.rs"),
    Path("rust/betelgeuze-docking-search/src/fixed64_validity.rs"),
    Path("rust/betelgeuze-docking-search/src/geometric_admission.rs"),
    Path("rust/betelgeuze-docking-search/src/geometry.rs"),
    Path("rust/betelgeuze-docking-search/src/identity.rs"),
    Path("rust/betelgeuze-docking-search/src/lib.rs"),
    Path("rust/betelgeuze-docking-search/src/model.rs"),
    Path("rust/betelgeuze-docking-search/src/native_hash.rs"),
    Path("rust/betelgeuze-docking-search/src/prune.rs"),
    Path("rust/betelgeuze-docking-search/src/receipt.rs"),
    Path("rust/betelgeuze-docking-search/src/refine.rs"),
    Path("rust/betelgeuze-docking-search/src/rigid_refinement.rs"),
    Path("rust/betelgeuze-docking-search/src/scorer_v1.rs"),
    Path("rust/betelgeuze-docking-search/src/search.rs"),
    Path("rust/betelgeuze-docking-search/src/sha256.rs"),
    Path("rust/betelgeuze-docking-search/src/short_range.rs"),
    Path("rust/betelgeuze-docking-search/src/so3.rs"),
    Path("rust/betelgeuze-docking-search/src/surface.rs"),
    Path("rust/betelgeuze-docking-search/src/torsion_refinement.rs"),
    Path("rust/betelgeuze-docking-search/src/validity.rs"),
    Path("rust/betelgeuze-docking-search/tests/fixed64_allocation.rs"),
    Path("rust/betelgeuze-docking-search/tests/fixed64_geometric_admission.rs"),
    Path("rust/betelgeuze-docking-search/tests/fixed64_placement.rs"),
    Path("rust/betelgeuze-docking-search/tests/fixed64_producer.rs"),
    Path("rust/betelgeuze-docking-search/tests/fixed64_scorer_v1.rs"),
    Path("rust/betelgeuze-docking-search/tests/search_contract.rs"),
    Path("rust/betelgeuze-docking-search/tests/short_range.rs"),
    Path("rust/reference-dynamics/Cargo.toml"),
    Path("rust/reference-dynamics/fixtures/dynamics_v1.tsv"),
    Path("rust/reference-dynamics/src/checkpoint.rs"),
    Path("rust/reference-dynamics/src/constraints.rs"),
    Path("rust/reference-dynamics/src/dynamics.rs"),
    Path("rust/reference-dynamics/src/lib.rs"),
    Path("rust/reference-dynamics/src/model.rs"),
    Path("rust/reference-dynamics/src/rng.rs"),
    Path("rust/reference-dynamics/tests/frozen_fixtures.rs"),
    Path("rust/reference-dynamics/tests/properties.rs"),
    Path("rust/reference-physics/Cargo.toml"),
    Path("rust/reference-physics/fixtures/exact_energy_v1.tsv"),
    Path("rust/reference-physics/src/geometry.rs"),
    Path("rust/reference-physics/src/lib.rs"),
    Path("rust/reference-physics/src/model.rs"),
    Path("rust/reference-physics/src/oracle.rs"),
    Path("rust/reference-physics/tests/frozen_fixtures.rs"),
    Path("rust/reference-physics/tests/properties.rs"),
)


class NativeFixed64CPUProfileV5Error(ValueError):
    """The frozen native fixed64 CPU profile failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeFixed64CPUProfileV5Error(message)


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"non-finite JSON constant is forbidden: {value}")


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _transitive_source_manifest_sha256(sources: dict[str, bytes]) -> str:
    expected_paths = tuple(
        path.as_posix() for path in NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS
    )
    if len(expected_paths) != len(set(expected_paths)) or set(sources) != set(
        expected_paths
    ):
        _fail("native transitive source manifest path set changed")
    if any(type(raw) is not bytes for raw in sources.values()):
        _fail("native transitive source manifest contains non-byte input")
    canonical_vendor_paths = tuple(
        path.as_posix() for path in NATIVE_VENDOR_CANONICAL_SOURCE_RELATIVE_PATHS
    )
    expected_vendor_declaration = (
        "const VENDORED_FILES: &[&str] = &[\n"
        + "".join(f'    "{path}",\n' for path in canonical_vendor_paths)
        + "];"
    ).encode("ascii")
    build_source = sources["rust/betelgeuze-sys/build.rs"]
    expected_build_prefix = (
        b"use std::fs;\n"
        b"use std::path::{Path, PathBuf};\n"
        b"use std::process::Command;\n\n"
        b'const QUALIFIED_ROCM_RELEASE_PREFIX: &str = "6.0.2-";\n\n'
        + expected_vendor_declaration
        + b"\n\nfn track(path: &Path) {"
    )
    if (
        not build_source.startswith(expected_build_prefix)
        or build_source.count(b"VENDORED_FILES") != 3
        or build_source.count(b"for relative in VENDORED_FILES {") != 2
    ):
        _fail("native vendor equality manifest changed")
    for canonical_path in canonical_vendor_paths:
        vendor_path = (Path("rust/betelgeuze-sys/vendor") / canonical_path).as_posix()
        if sources[canonical_path] != sources[vendor_path]:
            _fail(f"native vendor source differs from canonical: {canonical_path}")
    identities = {
        path: hashlib.sha256(sources[path]).hexdigest() for path in expected_paths
    }
    return hashlib.sha256(
        json.dumps(
            identities,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def require_native_vendor_tree_paths(observed_paths: tuple[str, ...]) -> None:
    expected_paths = tuple(
        path.as_posix() for path in NATIVE_VENDOR_COPY_SOURCE_RELATIVE_PATHS
    )
    if len(observed_paths) != len(set(observed_paths)) or tuple(
        sorted(observed_paths)
    ) != tuple(sorted(expected_paths)):
        _fail("native vendor tree contains an unbound or missing source")


def _require_directory_chain(root: Path, relative: Path, label: str) -> Path:
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink() or not current.is_dir():
            _fail(f"{label} is missing, invalid, or symlinked")
    return current


def _stable_file_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def read_bound_source_bytes(root: Path, relative: Path) -> bytes:
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        _fail("bound compiler source path is not a canonical repository-relative path")
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        _fail("platform lacks required no-follow compiler-source primitives")
    directory_flags = (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW
    descriptors: list[int] = []
    try:
        descriptors.append(os.open(root, directory_flags))
        for part in relative.parent.parts:
            descriptors.append(os.open(part, directory_flags, dir_fd=descriptors[-1]))
        descriptor = os.open(relative.name, file_flags, dir_fd=descriptors[-1])
        descriptors.append(descriptor)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            _fail("bound compiler source is invalid or symlinked")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        leaf = os.stat(
            relative.name,
            dir_fd=descriptors[-2],
            follow_symlinks=False,
        )
    except OSError as exc:
        raise NativeFixed64CPUProfileV5Error(
            "bound compiler source or parent is missing, unreadable, invalid, or symlinked"
        ) from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    if (
        _stable_file_identity(before) != _stable_file_identity(after)
        or _stable_file_identity(after) != _stable_file_identity(leaf)
        or stat.S_ISLNK(leaf.st_mode)
        or not stat.S_ISREG(leaf.st_mode)
    ):
        _fail("bound compiler source changed while it was read")
    return b"".join(chunks)


def read_bound_transitive_sources(root: Path) -> dict[str, bytes]:
    return {
        path.as_posix(): read_bound_source_bytes(root, path)
        for path in NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS
    }


def discover_native_vendor_tree_paths(root: Path) -> tuple[str, ...]:
    vendor_base = Path("rust/betelgeuze-sys/vendor")
    _require_directory_chain(root, vendor_base, "native vendor root")
    vendor_roots = tuple(
        _require_directory_chain(
            root,
            vendor_base / child,
            "native vendor root",
        )
        for child in ("include", "native")
    )
    vendor_entries = tuple(
        sorted(
            path
            for vendor_root in vendor_roots
            for path in vendor_root.rglob("*")
            if path.is_file() or path.is_symlink()
        )
    )
    if any(path.is_symlink() for path in vendor_entries):
        _fail("native vendor tree contains a symlink")
    observed_paths = tuple(path.relative_to(root).as_posix() for path in vendor_entries)
    require_native_vendor_tree_paths(observed_paths)
    return observed_paths


def require_rust_compiled_source_tree_paths(observed_paths: tuple[str, ...]) -> None:
    roots = tuple(
        f"{path.as_posix()}/" for path in RUST_COMPILED_SOURCE_TREE_ROOT_RELATIVE_PATHS
    )
    expected_paths = tuple(
        path.as_posix()
        for path in NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS
        if path.suffix == ".rs" and path.as_posix().startswith(roots)
    )
    if len(observed_paths) != len(set(observed_paths)) or tuple(
        sorted(observed_paths)
    ) != tuple(sorted(expected_paths)):
        _fail("Rust compiled source tree contains an unbound or missing source")


def discover_rust_compiled_source_tree_paths(root: Path) -> tuple[str, ...]:
    source_roots = tuple(
        _require_directory_chain(root, relative, "Rust compiled source root")
        for relative in RUST_COMPILED_SOURCE_TREE_ROOT_RELATIVE_PATHS
    )
    tree_entries = tuple(
        sorted(path for source_root in source_roots for path in source_root.rglob("*"))
    )
    if any(path.is_symlink() for path in tree_entries):
        _fail("Rust compiled source tree contains a symlink")
    source_entries = tuple(path for path in tree_entries if path.suffix == ".rs")
    if any(not path.is_file() for path in source_entries):
        _fail("Rust compiled source tree contains an invalid Rust source")
    observed_paths = tuple(path.relative_to(root).as_posix() for path in source_entries)
    require_rust_compiled_source_tree_paths(observed_paths)
    discover_rust_embedded_input_bindings(
        root,
        observed_paths
        + tuple(path.as_posix() for path in RUST_BOUND_BUILD_SCRIPT_RELATIVE_PATHS),
    )
    return observed_paths


_RUST_RAW_STRING_START = re.compile(r'(?:br|cr|r)(?P<hashes>#{0,255})"')
_RUST_INCLUDE_MACRO_START = re.compile(
    r"\b(?P<macro>include(?:_str|_bytes)?)\s*!\s*\("
)
_RUST_STATIC_INCLUDE_MACRO = re.compile(
    r'\b(?P<macro>include(?:_str|_bytes)?)\s*!\s*\(\s*'
    r'"(?P<path>[A-Za-z0-9_./-]+)"\s*\)'
)
_RUST_PATH_ATTRIBUTE = re.compile(r"#\s*\[[^\]]*\bpath\s*=", re.DOTALL)


def _rust_character_literal_end(source: str, start: int) -> int | None:
    if start >= len(source) or source[start] != "'":
        return None
    content = start + 1
    if content >= len(source) or source[content] in {"'", "\n", "\r", "\t"}:
        return None
    if source[content] != "\\":
        closing = content + 1
    else:
        escape = content + 1
        if escape >= len(source):
            return None
        if source[escape] in {"n", "r", "t", "\\", "0", "'", '"'}:
            closing = escape + 1
        elif source[escape] == "x":
            digits = source[escape + 1 : escape + 3]
            if re.fullmatch(r"[0-9A-Fa-f]{2}", digits) is None:
                return None
            closing = escape + 3
        elif source.startswith("u{", escape):
            brace = source.find("}", escape + 2)
            if brace < 0:
                return None
            digits = source[escape + 2 : brace].replace("_", "")
            if not 1 <= len(digits) <= 6 or re.fullmatch(
                r"[0-9A-Fa-f]+", digits
            ) is None:
                return None
            closing = brace + 1
        else:
            return None
    if closing >= len(source) or source[closing] != "'":
        return None
    return closing + 1


def _rust_source_lexical_views(source: str) -> tuple[str, str]:
    normalized = list(source)
    code_only = list(source)

    def blank(target: list[str], start: int, end: int) -> None:
        for index in range(start, end):
            if target[index] not in {"\n", "\r"}:
                target[index] = " "

    index = 0
    while index < len(source):
        raw = _RUST_RAW_STRING_START.match(source, index)
        if raw is not None:
            start = index
            terminator = '"' + raw.group("hashes")
            end = source.find(terminator, raw.end())
            if end < 0:
                _fail("Rust compiler source contains an unterminated raw string")
            index = end + len(terminator)
            blank(code_only, start, index)
            continue
        if source[index] == "'":
            end = _rust_character_literal_end(source, index)
            if end is not None:
                blank(code_only, index, end)
                index = end
                continue
        if source[index] == '"':
            start = index
            index += 1
            while index < len(source):
                if source[index] == "\\":
                    index += 2
                    continue
                if source[index] == '"':
                    index += 1
                    break
                index += 1
            else:
                _fail("Rust compiler source contains an unterminated string")
            blank(code_only, start, index)
            continue
        if source.startswith("//", index):
            end = source.find("\n", index + 2)
            if end < 0:
                end = len(source)
            blank(normalized, index, end)
            blank(code_only, index, end)
            index = end
            continue
        if source.startswith("/*", index):
            start = index
            depth = 1
            index += 2
            while index < len(source) and depth:
                if source.startswith("/*", index):
                    depth += 1
                    index += 2
                elif source.startswith("*/", index):
                    depth -= 1
                    index += 2
                else:
                    index += 1
            if depth:
                _fail("Rust compiler source contains an unterminated block comment")
            blank(normalized, start, index)
            blank(code_only, start, index)
            continue
        index += 1
    return "".join(normalized), "".join(code_only)


def require_rust_embedded_input_bindings(
    observed_bindings: tuple[tuple[str, str, str], ...],
) -> None:
    expected = tuple(sorted(RUST_BOUND_EMBEDDED_INPUT_BINDINGS))
    if (
        len(observed_bindings) != len(set(observed_bindings))
        or tuple(sorted(observed_bindings)) != expected
    ):
        _fail("Rust embedded compiler input binding set changed")
    transitive_paths = {
        path.as_posix() for path in NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS
    }
    if any(binding[2] not in transitive_paths for binding in observed_bindings):
        _fail("Rust embedded compiler input is absent from the transitive manifest")


def discover_rust_embedded_input_bindings(
    root: Path,
    source_paths: tuple[str, ...],
) -> tuple[tuple[str, str, str], ...]:
    observed: list[tuple[str, str, str]] = []
    for source_text in source_paths:
        source_relative = Path(source_text)
        try:
            source = read_bound_source_bytes(root, source_relative).decode("utf-8")
        except UnicodeError as exc:
            raise NativeFixed64CPUProfileV5Error(
                "Rust compiler source is not valid UTF-8"
            ) from exc
        normalized, code_only = _rust_source_lexical_views(source)
        if _RUST_PATH_ATTRIBUTE.search(code_only) is not None:
            _fail("Rust path attribute source expansion is forbidden")
        starts = tuple(_RUST_INCLUDE_MACRO_START.finditer(code_only))
        start_keys = {
            (match.start(), match.group("macro")) for match in starts
        }
        static_includes = tuple(
            match
            for match in _RUST_STATIC_INCLUDE_MACRO.finditer(normalized)
            if (match.start(), match.group("macro")) in start_keys
        )
        if tuple((match.start(), match.group("macro")) for match in starts) != tuple(
            (match.start(), match.group("macro")) for match in static_includes
        ):
            _fail("Rust include macro must use one bound static path literal")
        for match in static_includes:
            macro = match.group("macro")
            if macro == "include":
                _fail("Rust include! source expansion is forbidden")
            literal = Path(match.group("path"))
            if literal.is_absolute():
                _fail("Rust embedded compiler input path is absolute")
            normalized = Path(
                os.path.normpath((source_relative.parent / literal).as_posix())
            )
            if (
                normalized.is_absolute()
                or not normalized.parts
                or normalized.parts[0] == ".."
            ):
                _fail("Rust embedded compiler input escapes the repository")
            read_bound_source_bytes(root, normalized)
            observed.append((source_text, macro, normalized.as_posix()))
    observed_bindings = tuple(observed)
    require_rust_embedded_input_bindings(observed_bindings)
    return observed_bindings


def require_rust_package_build_script_paths(
    observed_paths: tuple[str, ...],
) -> None:
    expected_paths = tuple(
        path.as_posix() for path in RUST_BOUND_BUILD_SCRIPT_RELATIVE_PATHS
    )
    if len(observed_paths) != len(set(observed_paths)) or tuple(
        sorted(observed_paths)
    ) != tuple(sorted(expected_paths)):
        _fail("Rust package build-script set contains an unbound or missing input")


def discover_rust_package_build_script_paths(root: Path) -> tuple[str, ...]:
    package_roots = tuple(
        _require_directory_chain(root, relative, "Rust package root")
        for relative in RUST_PACKAGE_ROOT_RELATIVE_PATHS
    )
    observed: list[str] = []
    for package_root in package_roots:
        candidate = package_root / "build.rs"
        if candidate.is_symlink():
            _fail("Rust package build script is symlinked")
        if candidate.exists():
            if not candidate.is_file():
                _fail("Rust package build script is invalid")
            observed.append(candidate.relative_to(root).as_posix())
    observed_paths = tuple(observed)
    require_rust_package_build_script_paths(observed_paths)
    return observed_paths


def require_rust_cargo_target_source_paths(
    observed_paths: tuple[str, ...],
) -> None:
    expected_paths = tuple(
        sorted(
            path.as_posix() for path in RUST_BOUND_CARGO_TARGET_SOURCE_RELATIVE_PATHS
        )
    )
    if (
        len(observed_paths) != len(set(observed_paths))
        or tuple(sorted(observed_paths)) != expected_paths
    ):
        _fail("Cargo target source set contains an unbound or missing input")
    bound_sources = {
        path.as_posix() for path in NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS
    }
    if any(path not in bound_sources for path in observed_paths):
        _fail("Cargo target source is absent from the transitive manifest")


def require_rust_local_dependency_bindings(
    observed_bindings: tuple[
        tuple[
            str,
            str,
            str,
            str,
            str,
            tuple[str, ...],
            bool,
            bool,
            str,
        ],
        ...,
    ],
) -> None:
    expected_bindings = tuple(sorted(RUST_BOUND_LOCAL_DEPENDENCY_BINDINGS))
    if (
        len(observed_bindings) != len(set(observed_bindings))
        or tuple(sorted(observed_bindings)) != expected_bindings
    ):
        _fail("Cargo local dependency graph contains an unbound or missing input")
    expected_roots = {path.as_posix() for path in RUST_PACKAGE_ROOT_RELATIVE_PATHS}
    if any(binding[4] not in expected_roots for binding in observed_bindings):
        _fail("Cargo local dependency escapes the bound package roots")


def require_rust_cargo_manifest_table_bindings(
    root: Path,
    expected_manifest_paths: tuple[Path, ...],
) -> None:
    bound_manifest_paths = tuple(
        Path(relative_text)
        for relative_text, _ in RUST_BOUND_CARGO_MANIFEST_TABLE_BINDINGS
    )
    if len(bound_manifest_paths) != len(set(bound_manifest_paths)) or tuple(
        sorted(bound_manifest_paths)
    ) != tuple(sorted(expected_manifest_paths)):
        _fail("Cargo manifest table binding set is incomplete or duplicated")
    for relative_text, expected_tables in RUST_BOUND_CARGO_MANIFEST_TABLE_BINDINGS:
        relative = Path(relative_text)
        try:
            source = read_bound_source_bytes(root, relative).decode("utf-8")
        except UnicodeError as exc:
            raise NativeFixed64CPUProfileV5Error(
                "Cargo manifest is not valid UTF-8"
            ) from exc
        observed_tables: list[str] = []
        first_table_seen = False
        for line in source.splitlines():
            candidate = line.strip()
            if not candidate or candidate.startswith("#"):
                continue
            if not candidate.startswith("["):
                if not first_table_seen:
                    _fail("Cargo manifest contains an unbound root assignment")
                continue
            if re.fullmatch(r"\[[A-Za-z0-9_.-]+\]", candidate) is None:
                _fail("Cargo manifest contains an invalid or unbound table")
            first_table_seen = True
            observed_tables.append(candidate)
        if tuple(observed_tables) != expected_tables:
            _fail("Cargo manifest table set contains an unbound or missing input")


def discover_rust_cargo_target_source_paths(root: Path) -> tuple[str, ...]:
    rust_root = _require_directory_chain(root, Path("rust"), "Cargo workspace root")
    manifest_paths = (
        Path("rust/Cargo.toml"),
        *(path / "Cargo.toml" for path in RUST_PACKAGE_ROOT_RELATIVE_PATHS),
    )
    for relative in (*manifest_paths, Path("rust/Cargo.lock")):
        read_bound_source_bytes(root, relative)
    require_rust_cargo_manifest_table_bindings(root, manifest_paths)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CARGO_")
        and key
        not in {
            "RUSTC",
            "RUSTDOC",
            "RUSTFLAGS",
            "RUSTDOCFLAGS",
            "RUSTUP_TOOLCHAIN",
        }
    }
    try:
        with tempfile.TemporaryDirectory(
            prefix="betelgeuze-cargo-metadata-"
        ) as metadata_sandbox:
            cargo_home = Path(metadata_sandbox) / "cargo-home"
            cargo_home.mkdir(mode=0o700)
            environment["CARGO_HOME"] = str(cargo_home)
            environment["CARGO_NET_OFFLINE"] = "true"
            process = subprocess.run(
                (
                    "cargo",
                    "metadata",
                    "--manifest-path",
                    str(rust_root / "Cargo.toml"),
                    "--format-version=1",
                    "--no-deps",
                    "--locked",
                    "--offline",
                ),
                cwd=metadata_sandbox,
                env=environment,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeFixed64CPUProfileV5Error(
            "Cargo target metadata could not be derived fail-closed"
        ) from exc
    if process.returncode != 0:
        _fail("Cargo target metadata derivation failed")
    try:
        metadata = json.loads(
            process.stdout.decode("utf-8"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFixed64CPUProfileV5Error(
            "Cargo target metadata is not canonical JSON"
        ) from exc
    if type(metadata) is not dict or type(metadata.get("packages")) is not list:
        _fail("Cargo target metadata schema is invalid")
    if metadata.get("workspace_root") != str(rust_root):
        _fail("Cargo target metadata workspace root is cross-wired")
    expected_manifests = {str(root / relative) for relative in manifest_paths[1:]}
    observed_manifests: set[str] = set()
    observed_paths: list[str] = []
    local_dependency_bindings: list[
        tuple[
            str,
            str,
            str,
            str,
            str,
            tuple[str, ...],
            bool,
            bool,
            str,
        ]
    ] = []
    probe_bindings: list[tuple[str, tuple[str, ...], str]] = []
    activation_bindings: list[tuple[str, tuple[str, ...], str]] = []
    for package in metadata["packages"]:
        if (
            type(package) is not dict
            or type(package.get("targets")) is not list
            or type(package.get("dependencies")) is not list
        ):
            _fail("Cargo package target metadata schema is invalid")
        package_name = package.get("name")
        manifest_path = package.get("manifest_path")
        if type(package_name) is not str or type(manifest_path) is not str:
            _fail("Cargo package identity metadata is invalid")
        observed_manifests.add(manifest_path)
        for dependency in package["dependencies"]:
            if type(dependency) is not dict:
                _fail("Cargo dependency metadata row is invalid")
            dependency_name = dependency.get("name")
            dependency_path = dependency.get("path")
            dependency_source = dependency.get("source")
            dependency_kind = dependency.get("kind")
            dependency_rename = dependency.get("rename")
            dependency_features = dependency.get("features")
            dependency_uses_default_features = dependency.get("uses_default_features")
            dependency_optional = dependency.get("optional")
            dependency_target = dependency.get("target")
            dependency_registry = dependency.get("registry")
            if (
                type(dependency_name) is not str
                or (dependency_path is not None and type(dependency_path) is not str)
                or (
                    dependency_source is not None and type(dependency_source) is not str
                )
                or (dependency_kind is not None and type(dependency_kind) is not str)
                or (
                    dependency_rename is not None and type(dependency_rename) is not str
                )
                or type(dependency_features) is not list
                or any(type(feature) is not str for feature in dependency_features)
                or type(dependency_uses_default_features) is not bool
                or type(dependency_optional) is not bool
                or (
                    dependency_target is not None and type(dependency_target) is not str
                )
                or (
                    dependency_registry is not None
                    and type(dependency_registry) is not str
                )
            ):
                _fail("Cargo dependency identity metadata is invalid")
            if dependency_path is None:
                if dependency_source is None:
                    _fail("Cargo dependency has neither a bound path nor a source")
                continue
            if dependency_source is not None:
                _fail("Cargo local dependency has an unexpected source identity")
            if dependency_registry is not None:
                _fail("Cargo local dependency has an unexpected registry identity")
            local_root = Path(dependency_path)
            if not local_root.is_absolute():
                _fail("Cargo local dependency path is not absolute")
            try:
                local_relative = local_root.relative_to(root)
            except ValueError:
                _fail("Cargo local dependency escapes the repository")
            _require_directory_chain(
                root,
                local_relative,
                "Cargo local dependency root",
            )
            local_dependency_bindings.append(
                (
                    package_name,
                    dependency_name,
                    dependency_kind or "normal",
                    dependency_rename or "",
                    local_relative.as_posix(),
                    tuple(dependency_features),
                    dependency_uses_default_features,
                    dependency_optional,
                    dependency_target or "",
                )
            )
        for target in package["targets"]:
            if type(target) is not dict:
                _fail("Cargo target metadata row is invalid")
            target_name = target.get("name")
            kinds = target.get("kind")
            source_path = target.get("src_path")
            if (
                type(target_name) is not str
                or type(kinds) is not list
                or any(type(kind) is not str for kind in kinds)
                or type(source_path) is not str
            ):
                _fail("Cargo target identity metadata is invalid")
            source = Path(source_path)
            if not source.is_absolute():
                _fail("Cargo target source path is not absolute")
            try:
                relative = source.relative_to(root)
            except ValueError:
                _fail("Cargo target source escapes the repository")
            relative_path = relative.as_posix()
            read_bound_source_bytes(root, relative)
            observed_paths.append(relative_path)
            binding = (package_name, tuple(kinds), relative_path)
            if target_name == "betelgeuze-fixed64-cpu-probe-v5":
                probe_bindings.append(binding)
            if target_name == "fixed64_cpu_probe_v5_activation":
                activation_bindings.append(binding)
    if observed_manifests != expected_manifests:
        _fail("Cargo workspace package manifest set is cross-wired")
    require_rust_local_dependency_bindings(tuple(local_dependency_bindings))
    expected_probe = (
        "betelgeuze-runtime",
        ("bin",),
        PROBE_SOURCE_RELATIVE_PATH.as_posix(),
    )
    if probe_bindings != [expected_probe]:
        _fail("qualification probe Cargo target binding changed")
    expected_activation = (
        "betelgeuze-runtime",
        ("test",),
        ACTIVATION_TEST_RELATIVE_PATH.as_posix(),
    )
    if activation_bindings != [expected_activation]:
        _fail("release activation-test Cargo target binding changed")
    observed = tuple(sorted(observed_paths))
    require_rust_cargo_target_source_paths(observed)
    return observed


def _require_repository_paths_absent(
    root: Path,
    relative_paths: tuple[Path, ...],
    label: str,
) -> None:
    for relative in relative_paths:
        current = root
        for index, part in enumerate(relative.parts):
            current /= part
            try:
                entry = current.lstat()
            except FileNotFoundError:
                break
            except OSError as exc:
                raise NativeFixed64CPUProfileV5Error(
                    f"{label} path is unreadable"
                ) from exc
            if stat.S_ISLNK(entry.st_mode):
                _fail(f"{label} path is symlinked")
            if index + 1 < len(relative.parts):
                if not stat.S_ISDIR(entry.st_mode):
                    _fail(f"{label} parent is invalid")
            else:
                _fail(f"{label} is forbidden by the profile")


def require_repository_cargo_configuration_absent(root: Path) -> None:
    _require_repository_paths_absent(
        root,
        REPOSITORY_CARGO_CONFIG_RELATIVE_PATHS,
        "repository Cargo configuration",
    )


def require_repository_rust_toolchain_override_absent(root: Path) -> None:
    _require_repository_paths_absent(
        root,
        REPOSITORY_RUST_TOOLCHAIN_OVERRIDE_RELATIVE_PATHS,
        "repository Rust toolchain override",
    )


def _exact_keys(value: object, expected: set[str], name: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        _fail(f"{name} key schema changed")
    return value


def require_profile_document(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFixed64CPUProfileV5Error(
            "profile is not canonical ASCII JSON"
        ) from exc
    profile = _exact_keys(
        value,
        {
            "authority",
            "backends",
            "fixtures",
            "gates",
            "measurement_core",
            "numeric_parity",
            "performance",
            "profile_id",
            "restrictions",
            "sampling",
            "schema_id",
            "status",
        },
        "profile",
    )
    if raw != _canonical_bytes(profile):
        _fail("profile serialization is not canonical sorted indented JSON")
    if profile["schema_id"] != SCHEMA_ID or profile["profile_id"] != PROFILE_ID:
        _fail("profile identity changed")
    if profile["status"] != "implementation_profile_frozen_execution_not_consumed":
        _fail("profile execution status changed")

    authority = _exact_keys(
        profile["authority"],
        {
            "fresh_holdout_execution_authorized",
            "historical_ab_execution_authorized",
            "molecular_execution_authorized",
            "product_performance_claim_authorized",
            "public_benchmark_authorized",
            "qualification_authority",
            "reservation_authorized",
            "scientific_claim_authorized",
            "stage0_admission_authorized",
        },
        "authority",
    )
    if any(value is not False for value in authority.values()):
        _fail("all profile authority must remain false")

    backends = _exact_keys(
        profile["backends"],
        {"comparison", "fallback_allowed", "reference"},
        "backends",
    )
    if backends != {
        "comparison": "rust_cpu",
        "fallback_allowed": False,
        "reference": "cpp_cpu_reference",
    }:
        _fail("CPU backend comparison changed")

    fixtures = profile["fixtures"]
    expected_fixtures = [
        {
            "candidate_denominator": 64,
            "contains_molecular_data": False,
            "expected_generated_count": 64,
            "expected_typed_failure_count": 0,
            "fixture_id": "synthetic_complete_64",
            "fixture_payload_sha256": (
                "5e17b3a292a068115f223c5c433d5ec40557be50a05cc1dbaa07461d9aed7fb8"
            ),
            "fixture_source": "native_compiled_constant",
            "ligand_atom_count": 12,
            "receptor_atom_count": 12,
        },
        {
            "candidate_denominator": 64,
            "contains_molecular_data": False,
            "expected_generated_count": 48,
            "expected_typed_failure_count": 16,
            "fixture_id": "synthetic_feature_sparse_48_plus_16",
            "fixture_payload_sha256": (
                "fca0d6dbdc0f188e332929b9ea220f1d3ecaa37e9939c49aa80bf0629c14f1fb"
            ),
            "fixture_source": "native_compiled_constant",
            "ligand_atom_count": 12,
            "receptor_atom_count": 12,
        },
    ]
    if fixtures != expected_fixtures:
        _fail("synthetic fixture contract changed")

    gates = _exact_keys(
        profile["gates"],
        {
            "authority_false_required",
            "candidate_denominator_exact",
            "cpp_repeat_projection_exact_required",
            "decision_sha256_exact_between_cpu_backends_required",
            "failure_codes_exact_required",
            "post_refinement_admission_decisions_exact_required",
            "post_refinement_admission_failure_codes_exact_required",
            "post_refinement_rejected_rows_cannot_rank_required",
            "persistent_context_count_per_backend_exact",
            "rust_repeat_projection_exact_required",
            "score_term_count_exact",
            "scorer_v1_terms_rederivable_required",
            "top1_top5_and_v7_decisions_exact_required",
            "validity_decisions_exact_required",
            "validity_measurements_rederivable_required",
        },
        "gates",
    )
    if gates != {
        "authority_false_required": True,
        "candidate_denominator_exact": 64,
        "cpp_repeat_projection_exact_required": True,
        "decision_sha256_exact_between_cpu_backends_required": True,
        "failure_codes_exact_required": True,
        "post_refinement_admission_decisions_exact_required": True,
        "post_refinement_admission_failure_codes_exact_required": True,
        "post_refinement_rejected_rows_cannot_rank_required": True,
        "persistent_context_count_per_backend_exact": 1,
        "rust_repeat_projection_exact_required": True,
        "score_term_count_exact": 8,
        "scorer_v1_terms_rederivable_required": True,
        "top1_top5_and_v7_decisions_exact_required": True,
        "validity_decisions_exact_required": True,
        "validity_measurements_rederivable_required": True,
    }:
        _fail("scientific parity gates changed")

    core = _exact_keys(
        profile["measurement_core"],
        {
            "candidate_graph",
            "complete_rederivable_evidence_required",
            "native_abi_version",
            "native_binary",
            "native_cpp_pipeline_source_sha256",
            "native_pipeline_profile_id",
            "native_probe_source_sha256",
            "native_qualification_source_sha256",
            "native_rust_pipeline_source_sha256",
            "native_transitive_source_count",
            "native_transitive_source_manifest_sha256",
            "post_refinement_admission_before_scorer_required",
            "post_refinement_rejected_rows_typed_inactive_before_scorer_required",
            "python_scientific_work_allowed",
            "receptor_context_recreated_inside_samples",
        },
        "measurement core",
    )
    qualification_source_sha256 = core["native_qualification_source_sha256"]
    probe_source_sha256 = core["native_probe_source_sha256"]
    rust_pipeline_source_sha256 = core["native_rust_pipeline_source_sha256"]
    cpp_pipeline_source_sha256 = core["native_cpp_pipeline_source_sha256"]
    transitive_source_count = core["native_transitive_source_count"]
    transitive_source_manifest_sha256 = core["native_transitive_source_manifest_sha256"]
    if (
        type(qualification_source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", qualification_source_sha256) is None
        or type(probe_source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", probe_source_sha256) is None
        or type(rust_pipeline_source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", rust_pipeline_source_sha256) is None
        or type(cpp_pipeline_source_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", cpp_pipeline_source_sha256) is None
        or type(transitive_source_count) is not int
        or transitive_source_count
        != len(NATIVE_PIPELINE_TRANSITIVE_SOURCE_RELATIVE_PATHS)
        or type(transitive_source_manifest_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", transitive_source_manifest_sha256) is None
    ):
        _fail("native measured source identity is not canonical SHA-256")
    if core != {
        "candidate_graph": [
            "fixed64_proposal",
            "initial_geometric_admission",
            "rigid_refinement",
            "torsion_v7_refinement",
            "post_refinement_geometric_admission",
            "scorer_v1_8_term",
            "pose_validity",
            "stable_top_k",
            "direct_rmsd_clustering",
        ],
        "complete_rederivable_evidence_required": True,
        "native_abi_version": "1.21",
        "native_binary": "betelgeuze-fixed64-cpu-probe-v5",
        "native_cpp_pipeline_source_sha256": cpp_pipeline_source_sha256,
        "native_pipeline_profile_id": (
            "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0"
        ),
        "native_probe_source_sha256": probe_source_sha256,
        "native_qualification_source_sha256": qualification_source_sha256,
        "native_rust_pipeline_source_sha256": rust_pipeline_source_sha256,
        "native_transitive_source_count": transitive_source_count,
        "native_transitive_source_manifest_sha256": (transitive_source_manifest_sha256),
        "post_refinement_admission_before_scorer_required": True,
        "post_refinement_rejected_rows_typed_inactive_before_scorer_required": True,
        "python_scientific_work_allowed": False,
        "receptor_context_recreated_inside_samples": False,
    }:
        _fail("native measurement core changed")

    numeric = _exact_keys(
        profile["numeric_parity"],
        {
            "absolute_tolerance",
            "all_coordinate_states_compared",
            "all_post_refinement_admission_measurements_compared",
            "all_refinement_objectives_compared",
            "all_scorer_v1_terms_compared",
            "all_validity_measurements_compared",
            "compared_f64_count_exact",
            "nonfinite_values_allowed",
            "relative_tolerance",
        },
        "numeric parity",
    )
    if numeric != {
        "absolute_tolerance": 1e-11,
        "all_coordinate_states_compared": True,
        "all_post_refinement_admission_measurements_compared": True,
        "all_refinement_objectives_compared": True,
        "all_scorer_v1_terms_compared": True,
        "all_validity_measurements_compared": True,
        "compared_f64_count_exact": 28_544,
        "nonfinite_values_allowed": False,
        "relative_tolerance": 4e-12,
    }:
        _fail("numeric parity contract changed")

    performance = _exact_keys(
        profile["performance"],
        {"gate", "maximum_ratio", "performance_claim_authorized", "scope"},
        "performance",
    )
    if performance != {
        "gate": "rust_cpu_median_div_cpp_cpu_reference_median_lte",
        "maximum_ratio": 1.25,
        "performance_claim_authorized": False,
        "scope": "synthetic_development_non_regression_only",
    }:
        _fail("performance gate changed")

    restrictions = _exact_keys(
        profile["restrictions"],
        {
            "actual_molecular_execution_allowed",
            "contains_molecular_cases",
            "fresh_or_historical_case_input_allowed",
            "github_actions_live_qualification_allowed",
            "github_actions_production_authority_allowed",
            "hip_device_execution_allowed",
            "public_or_scientific_performance_claim_allowed",
            "reservation_allowed",
            "result_dependent_configuration_allowed",
            "test_double_production_authority_allowed",
        },
        "restrictions",
    )
    if any(value is not False for value in restrictions.values()):
        _fail("all restricted capabilities must remain false")

    sampling = _exact_keys(
        profile["sampling"],
        {"clock", "sample_rounds", "schedule", "timed_scope", "warmup_rounds"},
        "sampling",
    )
    if sampling != {
        "clock": "std_steady_instant",
        "sample_rounds": 25,
        "schedule": "paired_ab_ba",
        "timed_scope": "persistent_pipeline_run_only",
        "warmup_rounds": 5,
    }:
        _fail("sampling contract changed")
    return profile


def require_compiled_profile_binding(
    profile: dict[str, object],
    qualification_source_raw: bytes,
    docking_source_raw: bytes,
    native_pipeline_source_raw: bytes,
    probe_source_raw: bytes,
    transitive_sources_raw: dict[str, bytes],
    native_vendor_tree_paths: tuple[str, ...],
    rust_compiled_source_tree_paths: tuple[str, ...],
    rust_package_build_script_paths: tuple[str, ...],
    rust_cargo_target_source_paths: tuple[str, ...] = tuple(
        path.as_posix() for path in RUST_BOUND_CARGO_TARGET_SOURCE_RELATIVE_PATHS
    ),
) -> None:
    """Bind the native gate constants and entry point to the frozen JSON."""

    require_native_vendor_tree_paths(native_vendor_tree_paths)
    require_rust_compiled_source_tree_paths(rust_compiled_source_tree_paths)
    require_rust_package_build_script_paths(rust_package_build_script_paths)
    require_rust_cargo_target_source_paths(rust_cargo_target_source_paths)
    try:
        source = qualification_source_raw.decode("ascii")
        probe = probe_source_raw.decode("ascii")
        activation_test = transitive_sources_raw[
            ACTIVATION_TEST_RELATIVE_PATH.as_posix()
        ].decode("ascii")
    except UnicodeError as exc:
        raise NativeFixed64CPUProfileV5Error(
            "native qualification, probe, and activation-test sources must be ASCII"
        ) from exc
    except KeyError as exc:
        raise NativeFixed64CPUProfileV5Error(
            "release activation-test source is absent from the transitive manifest"
        ) from exc
    try:
        docking_source = docking_source_raw.decode("utf-8")
        native_pipeline_source = native_pipeline_source_raw.decode("utf-8")
    except UnicodeError as exc:
        raise NativeFixed64CPUProfileV5Error(
            "native pipeline sources must be UTF-8"
        ) from exc

    profile_id_matches = re.findall(
        r'pub const FIXED64_CPU_QUALIFICATION_V5_PROFILE_ID: &str\s*=\s*"([^"]+)";',
        source,
    )
    if profile_id_matches != [PROFILE_ID]:
        _fail("compiled qualification profile identity changed")

    core = profile["measurement_core"]
    if type(core) is not dict:
        _fail("profile measurement core is unavailable for compiled binding")
    if hashlib.sha256(qualification_source_raw).hexdigest() != core.get(
        "native_qualification_source_sha256"
    ):
        _fail("compiled qualification source changed from the frozen profile")
    if hashlib.sha256(probe_source_raw).hexdigest() != core.get(
        "native_probe_source_sha256"
    ):
        _fail("compiled native probe source changed from the frozen profile")
    if hashlib.sha256(docking_source_raw).hexdigest() != core.get(
        "native_rust_pipeline_source_sha256"
    ):
        _fail("compiled native Rust pipeline source changed from the frozen profile")
    if hashlib.sha256(native_pipeline_source_raw).hexdigest() != core.get(
        "native_cpp_pipeline_source_sha256"
    ):
        _fail("compiled native C++ pipeline source changed from the frozen profile")
    transitive_digest = _transitive_source_manifest_sha256(transitive_sources_raw)
    if transitive_digest != core.get("native_transitive_source_manifest_sha256"):
        _fail(
            "compiled native transitive source manifest changed from the frozen profile"
        )
    direct_sources = {
        QUALIFICATION_SOURCE_RELATIVE_PATH.as_posix(): qualification_source_raw,
        DOCKING_SOURCE_RELATIVE_PATH.as_posix(): docking_source_raw,
        NATIVE_PIPELINE_SOURCE_RELATIVE_PATH.as_posix(): native_pipeline_source_raw,
        PROBE_SOURCE_RELATIVE_PATH.as_posix(): probe_source_raw,
    }
    if any(
        source_raw != transitive_sources_raw.get(path)
        for path, source_raw in direct_sources.items()
    ):
        _fail(
            "compiled pipeline source inputs are cross-wired from the transitive manifest"
        )
    library_activation_function = re.compile(
        r"pub\s+const\s+fn\s+fixed64_cpu_v5_live_activation_admitted\(\)"
        r"\s*->\s*bool\s*\{\s*FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED\s*\}"
    )
    unit_test_profile_gate = "if config != Fixed64CpuProbeConfigV5::unit_test()"
    qualification_profile_gate = (
        "if config != Fixed64CpuProbeConfigV5::qualification_profile()"
    )
    library_activation_guard = "if !fixed64_cpu_v5_live_activation_admitted()"
    fixture_construction = "let fixture = SyntheticFixture::new();"
    if (
        source.count("pub const FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED: bool = false;")
        != 1
        or len(library_activation_function.findall(source)) != 1
        or source.count(unit_test_profile_gate) != 1
        or source.count(qualification_profile_gate) != 1
        or source.count(library_activation_guard) != 1
        or source.count(fixture_construction) != 1
        or not (
            source.index(unit_test_profile_gate)
            < source.index(qualification_profile_gate)
            < source.index(library_activation_guard)
        )
        or source.index(library_activation_guard) > source.index(fixture_construction)
    ):
        _fail("compiled public qualification API is not activation-gated")

    constant_observation = re.compile(
        r"let\s+activation_constant\s*=\s*std::hint::black_box\("
        r"\s*FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED\s*\);"
    )
    constant_observation_matches = list(constant_observation.finditer(activation_test))
    constant_assertion = "assert!(!activation_constant);"
    function_assertion = "assert!(!fixed64_cpu_v5_live_activation_admitted());"
    binary_launch = (
        'Command::new(env!("CARGO_BIN_EXE_betelgeuze-fixed64-cpu-probe-v5"))'
    )
    if (
        len(constant_observation_matches) != 1
        or activation_test.count(constant_assertion) != 1
        or activation_test.count(function_assertion) != 1
        or activation_test.count(binary_launch) != 1
        or not (
            constant_observation_matches[0].end()
            < activation_test.index(constant_assertion)
            < activation_test.index(function_assertion)
            < activation_test.index(binary_launch)
        )
    ):
        _fail("release non-test activation artifact check is missing or reordered")

    native_pipeline_profile_id = core.get("native_pipeline_profile_id")
    rust_pipeline_id_matches = re.findall(
        r'pub const FIXED64_NATIVE_PIPELINE_PROFILE_ID: &str\s*=\s*"([^"]+)";',
        docking_source,
    )
    cpp_pipeline_id_matches = re.findall(
        r'constexpr char kProfileIdV2\[\]\s*=\s*"([^"]+)";',
        native_pipeline_source,
    )
    if (
        rust_pipeline_id_matches != [native_pipeline_profile_id]
        or cpp_pipeline_id_matches != [native_pipeline_profile_id]
        or docking_source.count(str(native_pipeline_profile_id)) != 1
        or docking_source.count("FIXED64_NATIVE_PIPELINE_PROFILE_ID") != 6
        or native_pipeline_source.count(str(native_pipeline_profile_id)) != 1
        or native_pipeline_source.count("kProfileIdV2") != 6
        or native_pipeline_source.count(
            "return betelgeuze::native::docking::fixed64_pipeline::kProfileIdV2;"
        )
        != 1
        or native_pipeline_source.count("bg_docking_fixed64_pipeline_v2_profile_id")
        != 1
        or native_pipeline_source.count("bg_docking_fixed64_pipeline_v2_run") != 1
        or docking_source.count("sys::bg_docking_fixed64_pipeline_v2_create") != 1
        or docking_source.count("sys::bg_docking_fixed64_pipeline_v2_run") != 1
        or docking_source.count("Self::profile_id()?;") != 1
        or docking_source.count("profile_id != FIXED64_NATIVE_PIPELINE_PROFILE_ID") != 1
        or docking_source.count("hash.string(FIXED64_NATIVE_PIPELINE_PROFILE_ID);") != 3
        or docking_source.count(
            "pipeline_batch.string(FIXED64_NATIVE_PIPELINE_PROFILE_ID);"
        )
        != 1
    ):
        _fail("compiled native pipeline profile identity changed")

    header_source = transitive_sources_raw.get("include/betelgeuze/engine.h")
    if (
        header_source is None
        or header_source.count(b"#define BG_ABI_VERSION_MAJOR UINT32_C(1)") != 1
        or header_source.count(b"#define BG_ABI_VERSION_MINOR UINT32_C(21)") != 1
        or core.get("native_abi_version") != "1.21"
    ):
        _fail("compiled native ABI identity changed")

    v2_run_marker = "bg_docking_fixed64_pipeline_v2_run("
    post_gate_call = "bg_docking_geometric_admission_v1_evaluate_fixed64("
    downstream_call = "bg_docking_fixed64_downstream_v1_run("
    inactive_mapping = (
        "admitted ? BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE\n"
        "                         : BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE;"
    )
    if native_pipeline_source.count(v2_run_marker) != 1:
        _fail("compiled post-admission pipeline entry point changed")
    v2_run_source = native_pipeline_source[
        native_pipeline_source.index(v2_run_marker) :
    ]
    if (
        v2_run_source.count(post_gate_call) != 1
        or v2_run_source.count(downstream_call) != 1
        or v2_run_source.count(inactive_mapping) != 1
        or not (
            v2_run_source.index(post_gate_call)
            < v2_run_source.index(inactive_mapping)
            < v2_run_source.index(downstream_call)
        )
    ):
        _fail("post-refinement admission is not fail-closed before ScorerV1")

    post_projection_fields = (
        "row.post_admission.raw_minimum_distance_angstrom",
        "row.post_admission.minimum_vdw_surface_gap_angstrom",
        "row.post_admission.minimum_vdw_ratio",
        "row.post_admission.sphere_overlap_proxy_angstrom3",
        "row.post_admission.pocket_escape_angstrom",
    )
    if (
        any(source.count(field) != 1 for field in post_projection_fields)
        or source.count("fixture.numeric_parity.compared_f64_count == 28_544") != 1
        or source.count("row.scorer.weighted_terms") != 1
        or source.count("row.validity.rotation_orthogonality_max_error") != 1
    ):
        _fail("complete post-admission scorer/validity numeric parity changed")

    config_matches = re.findall(
        r"pub const fn qualification_profile\(\) -> Self \{\s*"
        r"Self \{\s*"
        r"warmup_rounds:\s*(\d+),\s*"
        r"sample_rounds:\s*(\d+),\s*"
        r"absolute_tolerance:\s*([0-9.eE+-]+),\s*"
        r"relative_tolerance:\s*([0-9.eE+-]+),\s*"
        r"maximum_rust_to_cpp_median_ratio:\s*([0-9.eE+-]+),\s*"
        r"\}\s*\}",
        source,
    )
    if len(config_matches) != 1:
        _fail("compiled qualification gate definition changed")
    warmup, samples, absolute, relative, ratio = config_matches[0]
    sampling = profile["sampling"]
    numeric = profile["numeric_parity"]
    performance = profile["performance"]
    if (
        type(sampling) is not dict
        or type(numeric) is not dict
        or type(performance) is not dict
    ):
        _fail("profile gate sections are unavailable for compiled binding")
    try:
        compiled_gate = {
            "warmup_rounds": int(warmup),
            "sample_rounds": int(samples),
            "absolute_tolerance": float(absolute),
            "relative_tolerance": float(relative),
            "maximum_ratio": float(ratio),
        }
    except ValueError as exc:
        raise NativeFixed64CPUProfileV5Error(
            "compiled qualification gate is not numeric"
        ) from exc
    expected_gate = {
        "warmup_rounds": sampling["warmup_rounds"],
        "sample_rounds": sampling["sample_rounds"],
        "absolute_tolerance": numeric["absolute_tolerance"],
        "relative_tolerance": numeric["relative_tolerance"],
        "maximum_ratio": performance["maximum_ratio"],
    }
    if compiled_gate != expected_gate:
        _fail("compiled qualification gate drifted from the frozen profile")

    slot_matches = re.findall(r"const SLOT_COUNT: usize = (\d+);", source)
    atom_matches = re.findall(r"const LIGAND_ATOM_COUNT: usize = (\d+);", source)
    fixtures = profile["fixtures"]
    gates = profile["gates"]
    if type(fixtures) is not list or type(gates) is not dict:
        _fail("profile fixture or gate sections are unavailable for compiled binding")
    expected_atoms = {
        fixture["receptor_atom_count"] for fixture in fixtures if type(fixture) is dict
    } | {fixture["ligand_atom_count"] for fixture in fixtures if type(fixture) is dict}
    if len(expected_atoms) != 1:
        _fail("frozen fixtures do not share one compiled atom denominator")
    expected_atom_count = next(iter(expected_atoms))
    if slot_matches != [str(gates["candidate_denominator_exact"])] or atom_matches != [
        str(expected_atom_count)
    ]:
        _fail("compiled fixed64 or atom denominator drifted from the frozen profile")

    expected_counts = [
        (
            fixture["expected_generated_count"],
            fixture["expected_typed_failure_count"],
        )
        for fixture in fixtures
        if type(fixture) is dict
    ]
    compiled_counts = [
        tuple(int(value) for value in match)
        for match in re.findall(
            r"Self::(?:Complete|FeatureSparse) => \((\d+), (\d+)\)", source
        )
    ]
    if compiled_counts != expected_counts:
        _fail("compiled fixture counts drifted from the frozen profile")

    expected_fixture_ids = [
        fixture["fixture_id"] for fixture in fixtures if type(fixture) is dict
    ]
    compiled_fixture_ids = [
        fixture_id
        for _, fixture_id in re.findall(
            r'Self::(Complete|FeatureSparse)\s*=>\s*"([^"]+)"', source
        )
    ]
    if compiled_fixture_ids != expected_fixture_ids:
        _fail("compiled fixture identities drifted from the frozen profile")

    expected_fixture_payloads = [
        fixture["fixture_payload_sha256"]
        for fixture in fixtures
        if type(fixture) is dict
    ]
    compiled_fixture_payloads = re.findall(
        r"const (?:COMPLETE|FEATURE_SPARSE)_FIXTURE_PAYLOAD_SHA256_HEX: "
        r'&str\s*=\s*"([0-9a-f]{64})";',
        source,
    )
    fixture_payload_mappings = re.findall(
        r"Self::(Complete|FeatureSparse)\s*=>\s*"
        r"((?:COMPLETE|FEATURE_SPARSE)_FIXTURE_PAYLOAD_SHA256_HEX)",
        source,
    )
    if (
        compiled_fixture_payloads != expected_fixture_payloads
        or fixture_payload_mappings
        != [
            ("Complete", "COMPLETE_FIXTURE_PAYLOAD_SHA256_HEX"),
            (
                "FeatureSparse",
                "FEATURE_SPARSE_FIXTURE_PAYLOAD_SHA256_HEX",
            ),
        ]
        or source.count(
            "canonical_fixture_payload_sha256(variant, scientific_context, input)"
        )
        != 1
        or source.count(
            "fixture_payload_sha256_hex != variant.expected_payload_sha256_hex()"
        )
        != 1
        or probe.count("digest(value.fixture_payload_sha256)") != 1
    ):
        _fail("compiled fixture payload identities drifted from the frozen profile")

    scorer_term_matches = re.findall(
        r"const FROZEN_SCORER_V1_TERM_COUNT: usize = (\d+);", source
    )
    scorer_term_assertions = re.findall(
        r"const _:\s*\[\(\);\s*FROZEN_SCORER_V1_TERM_COUNT\]\s*=\s*"
        r"\[\(\);\s*sys::BG_DOCKING_SCORER_V1_TERM_COUNT as usize\];",
        source,
    )
    runtime_scorer_gate = (
        "sys::BG_DOCKING_SCORER_V1_TERM_COUNT as usize == FROZEN_SCORER_V1_TERM_COUNT"
    )
    if (
        scorer_term_matches != [str(gates["score_term_count_exact"])]
        or len(scorer_term_assertions) != 1
        or source.count(runtime_scorer_gate) != 1
        or source.count(
            "score_term_count: sys::BG_DOCKING_SCORER_V1_TERM_COUNT as usize"
        )
        != 1
        or probe.count("value.score_term_count") != 1
    ):
        _fail("compiled ScorerV1 term-count gate drifted from the frozen profile")

    activation_guard = "if !fixed64_cpu_v5_live_activation_admitted()"
    qualification_call = "Fixed64CpuProbeConfigV5::qualification_profile()"
    qualification_binding = (
        "let config = Fixed64CpuProbeConfigV5::qualification_profile();"
    )
    measurement_call = "run_native_fixed64_cpu_probe_v5(config)"
    if (
        probe.count("fixed64_cpu_v5_live_activation_admitted") != 2
        or "FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED" in probe
        or probe.count(activation_guard) != 1
        or probe.count("return ExitCode::from(3);") != 1
        or probe.count(qualification_call) != 1
        or probe.count(qualification_binding) != 1
        or probe.count("Fixed64CpuProbeConfigV5") != 2
        or "Fixed64CpuProbeConfigV5::unit_test()" in probe
        or "Fixed64CpuProbeConfigV5 {" in probe
        or probe.count(measurement_call) != 1
        or probe.count("run_native_fixed64_cpu_probe_v5") != 2
    ):
        _fail("native probe entry point is not bound to the qualification profile")
    if not (
        probe.index(activation_guard)
        < probe.index(qualification_binding)
        < probe.index(measurement_call)
    ):
        _fail(
            "native probe activation gate does not precede configuration and measurement"
        )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    raw = (root / PROFILE_RELATIVE_PATH).read_bytes()
    profile = require_profile_document(raw)
    require_repository_cargo_configuration_absent(root)
    require_repository_rust_toolchain_override_absent(root)
    vendor_tree_paths = discover_native_vendor_tree_paths(root)
    rust_source_tree_paths = discover_rust_compiled_source_tree_paths(root)
    rust_build_script_paths = discover_rust_package_build_script_paths(root)
    rust_cargo_target_paths = discover_rust_cargo_target_source_paths(root)
    transitive_sources = read_bound_transitive_sources(root)
    require_compiled_profile_binding(
        profile,
        transitive_sources[QUALIFICATION_SOURCE_RELATIVE_PATH.as_posix()],
        transitive_sources[DOCKING_SOURCE_RELATIVE_PATH.as_posix()],
        transitive_sources[NATIVE_PIPELINE_SOURCE_RELATIVE_PATH.as_posix()],
        transitive_sources[PROBE_SOURCE_RELATIVE_PATH.as_posix()],
        transitive_sources,
        vendor_tree_paths,
        rust_source_tree_paths,
        rust_build_script_paths,
        rust_cargo_target_paths,
    )
    print(
        json.dumps(
            {
                "all_authority_false": True,
                "candidate_denominator": 64,
                "compiled_profile_binding_verified": True,
                "execution_consumed": False,
                "fixture_count": 2,
                "profile_id": PROFILE_ID,
                "profile_sha256": hashlib.sha256(raw).hexdigest(),
                "reservation_created": False,
                "status": "verified",
            },
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
