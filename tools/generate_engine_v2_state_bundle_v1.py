#!/usr/bin/env python3
"""Generate an exact-source Engine V2 implementation/authority/release bundle.

The generator is repository-local and read-only apart from its absent output
directory.  It inventories source facts; it never executes molecular, GPU,
reservation, supervisor, benchmark, or qualification work.
"""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

IMPLEMENTATION_SCHEMA_ID = "betelgeuze.engine_v2_implementation_state/1.0.0"
AUTHORITY_SCHEMA_ID = "betelgeuze.engine_v2_authority_state/1.0.0"
RELEASE_SCHEMA_ID = "betelgeuze.engine_v2_release_manifest/1.0.0"
ENGINE_ID = "betelgeuze_independent_engine_v2"
GENERATOR_PATH = Path("tools/generate_engine_v2_state_bundle_v1.py")

AUTHORITY_PATH = Path("config/engine_v2_authority_state_v1.json")
CAPABILITIES_PATH = Path("config/independent_engine_v2_capabilities.yaml")
OPERATIONS_DECISION_PATH = Path(
    "config/engine_v2_source_paired_clearance_external_reservation_operations_decision.json"
)
STAGE0_STATUS_PATH = Path("docs/engine_v2_stage0_status.md")
CPU_V7_RESULT_PATH = Path(
    "docs/engine_v2_native_fixed64_cpu_qualification_v7_result.md"
)
D1_PROFILE_PATH = Path("config/engine_v2_d1_development_profile_v1.json")
SAMPLING_PROFILE_PATH = Path("config/engine_v2_sampling_funnel_v1.json")

PYTHON_PACKAGE_PATH = Path("packaging/engine-v2/pyproject.toml")
NATIVE_PACKAGE_PATH = Path("rust_engine_v2/pyproject.toml")
ROOT_CMAKE_PATH = Path("CMakeLists.txt")
NATIVE_CMAKE_PATH = Path("native/CMakeLists.txt")
RUST_SYS_PATH = Path("rust/betelgeuze-sys/src/lib.rs")
RUST_WORKSPACE_MANIFEST_PATH = Path("rust/Cargo.toml")
RUST_WORKSPACE_LOCK_PATH = Path("rust/Cargo.lock")
RUST_CPU_CRATE_MANIFEST_PATH = Path("rust/cpu-kernel/Cargo.toml")
RUST_DOCKING_SEARCH_MANIFEST_PATH = Path(
    "rust/betelgeuze-docking-search/Cargo.toml"
)
REPOSITORY_CARGO_CONFIG_PATHS = (
    Path(".cargo/config"),
    Path(".cargo/config.toml"),
)
RUST_CPU_PROVIDER_CONTROL_PATHS = (
    RUST_WORKSPACE_MANIFEST_PATH,
    RUST_WORKSPACE_LOCK_PATH,
)
SAMPLING_POOL_PATH = Path("rust/betelgeuze-docking-search/src/sampling_pool.rs")
SAMPLING_FUNNEL_PATH = Path("rust/betelgeuze-docking-search/src/sampling_funnel.rs")
FIXED64_PATH = Path("rust/betelgeuze-docking-search/src/fixed64.rs")
SCORER_PATH = Path("rust/betelgeuze-docking-search/src/scorer_v1.rs")
PIPELINE_TYPES_PATH = Path("rust/betelgeuze-runtime/src/docking/types.rs")
CPP_CPU_BACKEND_PATH = Path("native/src/cpu/evaluator.cpp")
RUST_CPU_BACKEND_PATH = Path("native/src/rust/evaluator.cpp")
RUST_CPU_EVALUATOR_HEADER_PATH = Path("native/src/rust/evaluator.hpp")
RUST_CPU_PROVIDER_HEADER_PATH = Path("native/src/rust/provider.h")
RUST_CPU_BRIDGE_PATHS = (
    RUST_CPU_BACKEND_PATH,
    RUST_CPU_EVALUATOR_HEADER_PATH,
    RUST_CPU_PROVIDER_HEADER_PATH,
)
HIP_SAFE_WRAPPER_PATH = Path("native/src/hip/evaluator.cpp")
HIP_SAFE_PROVIDER_PATH = Path("native/src/hip/provider.hip")
HIP_FAST_BACKEND_PATH = Path("native/src/hip/backend.hip")

VINA_ADAPTER_PATH = Path("benchmarks/oracles/vina/adapter.py")
GNINA_ADAPTER_PATH = Path("benchmarks/oracles/gnina/adapter.py")
D1_MATERIALIZER_PATH = Path("tools/materialize_engine_v2_d1_case_results_v1.py")
D1_RUNNER_PATH = Path("tools/run_engine_v2_d1_development_v2.py")
D1_VERIFIER_PATH = Path("tools/verify_engine_v2_d1_development_v2.py")

D1_REPOSITORY_OUTPUTS = (
    Path("config/engine_v2_d1_manifest_v1.json"),
    Path("benchmarks/engine_v2_d1/baseline/manifest.json"),
    Path("benchmarks/engine_v2_d1/current/manifest.json"),
    Path("benchmarks/engine_v2_d1/current-vs-baseline-report.json"),
)

ABI_SURFACES = {
    "core": (Path("include/betelgeuze/engine.h"), "BG_ABI_VERSION"),
    "direct_ewald": (
        Path("include/betelgeuze/direct_ewald.h"),
        "BG_DIRECT_EWALD_ABI_VERSION",
    ),
    "direct_ewald_composite": (
        Path("include/betelgeuze/direct_ewald_composite.h"),
        "BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION",
    ),
    "direct_ewald_composite_dynamics": (
        Path("include/betelgeuze/direct_ewald_composite_dynamics.h"),
        "BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION",
    ),
    "particle_mesh_reciprocal": (
        Path("include/betelgeuze/particle_mesh_reciprocal.h"),
        "BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION",
    ),
    "particle_mesh_ewald": (
        Path("include/betelgeuze/particle_mesh_ewald.h"),
        "BG_PARTICLE_MESH_EWALD_ABI_VERSION",
    ),
    "particle_mesh_ewald_composite": (
        Path("include/betelgeuze/particle_mesh_ewald_composite.h"),
        "BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION",
    ),
    "particle_mesh_ewald_composite_dynamics": (
        Path("include/betelgeuze/particle_mesh_ewald_composite_dynamics.h"),
        "BG_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION",
    ),
}

EXPECTED_BLOCKERS = [
    "external_reservation_provider_not_operational",
    "external_reservation_endpoint_not_configured",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
]
EXPECTED_EXECUTION_FIELDS = {
    "customer_execution_enabled",
    "customer_pose_emission_authorized",
    "external_reservation_authorized",
    "fresh_128_execution_authorized",
    "hip_device_execution_authorized",
    "molecular_holdout_execution_authorized",
    "product_execution_authorized",
    "public_benchmark_execution_authorized",
    "stage0_admission_authorized",
    "supervisor_operation_authorized",
}
EXPECTED_CLAIM_FIELDS = {
    "benchmark_validity_green",
    "docking_accuracy_claim_allowed",
    "free_energy_claim_allowed",
    "gpu_acceleration_claim_allowed",
    "scientific_validity_green",
}
EXPECTED_QUALIFICATION_GUARD = {
    "native_fixed64_cpu_v7_authoritative": False,
    "native_fixed64_cpu_v7_consumed": True,
    "native_fixed64_cpu_v7_rerun_authorized": False,
}
EXPECTED_OPERATIONS_AUTHORITY_FIELDS = {
    "customer_pose_emission_authorized",
    "fresh_holdout_execution_authorized",
    "historical_execution_operational",
    "product_execution_authorized",
    "profile_promotion_authority",
    "public_or_scientific_claim_authorized",
    "stage0_admission_authority",
}
EXPECTED_D1_AUTHORITY_FIELDS = {
    "benchmark_claim_authorized",
    "fresh_128_execution_authorized",
    "molecular_holdout_execution_authorized",
    "product_authorized",
    "reservation_authorized",
    "scientific_claim_authorized",
}
EXPECTED_SAMPLING_AUTHORITY_FIELDS = {
    "benchmark_claim_authorized",
    "fresh_128_execution_authorized",
    "product_authorized",
    "rank_mutation_authorized",
    "scientific_claim_authorized",
}

IMPLEMENTATION_SOURCE_PATHS = tuple(
    sorted(
        {
            PYTHON_PACKAGE_PATH,
            NATIVE_PACKAGE_PATH,
            ROOT_CMAKE_PATH,
            NATIVE_CMAKE_PATH,
            RUST_SYS_PATH,
            *RUST_CPU_PROVIDER_CONTROL_PATHS,
            RUST_CPU_CRATE_MANIFEST_PATH,
            SAMPLING_POOL_PATH,
            SAMPLING_FUNNEL_PATH,
            SAMPLING_PROFILE_PATH,
            FIXED64_PATH,
            SCORER_PATH,
            PIPELINE_TYPES_PATH,
            VINA_ADAPTER_PATH,
            GNINA_ADAPTER_PATH,
            D1_PROFILE_PATH,
            D1_MATERIALIZER_PATH,
            D1_RUNNER_PATH,
            D1_VERIFIER_PATH,
            CPP_CPU_BACKEND_PATH,
            *RUST_CPU_BRIDGE_PATHS,
            HIP_SAFE_WRAPPER_PATH,
            HIP_SAFE_PROVIDER_PATH,
            HIP_FAST_BACKEND_PATH,
            *(path for path, _macro in ABI_SURFACES.values()),
            *(
                Path("rust/betelgeuze-sys/vendor") / path
                for path, _macro in ABI_SURFACES.values()
            ),
        },
        key=lambda value: value.as_posix(),
    )
)
VERIFIED_REQUIRED_PATHS = tuple(
    sorted(
        set(IMPLEMENTATION_SOURCE_PATHS)
        | {
            GENERATOR_PATH,
            AUTHORITY_PATH,
            CAPABILITIES_PATH,
            OPERATIONS_DECISION_PATH,
            STAGE0_STATUS_PATH,
            CPU_V7_RESULT_PATH,
        },
        key=lambda value: value.as_posix(),
    )
)

_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA64_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:a|b|rc)?[0-9]*$")


class StateBundleError(ValueError):
    """A source, authority, or generated-state invariant is invalid."""


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StateBundleError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _symlink_component(root: Path, relative: Path) -> Path | None:
    if relative.is_absolute() or ".." in relative.parts:
        raise StateBundleError(f"repository source path must stay below root: {relative}")
    candidate = root
    for part in relative.parts:
        candidate /= part
        if candidate.is_symlink():
            return candidate.relative_to(root)
    return None


def _path(root: Path, relative: Path) -> Path:
    symlink = _symlink_component(root, relative)
    candidate = root / relative
    if symlink is not None or not candidate.is_file():
        detail = f" (symlink component: {symlink})" if symlink is not None else ""
        raise StateBundleError(
            f"source must be a non-symlink regular file: {relative}{detail}"
        )
    return candidate


def _is_regular_repository_file(root: Path, relative: Path) -> bool:
    return _symlink_component(root, relative) is None and (root / relative).is_file()


def _directory(root: Path, relative: Path) -> Path:
    symlink = _symlink_component(root, relative)
    candidate = root / relative
    if symlink is not None or not candidate.is_dir():
        detail = f" (symlink component: {symlink})" if symlink is not None else ""
        raise StateBundleError(
            f"source must be a non-symlink directory: {relative}{detail}"
        )
    return candidate


def _load_toml(root: Path, relative: Path) -> dict[str, Any]:
    try:
        value = tomllib.loads(_text(root, relative))
    except tomllib.TOMLDecodeError as exc:
        raise StateBundleError(f"cannot parse {relative}: {exc}") from exc
    if type(value) is not dict:
        raise StateBundleError(f"{relative} must contain a TOML table")
    return value


def _cargo_path_dependency_manifests(root: Path, manifest: Path) -> tuple[Path, ...]:
    value = _load_toml(root, manifest)
    package = value.get("package")
    if type(package) is not dict:
        raise StateBundleError(f"{manifest} package table must be an object")
    build_setting = package.get("build")
    default_build_script = manifest.parent / "build.rs"
    if build_setting not in (None, False) or (
        build_setting is None
        and (
            (root / default_build_script).exists()
            or (root / default_build_script).is_symlink()
        )
    ):
        raise StateBundleError(f"{manifest} build scripts are unsupported")
    library = value.get("lib", {})
    if type(library) is not dict or "path" in library:
        raise StateBundleError(f"{manifest} custom library paths are unsupported")
    binaries = value.get("bin", [])
    if type(binaries) is not list or any(
        type(binary) is not dict or "path" in binary for binary in binaries
    ):
        raise StateBundleError(f"{manifest} custom binary paths are unsupported")
    dependency_tables: list[tuple[str, Any]] = [
        ("dependencies", value.get("dependencies", {})),
        ("build-dependencies", value.get("build-dependencies", {})),
    ]
    targets = value.get("target", {})
    if type(targets) is not dict:
        raise StateBundleError(f"{manifest} target table must be an object")
    for target_name, target in targets.items():
        if type(target) is not dict:
            raise StateBundleError(f"{manifest} target.{target_name} must be an object")
        dependency_tables.extend(
            (
                (f"target.{target_name}.dependencies", target.get("dependencies", {})),
                (
                    f"target.{target_name}.build-dependencies",
                    target.get("build-dependencies", {}),
                ),
            )
        )
    dependencies: set[Path] = set()
    for table_name, table in dependency_tables:
        if type(table) is not dict:
            raise StateBundleError(f"{manifest} {table_name} must be an object")
        for dependency_name, specification in table.items():
            if type(specification) is dict and specification.get("workspace") is True:
                raise StateBundleError(
                    f"{manifest} workspace-inherited dependency is unsupported: "
                    f"{dependency_name}"
                )
            if type(specification) is not dict or "path" not in specification:
                continue
            path_value = specification["path"]
            if type(path_value) is not str or not path_value:
                raise StateBundleError(
                    f"{manifest} dependency {dependency_name} path must be a string"
                )
            dependency_manifest = Path(
                os.path.normpath(
                    str(manifest.parent / Path(path_value) / "Cargo.toml")
                )
            )
            if not dependency_manifest.parts or dependency_manifest.parts[0] != "rust":
                raise StateBundleError(
                    f"{manifest} dependency {dependency_name} must stay below rust/"
                )
            _path(root, dependency_manifest)
            dependencies.add(dependency_manifest)
    return tuple(sorted(dependencies, key=lambda value: value.as_posix()))


def rust_cpu_provider_crate_manifest_paths(root: Path) -> tuple[Path, ...]:
    for cargo_config in REPOSITORY_CARGO_CONFIG_PATHS:
        if (root / cargo_config).exists() or (root / cargo_config).is_symlink():
            raise StateBundleError(
                f"repository Cargo configuration is unsupported: {cargo_config}"
            )
    workspace = _load_toml(root, RUST_WORKSPACE_MANIFEST_PATH)
    for override in ("patch", "replace"):
        if workspace.get(override):
            raise StateBundleError(
                f"Rust workspace {override} overrides are unsupported"
            )
    pending = [RUST_CPU_CRATE_MANIFEST_PATH]
    manifests: set[Path] = set()
    while pending:
        manifest = pending.pop()
        if manifest in manifests:
            continue
        _path(root, manifest)
        manifests.add(manifest)
        pending.extend(_cargo_path_dependency_manifests(root, manifest))
    workspace_table = workspace.get("workspace")
    if type(workspace_table) is not dict:
        raise StateBundleError("Rust workspace table must be an object")
    members = workspace_table.get("members")
    excluded = workspace_table.get("exclude", [])
    if (
        type(members) is not list
        or not members
        or any(type(pattern) is not str or not pattern for pattern in members)
        or type(excluded) is not list
        or any(type(pattern) is not str or not pattern for pattern in excluded)
    ):
        raise StateBundleError("Rust workspace membership must use explicit patterns")
    for manifest in manifests:
        relative_crate = manifest.parent.relative_to(
            RUST_WORKSPACE_MANIFEST_PATH.parent
        ).as_posix()
        if not any(fnmatchcase(relative_crate, pattern) for pattern in members) or any(
            fnmatchcase(relative_crate, pattern) for pattern in excluded
        ):
            raise StateBundleError(
                f"Rust CPU provider crate is not a workspace member: {manifest}"
            )
    return tuple(sorted(manifests, key=lambda value: value.as_posix()))


def rust_cpu_provider_source_directories(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            {manifest.parent / "src" for manifest in rust_cpu_provider_crate_manifest_paths(root)},
            key=lambda value: value.as_posix(),
        )
    )


_RUST_FILE_INPUT_RE = re.compile(
    r"\b(?P<macro>include|include_bytes|include_str)\s*!\s*\("
)
_RUST_FILE_INPUT_NAME_RE = re.compile(
    r"\b(?:include|include_bytes|include_str)\b"
)
_RUST_ATTRIBUTE_PATH_RE = re.compile(
    r"\b(?:r#)?path\b\s*="
)
_RUST_RAW_STRING_START_RE = re.compile(r'(?:br|r)(?P<hashes>#{0,255})"')


def _mask_rust_comments_and_strings(value: str) -> str:
    masked = list(value)
    index = 0
    while index < len(value):
        following = value[index + 1] if index + 1 < len(value) else ""
        if value[index] == "/" and following == "/":
            end = value.find("\n", index + 2)
            end = len(value) if end < 0 else end
            for position in range(index, end):
                masked[position] = " "
            index = end
            continue
        if value[index] == "/" and following == "*":
            depth = 1
            end = index + 2
            while end < len(value) and depth:
                if value[end : end + 2] == "/*":
                    depth += 1
                    end += 2
                elif value[end : end + 2] == "*/":
                    depth -= 1
                    end += 2
                else:
                    end += 1
            if depth:
                raise StateBundleError("Rust CPU provider source has an unterminated comment")
            for position in range(index, end):
                if value[position] != "\n":
                    masked[position] = " "
            index = end
            continue
        raw = (
            _RUST_RAW_STRING_START_RE.match(value, index)
            if value[index] in ("b", "r")
            else None
        )
        if raw is not None:
            terminator = f'"{raw.group("hashes")}'
            end = value.find(terminator, raw.end())
            if end < 0:
                raise StateBundleError("Rust CPU provider source has an unterminated raw string")
            end += len(terminator)
            for position in range(index, end):
                if value[position] != "\n":
                    masked[position] = " "
            index = end
            continue
        if value[index] == '"':
            end = index + 1
            while end < len(value):
                if value[end] == "\\" and end + 1 < len(value):
                    end += 2
                    continue
                if value[end] == '"':
                    end += 1
                    break
                end += 1
            else:
                raise StateBundleError("Rust CPU provider source has an unterminated string")
            for position in range(index, end):
                if value[position] != "\n":
                    masked[position] = " "
            index = end
            continue
        index += 1
    return "".join(masked)


def _rust_attribute_bodies(value: str) -> tuple[str, ...]:
    masked = _mask_rust_comments_and_strings(value)
    bodies = []
    for match in re.finditer(r"#\s*\[", masked):
        depth = 1
        index = match.end()
        while index < len(masked) and depth:
            if masked[index] == "[":
                depth += 1
            elif masked[index] == "]":
                depth -= 1
            index += 1
        if depth:
            raise StateBundleError("Rust CPU provider source has an unterminated attribute")
        bodies.append(masked[match.end() : index - 1])
    return tuple(bodies)


def _rust_literal_input_paths(root: Path, source: Path) -> tuple[Path, ...]:
    text = _text(root, source)
    if any(
        _RUST_ATTRIBUTE_PATH_RE.search(body) is not None
        for body in _rust_attribute_bodies(text)
    ):
        raise StateBundleError(
            f"Rust CPU provider source has an unsupported #[path] input: {source}"
        )
    file_inputs = list(_RUST_FILE_INPUT_RE.finditer(text))
    recognized_names = {match.start("macro") for match in file_inputs}
    if any(
        match.start() not in recognized_names
        for match in _RUST_FILE_INPUT_NAME_RE.finditer(text)
    ):
        raise StateBundleError(
            f"Rust CPU provider source has unsupported file-input syntax: {source}"
        )
    paths = []
    for match in file_inputs:
        close = text.find(")", match.end())
        if close < 0:
            raise StateBundleError(
                f"Rust CPU provider source has an unterminated file input: {source}"
            )
        argument = text[match.end() : close]
        literal = re.fullmatch(r'\s*"([^"\\\r\n]+)"\s*,?\s*', argument)
        if literal is None:
            raise StateBundleError(
                f"Rust CPU provider source has a non-literal file input: {source}"
            )
        relative = Path(
            os.path.normpath(str(source.parent / Path(literal.group(1))))
        )
        if relative.is_absolute() or ".." in relative.parts:
            raise StateBundleError(
                f"Rust CPU provider file input must stay below root: {source}"
            )
        if not relative.parts or relative.parts[0] != "rust":
            raise StateBundleError(
                f"Rust CPU provider file input must stay below rust/: {source}"
            )
        _path(root, relative)
        paths.append(relative)
    return tuple(paths)


def rust_cpu_provider_source_paths(root: Path) -> tuple[Path, ...]:
    manifests = rust_cpu_provider_crate_manifest_paths(root)
    paths = set(RUST_CPU_PROVIDER_CONTROL_PATHS) | set(manifests)
    pending_rust_sources: list[Path] = []
    for relative_directory in rust_cpu_provider_source_directories(root):
        directory = _directory(root, relative_directory)
        symlinked_entries = [
            candidate.relative_to(root)
            for candidate in directory.rglob("*")
            if candidate.is_symlink()
        ]
        if symlinked_entries:
            raise StateBundleError(
                "Rust CPU provider source tree contains symlink entries: "
                f"{sorted(path.as_posix() for path in symlinked_entries)}"
            )
        directory_sources = []
        for candidate in directory.rglob("*.rs"):
            relative = candidate.relative_to(root)
            _path(root, relative)
            paths.add(relative)
            pending_rust_sources.append(relative)
            directory_sources.append(relative)
        if not directory_sources:
            raise StateBundleError(
                f"Rust CPU provider source directory is empty: {relative_directory}"
            )
    scanned_rust_sources: set[Path] = set()
    while pending_rust_sources:
        source = pending_rust_sources.pop()
        if source in scanned_rust_sources:
            continue
        scanned_rust_sources.add(source)
        for literal_input in _rust_literal_input_paths(root, source):
            paths.add(literal_input)
            if literal_input.suffix == ".rs":
                pending_rust_sources.append(literal_input)
    return tuple(sorted(paths, key=lambda value: value.as_posix()))


def rust_cpu_provider_literal_input_paths(root: Path) -> tuple[Path, ...]:
    manifests = set(rust_cpu_provider_crate_manifest_paths(root))
    directories = rust_cpu_provider_source_directories(root)
    source_paths = set(rust_cpu_provider_source_paths(root))
    declared_sources = {
        path
        for path in source_paths
        if path.suffix == ".rs"
        and any(
            path.as_posix().startswith(f"{directory.as_posix()}/")
            for directory in directories
        )
    }
    return tuple(
        sorted(
            source_paths
            - set(RUST_CPU_PROVIDER_CONTROL_PATHS)
            - manifests
            - declared_sources,
            key=lambda value: value.as_posix(),
        )
    )


_PREPROCESSOR_DIRECTIVE_RE = re.compile(
    r"^\s*#\s*(?P<directive>[A-Za-z_][A-Za-z0-9_]*)\b(?P<operand>.*)$",
    re.MULTILINE,
)


def _strip_c_comments(value: str) -> str:
    output = []
    index = 0
    quoted: str | None = None
    while index < len(value):
        character = value[index]
        following = value[index + 1] if index + 1 < len(value) else ""
        if quoted is not None:
            output.append(character)
            if character == "\\" and following:
                output.append(following)
                index += 2
                continue
            if character == quoted:
                quoted = None
            index += 1
            continue
        if character in ('"', "'"):
            quoted = character
            output.append(character)
            index += 1
            continue
        if character == "/" and following == "/":
            index += 2
            while index < len(value) and value[index] != "\n":
                index += 1
            continue
        if character == "/" and following == "*":
            index += 2
            while index + 1 < len(value) and value[index : index + 2] != "*/":
                output.append("\n" if value[index] == "\n" else " ")
                index += 1
            if index + 1 >= len(value):
                raise StateBundleError("native source has an unterminated block comment")
            output.extend((" ", " "))
            index += 2
            continue
        output.append(character)
        index += 1
    return "".join(output)


def _resolve_local_include(
    root: Path, including: Path, include: str, *, quoted: bool
) -> Path | None:
    raw_candidates = (
        (including.parent / include, Path("include") / include, Path("native/src") / include)
        if quoted
        else (Path("include") / include, Path("native/src") / include)
    )
    for raw_candidate in raw_candidates:
        relative = Path(os.path.normpath(str(raw_candidate)))
        if relative.is_absolute() or ".." in relative.parts:
            continue
        candidate = root / relative
        if candidate.exists() or candidate.is_symlink():
            if relative.parts[:1] not in (("include",), ("native",)) or (
                relative.parts[0] == "native"
                and relative.parts[:2] != ("native", "src")
            ):
                raise StateBundleError(
                    f"native include must stay below include/ or native/src/: {relative}"
                )
            _path(root, relative)
            return relative
    if quoted:
        raise StateBundleError(f"cannot resolve local include {include!r} from {including}")
    return None


def _local_includes(root: Path, including: Path) -> tuple[Path, ...]:
    text = re.sub(r"\\\r?\n", "", _text(root, including))
    if re.search(r"\b(?:u8|u|U|L)?R\"", text):
        raise StateBundleError(
            f"C++ raw strings are unsupported in native include closure: {including}"
        )
    text = _strip_c_comments(text)
    if re.search(r"^\s*%:", text, flags=re.MULTILINE):
        raise StateBundleError(
            f"unsupported preprocessor digraph directive in {including}"
        )
    paths = []
    for match in _PREPROCESSOR_DIRECTIVE_RE.finditer(text):
        directive = match.group("directive")
        if directive != "include":
            if directive.startswith("include") or directive == "import":
                raise StateBundleError(
                    f"unsupported include directive in {including}: {directive}"
                )
            continue
        operand = match.group("operand").strip()
        quoted = re.fullmatch(r'"([^"]+)"\s*', operand)
        angled = re.fullmatch(r"<([^>]+)>\s*", operand)
        if quoted is not None:
            included = _resolve_local_include(
                root, including, quoted.group(1), quoted=True
            )
        elif angled is not None:
            included = _resolve_local_include(
                root, including, angled.group(1), quoted=False
            )
        else:
            raise StateBundleError(
                f"unsupported include operand in {including}: {operand!r}"
            )
        if included is not None:
            paths.append(included)
    return tuple(paths)


def rust_cpu_bridge_source_paths(root: Path) -> tuple[Path, ...]:
    pending = list(RUST_CPU_BRIDGE_PATHS)
    paths: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in paths:
            continue
        paths.add(path)
        for included in _local_includes(root, path):
            if included not in paths:
                pending.append(included)
    return tuple(sorted(paths, key=lambda value: value.as_posix()))


def implementation_source_paths(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            set(IMPLEMENTATION_SOURCE_PATHS)
            | set(rust_cpu_provider_source_paths(root))
            | set(rust_cpu_bridge_source_paths(root)),
            key=lambda value: value.as_posix(),
        )
    )


def verified_required_paths(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            set(VERIFIED_REQUIRED_PATHS) | set(implementation_source_paths(root)),
            key=lambda value: value.as_posix(),
        )
    )


def _require_running_generator(root: Path) -> None:
    symlink = _symlink_component(root, GENERATOR_PATH)
    if symlink is not None:
        raise StateBundleError(
            "verified repository generator path contains a symlink component: "
            f"{symlink}"
        )
    try:
        running_generator = Path(__file__).resolve(strict=True)
        repository_generator = (root / GENERATOR_PATH).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StateBundleError("executing generator path cannot be resolved") from exc
    if running_generator != repository_generator:
        raise StateBundleError(
            "executing generator must resolve to the verified repository generator"
        )


def _bytes(root: Path, relative: Path) -> bytes:
    try:
        return _path(root, relative).read_bytes()
    except OSError as exc:
        raise StateBundleError(f"cannot read {relative}: {exc}") from exc


def _text(root: Path, relative: Path) -> str:
    try:
        return _bytes(root, relative).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateBundleError(f"{relative} is not UTF-8") from exc


def _load_json(root: Path, relative: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            _text(root, relative), object_pairs_hook=_object_no_duplicates
        )
    except json.JSONDecodeError as exc:
        raise StateBundleError(f"cannot parse {relative}: {exc}") from exc
    if type(value) is not dict:
        raise StateBundleError(f"{relative} must contain a JSON object")
    return value


def _canonical_bytes(value: Any) -> bytes:
    try:
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
    except (TypeError, ValueError) as exc:
        raise StateBundleError("state bundle is not canonical JSON") from exc


def _canonical_compact_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise StateBundleError("source profile is not canonical JSON") from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(root: Path, relative: Path) -> str:
    return _sha256_bytes(_bytes(root, relative))


def _one(pattern: str, value: str, name: str, flags: int = re.MULTILINE) -> str:
    matches = re.findall(pattern, value, flags)
    if len(matches) != 1:
        raise StateBundleError(f"{name} must have exactly one source definition")
    match = matches[0]
    if isinstance(match, tuple):
        raise StateBundleError(f"{name} parser returned an ambiguous match")
    return match


def _toml_project(root: Path, relative: Path) -> tuple[str, str]:
    value = _text(root, relative)
    section = _one(
        r"^\[project\]\s*$\n(.*?)(?=^\[[^\]]+\]\s*$|\Z)",
        value,
        f"{relative} [project]",
        re.MULTILINE | re.DOTALL,
    )
    name = _one(r'^name\s*=\s*"([^"\n]+)"\s*$', section, f"{relative} name")
    version = _one(
        r'^version\s*=\s*"([^"\n]+)"\s*$', section, f"{relative} version"
    )
    if _VERSION_RE.fullmatch(version) is None:
        raise StateBundleError(f"{relative} has an invalid distribution version")
    return name, version


def _rust_string_constant(value: str, name: str) -> str:
    return _one(
        rf'pub const {re.escape(name)}\s*:[^=;]+?=\s*"([^"\n]+)"\s*;',
        value,
        name,
        re.MULTILINE | re.DOTALL,
    )


def _rust_integer_constant(value: str, name: str) -> int:
    raw = _one(
        rf"pub const {re.escape(name)}\s*:[^=;]+?=\s*([0-9_]+)\s*;",
        value,
        name,
        re.MULTILINE | re.DOTALL,
    )
    return int(raw.replace("_", ""))


def _rust_float_constant(value: str, name: str) -> float:
    raw = _one(
        rf"pub const {re.escape(name)}\s*:[^=;]+?=\s*([0-9]+(?:\.[0-9]+)?)\s*;",
        value,
        name,
        re.MULTILINE | re.DOTALL,
    )
    return float(raw)


def _rust_sha256_constant(value: str, name: str) -> bytes:
    body = _one(
        rf"pub const {re.escape(name)}:\s*\[u8;\s*32\]\s*=\s*\[(.*?)\]\s*;",
        value,
        name,
        re.MULTILINE | re.DOTALL,
    )
    octets = re.findall(r"0x([0-9a-fA-F]{2})", body)
    residual = re.sub(r"0x[0-9a-fA-F]{2}|[\s,]", "", body)
    if len(octets) != 32 or residual:
        raise StateBundleError(f"{name} must contain exactly 32 byte literals")
    return bytes.fromhex("".join(octets))


def _macro_integer(value: str, name: str) -> int:
    return int(
        _one(
            rf"^#define\s+{re.escape(name)}\s+UINT32_C\(([0-9]+)\)\s*$",
            value,
            name,
        )
    )


def _require_exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise StateBundleError(
            f"{name} keys changed: missing={sorted(expected - set(value))}, "
            f"unexpected={sorted(set(value) - expected)}"
        )


def _require_all_false(value: Any, expected: set[str], name: str) -> dict[str, bool]:
    if type(value) is not dict:
        raise StateBundleError(f"{name} must be an object")
    _require_exact_keys(value, expected, name)
    for key in sorted(expected):
        if value[key] is not False:
            raise StateBundleError(f"{name}.{key} must remain exactly false")
    return value


def _yaml_claim_policy(root: Path) -> dict[str, bool]:
    text = _text(root, CAPABILITIES_PATH)
    body = _one(
        r"^claim_policy:\s*$\n(.*?)(?=^capabilities:\s*$)",
        text,
        "capability claim_policy",
        re.MULTILINE | re.DOTALL,
    )
    rows = re.findall(r"^  ([a-z0-9_]+): (true|false)\s*$", body, re.MULTILINE)
    if not rows or len(rows) != len({key for key, _value in rows}):
        raise StateBundleError("capability claim_policy is duplicate or malformed")
    return {key: raw == "true" for key, raw in rows}


def _verify_authority(root: Path) -> dict[str, Any]:
    authority = _load_json(root, AUTHORITY_PATH)
    _require_exact_keys(
        authority,
        {
            "schema_id",
            "engine_id",
            "policy_id",
            "execution_authority",
            "claim_authority",
            "qualification_guard",
            "operational_blockers",
            "unresolved_operational_decisions",
        },
        "authority state",
    )
    if authority["schema_id"] != AUTHORITY_SCHEMA_ID:
        raise StateBundleError("authority schema changed")
    if authority["engine_id"] != ENGINE_ID:
        raise StateBundleError("authority engine changed")
    if authority["policy_id"] != "manual_fail_closed_successor_schema_only":
        raise StateBundleError("authority policy changed")
    execution = _require_all_false(
        authority["execution_authority"],
        EXPECTED_EXECUTION_FIELDS,
        "execution_authority",
    )
    claims = _require_all_false(
        authority["claim_authority"], EXPECTED_CLAIM_FIELDS, "claim_authority"
    )
    if authority["qualification_guard"] != EXPECTED_QUALIFICATION_GUARD:
        raise StateBundleError("qualification guard changed")
    if authority["operational_blockers"] != EXPECTED_BLOCKERS:
        raise StateBundleError("operational blocker set or order changed")
    if authority["unresolved_operational_decisions"] != 32:
        raise StateBundleError("unresolved operational decision count changed")

    capability_claims = _yaml_claim_policy(root)
    expected_capability_claims = {
        "customer_execution_enabled": execution["customer_execution_enabled"],
        **claims,
    }
    if capability_claims != expected_capability_claims:
        raise StateBundleError("capability claim policy and authority state differ")

    operations = _load_json(root, OPERATIONS_DECISION_PATH)
    if operations.get("operational_blockers") != EXPECTED_BLOCKERS:
        raise StateBundleError("operations decision blockers differ")
    unresolved = operations.get("unresolved_fields")
    if type(unresolved) is not list or len(unresolved) != 32 or len(set(unresolved)) != 32:
        raise StateBundleError("operations decision must retain 32 unique unresolved fields")
    if operations.get("operations_decision_ready") is not False:
        raise StateBundleError("operations decision must remain unresolved")
    _require_all_false(
        operations.get("authority"),
        EXPECTED_OPERATIONS_AUTHORITY_FIELDS,
        "operations authority",
    )
    qualification = operations.get("qualification")
    if type(qualification) is not dict or qualification != {
        "independent_review_complete": False,
        "provider_qualification_complete": False,
        "qualification_receipt_sha256": None,
    }:
        raise StateBundleError("operations qualification changed")

    d1 = _load_json(root, D1_PROFILE_PATH)
    if d1.get("profile_id") != "engine_v2_d1_repeatable_development_v1":
        raise StateBundleError("D1 profile identity changed")
    _require_all_false(
        d1.get("authority"), EXPECTED_D1_AUTHORITY_FIELDS, "D1 authority"
    )
    development_policy = d1.get("development_policy")
    if type(development_policy) is not dict:
        raise StateBundleError("D1 development policy is missing")
    for key in (
        "fresh_holdout_overlap_allowed",
        "fresh_holdout_execution_allowed",
        "stage0_admission_allowed",
        "public_benchmark_claim_allowed",
        "scientific_claim_allowed",
        "product_promotion_allowed",
        "customer_pose_emission_allowed",
    ):
        if development_policy.get(key) is not False:
            raise StateBundleError(f"D1 {key} must remain false")

    stage0 = _text(root, STAGE0_STATUS_PATH)
    for marker in ("`BLIND_RUN_BLOCKED`", "| Fresh 128 executed | false |"):
        if marker not in stage0:
            raise StateBundleError(f"Stage 0 status is missing marker: {marker}")
    cpu_v7 = _text(root, CPU_V7_RESULT_PATH)
    for marker in ("terminal decision is `PASS`", "recorded_pass_non_authoritative"):
        if marker not in cpu_v7:
            raise StateBundleError(f"CPU-v7 result is missing marker: {marker}")
    return authority


def _abi_inventory(root: Path) -> dict[str, dict[str, Any]]:
    rust = _text(root, RUST_SYS_PATH)
    inventory: dict[str, dict[str, Any]] = {}
    for surface, (header_path, macro) in sorted(ABI_SURFACES.items()):
        canonical = _bytes(root, header_path)
        vendor_path = Path("rust/betelgeuze-sys/vendor") / header_path
        if canonical != _bytes(root, vendor_path):
            raise StateBundleError(f"canonical/vendor ABI header drift: {header_path}")
        header = canonical.decode("utf-8")
        major = _macro_integer(header, f"{macro}_MAJOR")
        minor = _macro_integer(header, f"{macro}_MINOR")
        if _macro_integer(header, macro) != major:
            raise StateBundleError(f"{surface} ABI compatibility number changed")
        rust_major = _rust_integer_constant(rust, f"{macro}_MAJOR")
        rust_minor = _rust_integer_constant(rust, f"{macro}_MINOR")
        rust_compatibility = _rust_integer_constant(rust, macro)
        if (rust_compatibility, rust_major, rust_minor) != (major, major, minor):
            raise StateBundleError(f"{surface} C/Rust ABI drift")
        inventory[surface] = {
            "header_path": header_path.as_posix(),
            "major": major,
            "minor": minor,
            "version": f"{major}.{minor}",
        }

    cmake = _text(root, ROOT_CMAKE_PATH)
    cmake_version = _one(
        r"^project\(betelgeuze_native_engine VERSION ([0-9]+\.[0-9]+\.[0-9]+) ",
        cmake,
        "native CMake project version",
    )
    if cmake_version != f"{inventory['core']['version']}.0":
        raise StateBundleError("CMake project version and core ABI differ")
    return inventory


def _sampling_inventory(root: Path) -> dict[str, Any]:
    profile = _load_json(root, SAMPLING_PROFILE_PATH)
    required = {
        "schema_id",
        "profile_id",
        "input_denominator",
        "output_denominator",
        "hard_minimum_vdw_ratio",
        "maximum_pocket_escape_angstrom",
        "quality_prefilter_multiplier",
        "duplicate_policy",
        "lane_order",
        "lane_quotas",
        "authority",
    }
    _require_exact_keys(profile, required, "sampling profile")
    if profile["schema_id"] != "betelgeuze.engine_v2_sampling_funnel_profile/1.1.0":
        raise StateBundleError("sampling profile schema changed")
    if profile["profile_id"] != "engine_v2_deterministic_512_to_64_funnel_v1":
        raise StateBundleError("sampling profile identity changed")
    if profile["input_denominator"] != 512 or profile["output_denominator"] != 64:
        raise StateBundleError("sampling denominator changed")
    lane_order = profile["lane_order"]
    quotas = profile["lane_quotas"]
    if (
        type(lane_order) is not list
        or lane_order != ["uniform_so3", "pocket_surface", "single_anchor", "multi_anchor"]
        or type(quotas) is not dict
        or quotas
        != {
            "uniform_so3": 24,
            "pocket_surface": 16,
            "single_anchor": 16,
            "multi_anchor": 8,
        }
        or list(quotas) != lane_order
    ):
        raise StateBundleError("sampling lane order or quota changed")
    if (
        profile["hard_minimum_vdw_ratio"] != 0.55
        or profile["maximum_pocket_escape_angstrom"] != 4.0
        or profile["quality_prefilter_multiplier"] != 4
        or profile["duplicate_policy"]
        != "global_coordinate_sha256_first_pool_index"
    ):
        raise StateBundleError("sampling selection policy changed")
    _require_all_false(
        profile["authority"],
        EXPECTED_SAMPLING_AUTHORITY_FIELDS,
        "sampling authority",
    )

    pool = _text(root, SAMPLING_POOL_PATH)
    funnel = _text(root, SAMPLING_FUNNEL_PATH)
    pool_profile = _rust_string_constant(pool, "NATIVE_SAMPLING_POOL_PROFILE_ID")
    lane_denominator = _rust_integer_constant(
        pool, "NATIVE_SAMPLING_POOL_LANE_DENOMINATOR"
    )
    funnel_profile = _rust_string_constant(
        funnel, "NATIVE_SAMPLING_FUNNEL_PROFILE_ID"
    )
    input_denominator = _rust_integer_constant(
        funnel, "NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR"
    )
    output_denominator = _rust_integer_constant(
        funnel, "NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR"
    )
    profile_sha256 = hashlib.sha256(_canonical_compact_bytes(profile)).digest()
    rust_profile_sha256 = _rust_sha256_constant(
        funnel, "NATIVE_SAMPLING_FUNNEL_PROFILE_CANONICAL_SHA256"
    )
    if pool_profile != "engine_v2_source_bound_four_lane_512_producer_v1":
        raise StateBundleError("sampling-pool producer identity changed")
    if lane_denominator * len(lane_order) != input_denominator:
        raise StateBundleError("sampling-pool lane denominator changed")
    if (funnel_profile, input_denominator, output_denominator) != (
        profile["profile_id"],
        profile["input_denominator"],
        profile["output_denominator"],
    ):
        raise StateBundleError("Rust sampling funnel and profile differ")
    rust_selection_policy = (
        _rust_float_constant(funnel, "NATIVE_SAMPLING_FUNNEL_HARD_MINIMUM_VDW_RATIO"),
        _rust_float_constant(
            funnel, "NATIVE_SAMPLING_FUNNEL_MAXIMUM_POCKET_ESCAPE_ANGSTROM"
        ),
        _rust_integer_constant(
            funnel, "NATIVE_SAMPLING_FUNNEL_QUALITY_PREFILTER_MULTIPLIER"
        ),
        _rust_string_constant(funnel, "NATIVE_SAMPLING_FUNNEL_DUPLICATE_POLICY"),
    )
    profile_selection_policy = (
        profile["hard_minimum_vdw_ratio"],
        profile["maximum_pocket_escape_angstrom"],
        profile["quality_prefilter_multiplier"],
        profile["duplicate_policy"],
    )
    if rust_profile_sha256 != profile_sha256:
        raise StateBundleError("Rust sampling profile hash and canonical profile differ")
    if rust_selection_policy != profile_selection_policy:
        raise StateBundleError("Rust sampling selection policy and profile differ")
    for marker in (
        "Deterministic, result-independent 512-to-64 proposal selection.",
        "Select exactly 64 result-independent rows from an exact 512-row pool.",
        'Self::UniformSo3 => "uniform_so3"',
        'Self::PocketSurface => "pocket_surface"',
        'Self::SingleAnchor => "single_anchor"',
        'Self::MultiAnchor => "multi_anchor"',
        "Self::UniformSo3 => 24",
        "Self::PocketSurface | Self::SingleAnchor => 16",
        "Self::MultiAnchor => 8",
    ):
        if funnel.count(marker) != 1:
            raise StateBundleError(f"Rust sampling lane policy changed: {marker}")
    return {
        "source_pool_profile_id": pool_profile,
        "source_pool_lane_denominator": lane_denominator,
        "funnel_profile_id": funnel_profile,
        "input_denominator": input_denominator,
        "output_denominator": output_denominator,
        "lane_order": lane_order,
        "lane_quotas": quotas,
        "result_dependent_selection": False,
        "profile_path": SAMPLING_PROFILE_PATH.as_posix(),
        "profile_sha256": _sha256_path(root, SAMPLING_PROFILE_PATH),
    }


def _docking_inventory(root: Path) -> dict[str, Any]:
    rust_sys = _text(root, RUST_SYS_PATH)
    core_header = _text(root, ABI_SURFACES["core"][0])
    fixed64 = _text(root, FIXED64_PATH)
    scorer = _text(root, SCORER_PATH)
    pipeline = _text(root, PIPELINE_TYPES_PATH)
    candidate_count = _macro_integer(
        core_header, "BG_DOCKING_FIXED64_CANDIDATE_COUNT"
    )
    term_count = _macro_integer(core_header, "BG_DOCKING_SCORER_V1_TERM_COUNT")
    if _rust_integer_constant(
        rust_sys, "BG_DOCKING_FIXED64_CANDIDATE_COUNT"
    ) != candidate_count or _rust_integer_constant(
        fixed64, "FIXED64_CANDIDATE_COUNT"
    ) != candidate_count:
        raise StateBundleError("fixed64 denominator differs across C/Rust surfaces")
    if _rust_integer_constant(rust_sys, "BG_DOCKING_SCORER_V1_TERM_COUNT") != term_count:
        raise StateBundleError("ScorerV1 term count differs across C/Rust surfaces")
    scorer_weight_counts = re.findall(r"weights:\s*\[f64;\s*([0-9]+)\]", scorer)
    if not scorer_weight_counts or set(scorer_weight_counts) != {str(term_count)}:
        raise StateBundleError("ScorerV1 Rust weight count changed")
    return {
        "candidate_denominator": candidate_count,
        "pipeline_profile_id": _rust_string_constant(
            pipeline, "FIXED64_NATIVE_PIPELINE_PROFILE_ID"
        ),
        "scorer": {
            "score_id": _rust_string_constant(scorer, "NATIVE_SCORER_V1_SCORE_ID"),
            "algorithm_id": _rust_string_constant(
                scorer, "NATIVE_SCORER_V1_ALGORITHM_ID"
            ),
            "term_count": term_count,
        },
        "sampling": _sampling_inventory(root),
    }


_CMAKE_ARGUMENT_RE = re.compile(r'"([^"]*)"|([^\s]+)')


def _cmake_arguments(body: str) -> list[str]:
    return [quoted or bare for quoted, bare in _CMAKE_ARGUMENT_RE.findall(body)]


def _strip_cmake_comments(value: str) -> str:
    output = []
    index = 0
    quoted = False
    while index < len(value):
        character = value[index]
        following = value[index + 1] if index + 1 < len(value) else ""
        if quoted:
            output.append(character)
            if character == "\\" and following:
                output.append(following)
                index += 2
                continue
            if character == '"':
                quoted = False
            index += 1
            continue
        if character == '"':
            quoted = True
            output.append(character)
            index += 1
            continue
        if character == "#":
            bracket = re.match(r"#\[(?P<equals>=*)\[", value[index:])
            if bracket is not None:
                terminator = f"]{bracket.group('equals')}]"
                end = value.find(terminator, index + len(bracket.group(0)))
                if end < 0:
                    raise StateBundleError("native CMake has an unterminated bracket comment")
                end += len(terminator)
                output.extend(
                    "\n" if item == "\n" else " " for item in value[index:end]
                )
                index = end
                continue
            while index < len(value) and value[index] != "\n":
                index += 1
            continue
        output.append(character)
        index += 1
    return "".join(output)


def _cmake_command_arguments(value: str, command: str) -> list[list[str]]:
    return [
        _cmake_arguments(body)
        for body in re.findall(
            rf"\b{re.escape(command)}\s*\((?P<body>.*?)\)",
            value,
            flags=re.DOTALL | re.IGNORECASE,
        )
    ]


def _validate_rust_cpu_cmake_closure(
    root: Path, root_cmake: str, native_cmake: str
) -> None:
    root_cmake = _strip_cmake_comments(root_cmake)
    native_cmake = _strip_cmake_comments(native_cmake)
    root_includes = _cmake_command_arguments(root_cmake, "include")
    root_subdirectories = _cmake_command_arguments(root_cmake, "add_subdirectory")
    if root_includes != [["CTest"]] or root_subdirectories != [["native"]]:
        raise StateBundleError("root CMake native inclusion boundary changed")
    if re.search(r"\bbetelgeuze_engine\b|\bCARGO_EXECUTABLE\b", root_cmake):
        raise StateBundleError("root CMake must not mutate the native Rust provider")
    if re.search(
        r"(?<!target_)\binclude_directories\s*\(|"
        r"\b(?:INTERFACE_)?INCLUDE_DIRECTORIES\b|"
        r"\b(?:add_compile_options|add_definitions|link_directories)\s*\(|"
        r"\bCMAKE_(?:C|CXX)_FLAGS\b|\breturn\s*\(",
        root_cmake,
        flags=re.IGNORECASE,
    ):
        raise StateBundleError("root CMake build mutation is unsupported")

    for cmake_source in (root_cmake, native_cmake):
        for command in ("set", "unset"):
            for arguments in _cmake_command_arguments(cmake_source, command):
                if arguments and "$" in arguments[0]:
                    raise StateBundleError("dynamic CMake variable assignment is unsupported")
                if arguments and arguments[0] in {
                    "CARGO_EXECUTABLE",
                    "PROJECT_SOURCE_DIR",
                    "CMAKE_COMMAND",
                }:
                    raise StateBundleError("bound CMake variable reassignment is unsupported")

    if _cmake_command_arguments(native_cmake, "include") != [["GNUInstallDirs"]] or (
        _cmake_command_arguments(native_cmake, "add_subdirectory")
    ):
        raise StateBundleError("native CMake inclusion boundary changed")

    if re.search(
        r"(?<!target_)\binclude_directories\s*\(",
        native_cmake,
        flags=re.IGNORECASE,
    ) or re.search(
        r"\b(?:INTERFACE_)?INCLUDE_DIRECTORIES\b",
        native_cmake,
        flags=re.IGNORECASE,
    ):
        raise StateBundleError("directory-level native include paths are unsupported")
    target_source_blocks = _cmake_command_arguments(native_cmake, "target_sources")
    if any(arguments and arguments[0] == "betelgeuze_engine" for arguments in target_source_blocks):
        raise StateBundleError("incremental native engine source mutation is unsupported")

    engine_libraries = [
        arguments
        for arguments in _cmake_command_arguments(native_cmake, "add_library")
        if arguments and arguments[0] == "betelgeuze_engine"
    ]
    if (
        len(engine_libraries) != 1
        or len(engine_libraries[0]) < 3
        or engine_libraries[0][1] != "SHARED"
        or engine_libraries[0].count(RUST_CPU_BACKEND_PATH.relative_to("native").as_posix())
        != 1
    ):
        raise StateBundleError("native engine Rust bridge source binding changed")

    cargo_find_programs = [
        arguments
        for arguments in _cmake_command_arguments(native_cmake, "find_program")
        if arguments and arguments[0] == "CARGO_EXECUTABLE"
    ]
    if cargo_find_programs != [["CARGO_EXECUTABLE", "cargo", "REQUIRED"]] or len(
        re.findall(r"\bCARGO_EXECUTABLE\b", native_cmake)
    ) != 2:
        raise StateBundleError("Rust CPU Cargo executable binding changed")

    provider_start = re.search(
        r"\bfind_program\s*\(\s*CARGO_EXECUTABLE\b", native_cmake, re.IGNORECASE
    )
    provider_link_spans = [
        match
        for match in re.finditer(
            r"\btarget_link_libraries\s*\((?P<body>.*?)\)",
            native_cmake,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if _cmake_arguments(match.group("body"))
        == ["betelgeuze_engine", "PRIVATE", "betelgeuze_rust_cpu_provider"]
    ]
    if provider_start is None or len(provider_link_spans) != 1:
        raise StateBundleError("Rust CPU provider control-flow boundary changed")
    provider_region = native_cmake[: provider_link_spans[0].end()]
    if (
        _cmake_command_arguments(provider_region, "if")
        != [["BG_ENABLE_HIP"], ["WIN32"]]
        or _cmake_command_arguments(provider_region, "else") != [[], []]
        or _cmake_command_arguments(provider_region, "endif") != [[], []]
        or re.search(
            r"\b(?:return|foreach|while|function|macro|block|include|add_subdirectory|"
            r"cmake_language)\s*\(",
            provider_region,
            flags=re.IGNORECASE,
        )
    ):
        raise StateBundleError("Rust CPU provider commands must remain active at top level")

    include_blocks = re.findall(
        r"target_include_directories\s*\(\s*betelgeuze_engine\s+(?P<body>.*?)\)",
        native_cmake,
        flags=re.DOTALL,
    )
    expected_include_arguments = (
        "PUBLIC",
        "$<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>",
        "$<INSTALL_INTERFACE:include>",
        "PRIVATE",
        "${CMAKE_CURRENT_SOURCE_DIR}/src",
    )
    if len(include_blocks) != 1 or tuple(
        _cmake_arguments(include_blocks[0])
    ) != expected_include_arguments:
        raise StateBundleError("native include search path order changed")
    if len(re.findall(r"\bBG_RUST_CPU_SOURCES\b", native_cmake)) != 2:
        raise StateBundleError("Rust CPU CMake source variable usage changed")
    glob_blocks = re.findall(
        r"file\s*\(\s*GLOB_RECURSE\s+BG_RUST_CPU_SOURCES\s+"
        r"CONFIGURE_DEPENDS(?P<body>.*?)\)",
        native_cmake,
        flags=re.DOTALL,
    )
    if len(glob_blocks) != 1:
        raise StateBundleError("Rust CPU CMake source glob block changed")
    actual_globs = _cmake_arguments(glob_blocks[0])
    expected_globs = [
        f"${{PROJECT_SOURCE_DIR}}/{directory.as_posix()}/*.rs"
        for directory in rust_cpu_provider_source_directories(root)
    ]
    if sorted(actual_globs) != sorted(expected_globs):
        raise StateBundleError(
            "Rust CPU CMake source globs differ from Cargo path closure: "
            f"expected={sorted(expected_globs)}, actual={sorted(actual_globs)}"
        )

    command_blocks = re.findall(
        r"add_custom_command\s*\((?P<body>.*?)\)",
        native_cmake,
        flags=re.DOTALL | re.IGNORECASE,
    )
    rust_blocks = [
        block for block in command_blocks if 'OUTPUT "${BG_RUST_CPU_STATIC_LIBRARY}"' in block
    ]
    if len(rust_blocks) != 1:
        raise StateBundleError("Rust CPU Cargo custom command block changed")
    entry_manifest = _load_toml(root, RUST_CPU_CRATE_MANIFEST_PATH)
    package = entry_manifest.get("package")
    library = entry_manifest.get("lib")
    if type(package) is not dict or package.get("name") != "betelgeuze-cpu-kernel":
        raise StateBundleError("Rust CPU entry package name changed")
    if type(library) is not dict or library.get("crate-type") != ["rlib", "staticlib"]:
        raise StateBundleError("Rust CPU entry package must produce the static provider")
    manifests = rust_cpu_provider_crate_manifest_paths(root)
    dependency_manifests = tuple(
        manifest for manifest in manifests if manifest != RUST_CPU_CRATE_MANIFEST_PATH
    )
    expected_dependencies = (
        *RUST_CPU_PROVIDER_CONTROL_PATHS,
        RUST_CPU_CRATE_MANIFEST_PATH,
        *dependency_manifests,
        *rust_cpu_provider_literal_input_paths(root),
    )
    expected_custom_command = (
        "OUTPUT",
        "${BG_RUST_CPU_STATIC_LIBRARY}",
        "COMMAND",
        "${CMAKE_COMMAND}",
        "-E",
        "env",
        "CARGO_TARGET_DIR=${BG_RUST_CPU_TARGET_DIR}",
        "RUSTFLAGS=-C target-feature=-fma -C relocation-model=pic",
        "${CARGO_EXECUTABLE}",
        "build",
        "--manifest-path",
        "${PROJECT_SOURCE_DIR}/rust/Cargo.toml",
        "--package",
        "betelgeuze-cpu-kernel",
        "--release",
        "--locked",
        "DEPENDS",
        *(f"${{PROJECT_SOURCE_DIR}}/{path.as_posix()}" for path in expected_dependencies),
        "${BG_RUST_CPU_SOURCES}",
        "COMMENT",
        "Building deterministic Rust CPU provider",
        "VERBATIM",
    )
    actual_custom_command = tuple(_cmake_arguments(rust_blocks[0]))
    if actual_custom_command != expected_custom_command:
        raise StateBundleError(
            "Rust CPU Cargo command or dependencies differ from the bound build: "
            f"expected={expected_custom_command}, actual={actual_custom_command}"
        )

    provider_declarations = [
        arguments
        for arguments in _cmake_command_arguments(native_cmake, "add_library")
        if arguments and arguments[0] == "betelgeuze_rust_cpu_provider"
    ]
    if provider_declarations != [
        ["betelgeuze_rust_cpu_provider", "STATIC", "IMPORTED", "GLOBAL"]
    ]:
        raise StateBundleError("Rust CPU imported provider declaration changed")
    provider_custom_targets = [
        arguments
        for arguments in _cmake_command_arguments(native_cmake, "add_custom_target")
        if arguments and arguments[0] == "betelgeuze_rust_cpu_provider_build"
    ]
    if provider_custom_targets != [
        [
            "betelgeuze_rust_cpu_provider_build",
            "DEPENDS",
            "${BG_RUST_CPU_STATIC_LIBRARY}",
        ]
    ]:
        raise StateBundleError("Rust CPU provider build target changed")
    provider_properties = [
        arguments
        for arguments in _cmake_command_arguments(native_cmake, "set_target_properties")
        if arguments and arguments[0] == "betelgeuze_rust_cpu_provider"
    ]
    if provider_properties != [
        [
            "betelgeuze_rust_cpu_provider",
            "PROPERTIES",
            "IMPORTED_LOCATION",
            "${BG_RUST_CPU_STATIC_LIBRARY}",
        ]
    ]:
        raise StateBundleError("Rust CPU imported provider location changed")
    dependency_bindings = _cmake_command_arguments(native_cmake, "add_dependencies")
    for expected in (
        [
            "betelgeuze_rust_cpu_provider",
            "betelgeuze_rust_cpu_provider_build",
        ],
        ["betelgeuze_engine", "betelgeuze_rust_cpu_provider_build"],
    ):
        if dependency_bindings.count(expected) != 1:
            raise StateBundleError("Rust CPU provider dependency binding changed")
    provider_links = _cmake_command_arguments(native_cmake, "target_link_libraries")
    expected_provider_link = [
        "betelgeuze_engine",
        "PRIVATE",
        "betelgeuze_rust_cpu_provider",
    ]
    if provider_links.count(expected_provider_link) != 1:
        raise StateBundleError("Rust CPU provider link binding changed")


def _backend_inventory(root: Path) -> dict[str, Any]:
    root_cmake = _text(root, ROOT_CMAKE_PATH)
    native_cmake = _text(root, NATIVE_CMAKE_PATH)
    if 'option(BG_ENABLE_HIP "Build the native ROCm/HIP compute backend" OFF)' not in root_cmake:
        raise StateBundleError("HIP-fast build default changed")
    if 'set(BG_ENABLE_HIP_SAFE "AUTO" CACHE STRING' not in native_cmake:
        raise StateBundleError("HIP-safe build default changed")
    for marker in ("BG_RUST_CPU_STATIC_LIBRARY", "betelgeuze_cpu_kernel"):
        if marker not in native_cmake:
            raise StateBundleError(f"Rust CPU build marker missing: {marker}")
    _validate_rust_cpu_cmake_closure(root, root_cmake, native_cmake)
    for path in (HIP_SAFE_WRAPPER_PATH, HIP_SAFE_PROVIDER_PATH, HIP_FAST_BACKEND_PATH):
        if path.relative_to("native").as_posix() not in native_cmake:
            raise StateBundleError(f"HIP build source marker missing: {path}")
    rust_cpu_source_paths = tuple(
        sorted(
            {
                *rust_cpu_bridge_source_paths(root),
                *rust_cpu_provider_source_paths(root),
            },
            key=lambda value: value.as_posix(),
        )
    )
    return {
        "cpp_cpu_reference": {
            "implementation_state": "repository_source_implemented",
            "source_path": CPP_CPU_BACKEND_PATH.as_posix(),
        },
        "rust_cpu": {
            "implementation_state": "repository_source_and_build_surface_declared",
            "binary_provenance_evaluated": False,
            "build_path": NATIVE_CMAKE_PATH.as_posix(),
            "source_inventory_scope": (
                "declared_rust_provider_and_native_bridge_inputs"
            ),
            "source_paths": [path.as_posix() for path in rust_cpu_source_paths],
        },
        "hip_safe": {
            "configuration_default": "AUTO",
            "implementation_state": "conditional_build_implemented",
            "source_paths": [
                HIP_SAFE_WRAPPER_PATH.as_posix(),
                HIP_SAFE_PROVIDER_PATH.as_posix(),
            ],
        },
        "hip_fast": {
            "configuration_default": "OFF",
            "implementation_state": "conditional_build_implemented",
            "source_path": HIP_FAST_BACKEND_PATH.as_posix(),
        },
    }


def _comparator_inventory(root: Path) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for engine, path, marker in (
        ("vina", VINA_ADAPTER_PATH, "def run_vina("),
        ("gnina", GNINA_ADAPTER_PATH, "def run_gnina("),
    ):
        text = _text(root, path)
        if marker not in text or 'SCORING_MODE = "vina"' not in text:
            raise StateBundleError(f"{engine} repository adapter contract changed")
        output[engine] = {
            "adapter_path": path.as_posix(),
            "repository_adapter_implemented": True,
            "runtime_availability": "not_evaluated_by_state_generator",
        }
    return output


def _optional_repository_file(root: Path, relative: Path) -> dict[str, Any]:
    candidate = root / relative
    symlink = _symlink_component(root, relative)
    if symlink is not None:
        raise StateBundleError(
            f"D1 repository output must not use a symlink: {relative} ({symlink})"
        )
    if not candidate.exists():
        return {"path": relative.as_posix(), "present": False, "sha256": None}
    if not candidate.is_file():
        raise StateBundleError(f"D1 repository output must be a file: {relative}")
    return {
        "path": relative.as_posix(),
        "present": True,
        "sha256": _sha256_bytes(_bytes(root, relative)),
    }


def _d1_inventory(root: Path) -> dict[str, Any]:
    profile = _load_json(root, D1_PROFILE_PATH)
    if (
        profile.get("schema_id")
        != "betelgeuze.engine_v2_d1_development_profile/1.0.0"
        or profile.get("profile_id") != "engine_v2_d1_repeatable_development_v1"
        or profile.get("case_count") != 32
        or profile.get("candidate_denominator") != 64
    ):
        raise StateBundleError("D1 development profile changed")
    outputs = [_optional_repository_file(root, path) for path in D1_REPOSITORY_OUTPUTS]
    present_count = sum(row["present"] is True for row in outputs)
    return {
        "contract_implemented": True,
        "profile_id": profile["profile_id"],
        "case_count": 32,
        "candidate_denominator": 64,
        "materializer_path": D1_MATERIALIZER_PATH.as_posix(),
        "runner_path": D1_RUNNER_PATH.as_posix(),
        "verifier_path": D1_VERIFIER_PATH.as_posix(),
        "repository_outputs": outputs,
        "repository_output_present_count": present_count,
        "all_repository_output_paths_present": present_count == len(outputs),
        "repository_output_semantic_validation": "not_evaluated_by_state_generator",
    }


def _source_inputs(root: Path) -> list[dict[str, str]]:
    return [
        {"path": path.as_posix(), "sha256": _sha256_path(root, path)}
        for path in implementation_source_paths(root)
    ]


def _validate_sha(value: str, name: str) -> str:
    if _SHA40_RE.fullmatch(value) is None:
        raise StateBundleError(f"{name} must be a lowercase 40-hex Git SHA")
    return value


def _git_output(root: Path, arguments: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StateBundleError(f"git {' '.join(arguments)} failed") from exc
    return result.stdout.strip()


def git_source_identity(root: Path) -> tuple[str, str]:
    dirty = _git_output(root, ["status", "--porcelain=v1", "--untracked-files=normal"])
    if dirty:
        raise StateBundleError("automatic source identity requires a clean checkout")
    return (
        _validate_sha(_git_output(root, ["rev-parse", "HEAD"]), "source commit"),
        _validate_sha(
            _git_output(root, ["rev-parse", "HEAD^{tree}"]), "source tree"
        ),
    )


def explicit_git_source_identity(
    root: Path, source_commit: str, source_tree: str
) -> tuple[str, str]:
    source_commit = _validate_sha(source_commit, "source commit")
    source_tree = _validate_sha(source_tree, "source tree")
    top_level = Path(_git_output(root, ["rev-parse", "--show-toplevel"])).resolve()
    if top_level != root:
        raise StateBundleError("repository root must be the Git top level")
    _require_running_generator(root)
    dirty = _git_output(root, ["status", "--porcelain=v1", "--untracked-files=normal"])
    if dirty:
        raise StateBundleError("explicit source identity requires a clean checkout")
    actual_commit = _validate_sha(_git_output(root, ["rev-parse", "HEAD"]), "HEAD")
    actual_tree = _validate_sha(
        _git_output(root, ["rev-parse", "HEAD^{tree}"]), "HEAD tree"
    )
    if source_commit != actual_commit:
        raise StateBundleError("explicit source commit does not match checkout HEAD")
    if source_tree != actual_tree:
        raise StateBundleError("explicit source tree does not match checkout HEAD tree")
    tracked_paths = set(
        _git_output(root, ["ls-tree", "-r", "--name-only", "HEAD"]).splitlines()
    )
    rust_source_directories = rust_cpu_provider_source_directories(root)
    rust_crate_manifests = rust_cpu_provider_crate_manifest_paths(root)
    rust_build_scripts = {manifest.parent / "build.rs" for manifest in rust_crate_manifests}
    tracked_rust_source_paths = {
        Path(relative)
        for relative in tracked_paths
        if (
            relative.endswith(".rs")
            and any(
                relative.startswith(f"{directory.as_posix()}/")
                for directory in rust_source_directories
            )
        )
        or Path(relative) in rust_build_scripts
    }
    worktree_rust_source_paths = set(rust_cpu_provider_source_paths(root)) - (
        set(RUST_CPU_PROVIDER_CONTROL_PATHS) | set(rust_crate_manifests)
    )
    discovered_literal_inputs = worktree_rust_source_paths - {
        path
        for path in worktree_rust_source_paths
        if path in rust_build_scripts
        or any(
            path.suffix == ".rs"
            and path.as_posix().startswith(f"{directory.as_posix()}/")
            for directory in rust_source_directories
        )
    }
    expected_rust_source_paths = tracked_rust_source_paths | discovered_literal_inputs
    if worktree_rust_source_paths != expected_rust_source_paths:
        missing = sorted(
            path.as_posix()
            for path in expected_rust_source_paths - worktree_rust_source_paths
        )
        extra = sorted(
            path.as_posix()
            for path in worktree_rust_source_paths - expected_rust_source_paths
        )
        raise StateBundleError(
            "Rust CPU provider source closure differs from HEAD: "
            f"missing={missing}, extra={extra}"
        )
    required_paths = verified_required_paths(root)
    missing_required = [
        path.as_posix()
        for path in required_paths
        if path.as_posix() not in tracked_paths
    ]
    if missing_required:
        raise StateBundleError(
            f"verified source inputs are not tracked by HEAD: {missing_required}"
        )
    unavailable_required = [
        path.as_posix()
        for path in required_paths
        if not _is_regular_repository_file(root, path)
    ]
    if unavailable_required:
        raise StateBundleError(
            "verified source inputs are unavailable as regular files: "
            f"{unavailable_required}"
        )
    untracked_optional = [
        path.as_posix()
        for path in D1_REPOSITORY_OUTPUTS
        if (
            (root / path).exists()
            or (root / path).is_symlink()
            or _symlink_component(root, path) is not None
        )
        and path.as_posix() not in tracked_paths
    ]
    if untracked_optional:
        raise StateBundleError(
            f"optional D1 inputs are not tracked by HEAD: {untracked_optional}"
        )
    unavailable_tracked_optional = [
        path.as_posix()
        for path in D1_REPOSITORY_OUTPUTS
        if path.as_posix() in tracked_paths
        and not _is_regular_repository_file(root, path)
    ]
    if unavailable_tracked_optional:
        raise StateBundleError(
            "tracked optional D1 inputs are unavailable as regular files: "
            f"{unavailable_tracked_optional}"
        )
    consumed_paths = list(required_paths) + [
        path for path in D1_REPOSITORY_OUTPUTS if path.as_posix() in tracked_paths
    ]
    mismatched_blobs = []
    for path in consumed_paths:
        relative = path.as_posix()
        expected_blob = _git_output(root, ["rev-parse", f"HEAD:{relative}"])
        worktree_blob = _git_output(
            root, ["hash-object", "--no-filters", "--", relative]
        )
        if worktree_blob != expected_blob:
            mismatched_blobs.append(relative)
    if mismatched_blobs:
        raise StateBundleError(
            f"consumed worktree files differ from HEAD blobs: {mismatched_blobs}"
        )
    return source_commit, source_tree


def build_bundle(
    root: Path,
    *,
    source_commit: str,
    source_tree: str,
    source_binding: str = "verified_git_checkout",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    source_commit = _validate_sha(source_commit, "source commit")
    source_tree = _validate_sha(source_tree, "source tree")
    if source_binding == "verified_git_checkout":
        explicit_git_source_identity(root, source_commit, source_tree)
    elif source_binding != "unverified_fixture":
        raise StateBundleError("source binding mode is invalid")
    authority = _verify_authority(root)
    python_name, python_version = _toml_project(root, PYTHON_PACKAGE_PATH)
    native_name, native_version = _toml_project(root, NATIVE_PACKAGE_PATH)
    python_project = _text(root, PYTHON_PACKAGE_PATH)
    required_native_version = _one(
        r'"betelgeuze-engine-v2-native==([^;"\n]+);',
        python_project,
        "Python native dependency version",
    )
    if (python_name, native_name) != (
        "betelgeuze-engine-v2",
        "betelgeuze-engine-v2-native",
    ):
        raise StateBundleError("Engine V2 distribution name changed")
    if required_native_version != native_version:
        raise StateBundleError("Python native dependency and native package version differ")

    implementation: dict[str, Any] = {
        "schema_id": IMPLEMENTATION_SCHEMA_ID,
        "engine_id": ENGINE_ID,
        "source_identity": {
            "binding": source_binding,
            "commit_sha": source_commit,
            "tree_sha": source_tree,
        },
        "packages": {
            "python_distribution": {
                "name": python_name,
                "version": python_version,
                "source_path": PYTHON_PACKAGE_PATH.as_posix(),
                "required_native_distribution_version": required_native_version,
            },
            "native_distribution": {
                "name": native_name,
                "version": native_version,
                "source_path": NATIVE_PACKAGE_PATH.as_posix(),
            },
            "version_surfaces_independent": True,
        },
        "public_abis": _abi_inventory(root),
        "docking": _docking_inventory(root),
        "backends": _backend_inventory(root),
        "external_comparators": _comparator_inventory(root),
        "d1_development": _d1_inventory(root),
        "source_inputs": _source_inputs(root),
    }
    implementation_bytes = _canonical_bytes(implementation)
    authority_bytes = _canonical_bytes(authority)
    release: dict[str, Any] = {
        "schema_id": RELEASE_SCHEMA_ID,
        "engine_id": ENGINE_ID,
        "release_status": (
            "unreleased_source_snapshot"
            if source_binding == "verified_git_checkout"
            else "unreleased_unverified_fixture"
        ),
        "release_id": None,
        "source_identity": {
            "binding": source_binding,
            "commit_sha": source_commit,
            "tree_sha": source_tree,
        },
        "state_documents": {
            "implementation": {
                "file_name": "engine_v2_implementation_state_v1.json",
                "schema_id": IMPLEMENTATION_SCHEMA_ID,
                "sha256": _sha256_bytes(implementation_bytes),
            },
            "authority": {
                "file_name": "engine_v2_authority_state_v1.json",
                "schema_id": AUTHORITY_SCHEMA_ID,
                "sha256": _sha256_bytes(authority_bytes),
            },
        },
        "artifacts": [],
        "release_authorized": False,
        "claim_authority_granted": False,
    }
    _canonical_bytes(release)
    return implementation, authority, release


def write_bundle(
    output_dir: Path,
    implementation: dict[str, Any],
    authority: dict[str, Any],
    release: dict[str, Any],
) -> dict[str, str]:
    output_dir = output_dir.resolve()
    if output_dir.exists() or output_dir.is_symlink():
        raise StateBundleError("output directory must be absent")
    parent = output_dir.parent
    if not parent.is_dir():
        raise StateBundleError("output directory parent must exist")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=parent))
    try:
        os.chmod(temporary, 0o700)
        documents = {
            "engine_v2_implementation_state_v1.json": _canonical_bytes(
                implementation
            ),
            "engine_v2_authority_state_v1.json": _canonical_bytes(authority),
            "engine_v2_release_manifest_v1.json": _canonical_bytes(release),
        }
        for name, data in documents.items():
            (temporary / name).write_bytes(data)
        if output_dir.exists() or output_dir.is_symlink():
            raise StateBundleError("output directory appeared during generation")
        temporary.rename(output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {name: _sha256_bytes(data) for name, data in sorted(documents.items())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--source-tree")
    args = parser.parse_args()
    try:
        if (args.source_commit is None) != (args.source_tree is None):
            raise StateBundleError(
                "--source-commit and --source-tree must be supplied together"
            )
        if args.source_commit is None:
            source_commit, source_tree = git_source_identity(args.root.resolve())
        else:
            source_commit, source_tree = explicit_git_source_identity(
                args.root.resolve(), args.source_commit, args.source_tree
            )
        implementation, authority, release = build_bundle(
            args.root,
            source_commit=source_commit,
            source_tree=source_tree,
        )
        hashes = write_bundle(
            args.output_dir, implementation, authority, release
        )
    except StateBundleError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "source_commit": source_commit,
                "source_tree": source_tree,
                "output_dir": str(args.output_dir.resolve()),
                "document_sha256": hashes,
                "release_authorized": False,
                "claim_authority_granted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
