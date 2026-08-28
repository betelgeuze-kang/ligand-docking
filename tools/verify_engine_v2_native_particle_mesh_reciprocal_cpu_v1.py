#!/usr/bin/env python3
"""Verify the immutable native particle-mesh reciprocal CPU v1 development evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1_sources.json"
)
REFERENCE_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_pme_reciprocal_reference_profile_v1.json"
)
REFERENCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_pme_reciprocal_reference_profile_v1_sources.json"
)
REFERENCE_SOURCE_RELATIVE_PATH = Path("rust/reference-pme/src/lib.rs")
REFERENCE_FFT_RELATIVE_PATH = Path("rust/reference-pme/src/fft.rs")
REFERENCE_FIXTURE_RELATIVE_PATH = Path(
    "rust/reference-pme/fixtures/pme_reciprocal_v1.tsv"
)
REFERENCE_LOCK_RELATIVE_PATH = Path("rust/reference-pme/Cargo.lock")
RUNTIME_FIXTURE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/tests/fixtures/particle_mesh_reciprocal_v1.tsv"
)

SCHEMA_ID = "betelgeuze.engine_v2_native_particle_mesh_reciprocal_cpu_profile/1.0.0"
PROFILE_ID = "engine_v2_native_particle_mesh_reciprocal_cpu_development_v1"
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_reciprocal_cpu_sources/1.0.0"
)
SOURCE_SCOPE = (
    "particle_mesh_reciprocal_v1_owned_sources_bindings_tests_and_parent_oracle_inputs"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

PUBLIC_SYMBOLS = (
    "bg_particle_mesh_reciprocal_abi_version",
    "bg_particle_mesh_reciprocal_abi_version_major",
    "bg_particle_mesh_reciprocal_abi_version_minor",
    "bg_particle_mesh_reciprocal_abi_version_string",
    "bg_particle_mesh_reciprocal_parameters_v1_init",
    "bg_particle_mesh_reciprocal_energy_v1_init",
    "bg_particle_mesh_reciprocal_force_soa_v1_init",
    "bg_particle_mesh_reciprocal_error_v1_init",
    "bg_particle_mesh_reciprocal_model_v1_create",
    "bg_particle_mesh_reciprocal_model_v1_destroy",
    "bg_particle_mesh_reciprocal_model_v1_get_atom_count",
    "bg_particle_mesh_reciprocal_model_v1_profile_id",
    "bg_context_evaluate_particle_mesh_reciprocal_v1",
)

PARENT_REFERENCE = {
    "cargo_lock_sha256": (
        "98d90148a16d2a7fc3f20b27a0cc9ab570c47759c2666ea7a9a0193067c94d80"
    ),
    "fft_sha256": (
        "e65c2a4f3837ae25ce32883671462120c6a2ac9af60c27bbe78e92d502c58c01"
    ),
    "fixture_sha256": (
        "669e4409ba56897061976c38fbf53985fb1f744e8e5b3613512b0f957951deef"
    ),
    "merge_commit": "ebbd7a20538cfd7516d9b53adb2e54c6de14bd97",
    "merge_tree": "2ae92801369c7e16147e07cbb16e19c062e52cc9",
    "observation_sha256": (
        "899845a391e23da253a5f0e2bdb5a78794ec7beb4dabee1f04726d6af1492144"
    ),
    "profile_path": REFERENCE_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "d867651e8d6ce0ec1ead0c0e22dc684b4a0b6247ee35f2bcc9e17105f4c244d3"
    ),
    "pull_request": 439,
    "reference_schema_id": "betelgeuze.reference_particle_mesh_reciprocal/1.0.0",
    "reviewed_head": "62d309c82aab9b4cfa45c4c3e6d11c93b3bd3786",
    "source_manifest_path": REFERENCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "da6d669c85d63236936ba1f1324937b90e7cf57cc6dd58b16ab7d43d6278b296"
    ),
    "source_sha256": (
        "9579d213ec47fc75f70dbb4df76ff951de4a51518dc9216233c663a3e43e53c4"
    ),
}

ABI_CONTRACT = {
    "abi_version": 1,
    "abi_version_major": 1,
    "abi_version_minor": 0,
    "abi_version_string": "1.0.0",
    "engine_abi_reserved_fields_repurposed": False,
    "engine_abi_version_changed": False,
    "error_code_minimum": 0,
    "error_code_maximum": 10,
    "export_version_node": "BETELGEUZE_PARTICLE_MESH_RECIPROCAL_1.0",
    "export_version_parent": "BETELGEUZE_ENGINE_1.21",
    "header": "include/betelgeuze/particle_mesh_reciprocal.h",
    "model_profile_id": "betelgeuze.native_particle_mesh_reciprocal/1.0.0",
    "separately_versioned_boundary": True,
}

IMPLEMENTATION_CONTRACT_BASE = {
    "cardinal_b_spline_order": 4,
    "cpp_cpu_reference_lane": True,
    "deep_copied_model_configuration": True,
    "full_pme_implemented": False,
    "particle_mesh_reciprocal_implemented": True,
    "external_md_engine_dependency": False,
    "fixed64_cpu_v7_qualification_invoked": False,
    "hip_device_implementation": False,
    "hip_to_cpu_fallback": False,
    "independent_parent_reference_linked_into_production": False,
    "real_self_pair_total_composition_implemented": False,
    "reference_direct_dft_linked_into_production": False,
    "rust_cpu_lane": True,
    "runtime_fixture_path": RUNTIME_FIXTURE_RELATIVE_PATH.as_posix(),
    "runtime_fixture_sha256": PARENT_REFERENCE["fixture_sha256"],
    "shared_runtime_dynamics_integrated": False,
    "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
}

VALIDATION_CONTRACT = {
    "c11_public_header_probe": True,
    "canonical_vendor_byte_identity": True,
    "cpp_and_rust_typed_error_and_underflow_classification_parity": True,
    "cpp_allocation_failure_is_untyped_out_of_memory": True,
    "cpp_cpu_frozen_fixture_against_parent_oracle": True,
    "cpp_cpu_same_input_bitwise_repeat": True,
    "cpp_rust_energy_and_force_mixed_tolerance": {
        "absolute_tolerance": 5e-12,
        "formula": (
            "abs(observed - expected) <= absolute_tolerance + "
            "relative_tolerance * max(abs(observed), abs(expected))"
        ),
        "relative_tolerance": 5e-12,
    },
    "cpp_struct_layout_probe": True,
    "create_out_model_alias_rejected_before_write": True,
    "create_output_storage_parameter_alias_rejected_before_write": True,
    "descriptor_initializer_transactionality": True,
    "energy_component_count": 1,
    "evaluation_failure_output_transactionality": True,
    "force_component_count": 12,
    "hip_backend_fails_closed_without_device_execution": True,
    "model_create_failure_returns_null_handle": True,
    "model_deep_copy_survives_caller_input_mutation": True,
    "model_configuration_ownership_source_guard": True,
    "mach_o_public_export_allowlist_enforced": True,
    "public_symbol_version_enforced": True,
    "raw_c_auto_backend_fails_closed_before_input_access": True,
    "required_null_input_clears_valid_typed_error": True,
    "required_null_alias_suppresses_typed_error_write": True,
    "rust_safe_abnormal_create_return_handle_guard": True,
    "rust_safe_model_single_owner_drop_contract": True,
    "rust_safe_model_send_sync_disabled": True,
    "rust_safe_runtime_both_cpu_lanes_against_parent_fixture": True,
    "rust_safe_runtime_energy_only_bit_identity": True,
    "rust_cpu_energy_only_skips_force_storage_and_accumulation": True,
    "rust_cpu_failure_diagnostics_statically_allocated": True,
    "rust_cpu_fallible_allocations_map_to_untyped_out_of_memory": True,
    "rust_safe_runtime_oom_diagnostics_use_borrowed_static_storage": True,
    "rust_safe_runtime_failure_recovery": True,
    "rust_safe_runtime_parent_fixture_byte_identity": True,
    "rust_safe_runtime_same_lane_bitwise_repeat": True,
    "rust_safe_runtime_temporary_model_drop_iterations": 32,
    "rust_safe_typed_error_mapping_complete": True,
    "rust_cpu_frozen_fixture_bit_identity_against_parent_oracle": True,
    "rust_cpu_same_input_bitwise_repeat": True,
    "rust_sys_raw_abi_binding": True,
    "rust_provider_aliases_checked_before_typed_error_write": True,
    "stale_typed_error_cleared_before_untyped_failure": True,
    "work_cap_rejected_before_mesh_allocation": True,
}

AUTHORITY_CONTRACT = {
    "acceleration_claim_authorized": False,
    "d1_d2_execution_authorized": False,
    "development_fixture_only": True,
    "fresh_holdout_execution_authorized": False,
    "historical_molecular_ab_execution_authorized": False,
    "hip_device_execution_authorized": False,
    "molecular_execution_authorized": False,
    "performance_claim_authorized": False,
    "product_authority": False,
    "public_benchmark_authorized": False,
    "qualification_authority": False,
    "reservation_authorized": False,
    "root_supervisor_install_authorized": False,
    "scientific_claim_authorized": False,
    "stage0_admission_authorized": False,
    "test_double_production_authority": False,
}

OPERATIONAL_BLOCKERS = (
    "external_reservation_endpoint_not_configured",
    "external_reservation_provider_not_operational",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
)
OPERATIONAL_BOUNDARY = {
    "blockers": list(OPERATIONAL_BLOCKERS),
    "unresolved_operational_decisions": 32,
}

# These files are direct build/binding inputs even when their names are shared
# with other native features.  The manifest is intentionally not a complete
# repository or linker transitive closure.
REQUIRED_SOURCE_PATHS = (
    Path(".github/workflows/ci-engine-v2-native-particle-mesh-reciprocal.yml"),
    Path(".github/workflows/ci-engine-v2-native-direct-ewald.yml"),
    Path(".github/workflows/ci-engine-v2-native-direct-ewald-composite.yml"),
    Path(
        ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics.yml"
    ),
    Path("CMakeLists.txt"),
    Path("docs/engine_v2_native_particle_mesh_reciprocal_cpu_v1.md"),
    Path("include/betelgeuze/particle_mesh_reciprocal.h"),
    Path("include/betelgeuze/engine.h"),
    Path("native/CMakeLists.txt"),
    Path("native/betelgeuze_engine.exports"),
    Path("native/betelgeuze_engine.map"),
    Path("native/src/context.cpp"),
    Path("native/src/internal.hpp"),
    Path("native/src/system.cpp"),
    Path("native/tests/check_exports.cmake"),
    Path("native/tests/particle_mesh_reciprocal.cpp"),
    Path("rust/Cargo.lock"),
    Path("rust/Cargo.toml"),
    Path("rust/betelgeuze-runtime/Cargo.toml"),
    Path("rust/betelgeuze-runtime/build.rs"),
    Path("rust/betelgeuze-runtime/src/particle_mesh_reciprocal.rs"),
    Path("rust/betelgeuze-runtime/src/lib.rs"),
    Path("rust/betelgeuze-runtime/tests/particle_mesh_reciprocal.rs"),
    RUNTIME_FIXTURE_RELATIVE_PATH,
    Path("rust/betelgeuze-sys/Cargo.toml"),
    Path("rust/betelgeuze-sys/abi/particle_mesh_reciprocal_header_c11.c"),
    Path("rust/betelgeuze-sys/abi/particle_mesh_reciprocal_layout_assertions.cpp"),
    Path("rust/betelgeuze-sys/build.rs"),
    Path("rust/betelgeuze-sys/src/lib.rs"),
    Path("rust/betelgeuze-sys/tests/layout.rs"),
    Path("rust/betelgeuze-sys/tests/raw_smoke.rs"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze/particle_mesh_reciprocal.h"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze/engine.h"),
    Path("rust/betelgeuze-sys/vendor/native/src/context.cpp"),
    Path("rust/betelgeuze-sys/vendor/native/src/internal.hpp"),
    Path("rust/betelgeuze-sys/vendor/native/src/system.cpp"),
    Path("rust/cpu-kernel/Cargo.toml"),
    Path("rust/cpu-kernel/src/particle_mesh_reciprocal.rs"),
    Path("rust/cpu-kernel/src/lib.rs"),
    Path("rust_engine_v2/Cargo.lock"),
    Path("rust_engine_v2/Cargo.toml"),
    REFERENCE_PROFILE_RELATIVE_PATH,
    REFERENCE_MANIFEST_RELATIVE_PATH,
    REFERENCE_SOURCE_RELATIVE_PATH,
    REFERENCE_FFT_RELATIVE_PATH,
    REFERENCE_FIXTURE_RELATIVE_PATH,
    REFERENCE_LOCK_RELATIVE_PATH,
    Path("tools/__init__.py"),
    Path("tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py"),
    Path("tools/verify_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py"),
    Path("tests/unit/test_engine_v2_native_direct_ewald_cpu_v1.py"),
    Path("tests/unit/test_engine_v2_native_direct_ewald_composite_v1.py"),
    Path(
        "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_v1.py"
    ),
    Path("tests/unit/test_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py"),
)

# New particle-mesh reciprocal-specific ABI probes, vendor copies, runtime bindings, and
# tests are discovered automatically. Descendant composite ABIs have their own
# evidence closures and must not become dependencies of this parent profile.
# Adding or removing a parent source makes ordinary verification fail until
# --refresh is explicitly run.
DISCOVERED_SOURCE_GLOBS = (
    "native/src/particle_mesh_reciprocal/**/*",
    "rust/betelgeuze-runtime/src/**/*particle_mesh_reciprocal*",
    "rust/betelgeuze-runtime/tests/**/*particle_mesh_reciprocal*",
    "rust/betelgeuze-sys/abi/**/*particle_mesh_reciprocal*",
    "rust/betelgeuze-sys/tests/**/*particle_mesh_reciprocal*",
    "rust/betelgeuze-sys/vendor/include/betelgeuze/particle_mesh_reciprocal.h",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/**/*",
)


class NativeParticleMeshReciprocalCPUProfileV1Error(ValueError):
    """The native particle-mesh reciprocal CPU v1 evidence failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeParticleMeshReciprocalCPUProfileV1Error(message)


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"non-finite JSON constant is forbidden: {value}")


def canonical_bytes(value: object) -> bytes:
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


def _load_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeParticleMeshReciprocalCPUProfileV1Error(
            f"{label} is not canonical ASCII JSON"
        ) from exc
    if type(value) is not dict or raw != canonical_bytes(value):
        _fail(f"{label} canonical serialization changed")
    return value


def _exact_keys(
    value: object, expected: set[str], *, label: str
) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        _fail(f"{label} field set changed")
    return value


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_regular_file(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        _fail(f"source path is not a regular non-symlink file: {relative}")
    return path


def discover_source_paths(root: Path) -> tuple[Path, ...]:
    paths = set(REQUIRED_SOURCE_PATHS)
    for pattern in DISCOVERED_SOURCE_GLOBS:
        for path in root.glob(pattern):
            if path.is_symlink():
                _fail(
                    "particle-mesh reciprocal discovered source must not be a symlink: "
                    f"{path.relative_to(root)}"
                )
            if path.is_file():
                relative = path.relative_to(root)
                if any(
                    "particle_mesh_reciprocal_composite" in component
                    for component in relative.parts
                ):
                    _fail(
                        "descendant composite source entered parent discovery: "
                        f"{relative}"
                    )
                paths.add(relative)
    for relative in paths:
        _require_regular_file(root, relative)
    return tuple(sorted(paths, key=lambda value: value.as_posix()))


def build_source_manifest(root: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for relative in discover_source_paths(root):
        raw = _require_regular_file(root, relative).read_bytes()
        rows.append(
            {
                "byte_count": len(raw),
                "path": relative.as_posix(),
                "sha256": _sha256(raw),
            }
        )
    return {
        "files": rows,
        "schema_id": SOURCE_SCHEMA_ID,
        "scope": SOURCE_SCOPE,
    }


def require_source_manifest(
    root: Path, raw: bytes
) -> tuple[dict[str, object], dict[str, bytes]]:
    manifest = _load_canonical_object(raw, label="source manifest")
    _exact_keys(manifest, {"files", "schema_id", "scope"}, label="manifest")
    if manifest["schema_id"] != SOURCE_SCHEMA_ID:
        _fail("source manifest schema changed")
    if manifest["scope"] != SOURCE_SCOPE:
        _fail("source manifest scope changed")
    rows = manifest["files"]
    if type(rows) is not list or not rows:
        _fail("source manifest files must be a non-empty list")

    expected_paths = [path.as_posix() for path in discover_source_paths(root)]
    observed_paths: list[str] = []
    for index, row in enumerate(rows):
        entry = _exact_keys(
            row,
            {"byte_count", "path", "sha256"},
            label=f"source row {index}",
        )
        path_value = entry["path"]
        byte_count = entry["byte_count"]
        digest = entry["sha256"]
        if type(path_value) is not str or not path_value:
            _fail(f"source row {index} path is invalid")
        relative = Path(path_value)
        if relative.is_absolute() or relative.as_posix() != path_value:
            _fail(f"source row {index} path is not normalized")
        if ".." in relative.parts:
            _fail(f"source row {index} path escapes the repository")
        if type(byte_count) is not int or byte_count < 0:
            _fail(f"source row {index} byte_count is invalid")
        if type(digest) is not str or SHA256_PATTERN.fullmatch(digest) is None:
            _fail(f"source row {index} sha256 is invalid")
        observed_paths.append(path_value)

    if observed_paths != sorted(set(observed_paths)):
        _fail("source manifest paths must be sorted and unique")
    if observed_paths != expected_paths:
        _fail("source manifest path closure changed; run --refresh explicitly")

    sources: dict[str, bytes] = {}
    for entry in rows:
        assert isinstance(entry, dict)
        path_value = entry["path"]
        byte_count = entry["byte_count"]
        digest = entry["sha256"]
        assert isinstance(path_value, str)
        assert isinstance(byte_count, int)
        assert isinstance(digest, str)
        source_raw = _require_regular_file(root, Path(path_value)).read_bytes()
        if len(source_raw) != byte_count or _sha256(source_raw) != digest:
            _fail(f"source bytes drifted: {path_value}")
        sources[path_value] = source_raw
    return manifest, sources


def _require_parent_reference(root: Path) -> None:
    expected = {
        REFERENCE_PROFILE_RELATIVE_PATH: PARENT_REFERENCE["profile_sha256"],
        REFERENCE_MANIFEST_RELATIVE_PATH: PARENT_REFERENCE[
            "source_manifest_sha256"
        ],
        REFERENCE_SOURCE_RELATIVE_PATH: PARENT_REFERENCE["source_sha256"],
        REFERENCE_FFT_RELATIVE_PATH: PARENT_REFERENCE["fft_sha256"],
        REFERENCE_FIXTURE_RELATIVE_PATH: PARENT_REFERENCE["fixture_sha256"],
        REFERENCE_LOCK_RELATIVE_PATH: PARENT_REFERENCE["cargo_lock_sha256"],
    }
    for relative, digest in expected.items():
        raw = _require_regular_file(root, relative).read_bytes()
        if _sha256(raw) != digest:
            _fail(f"parent reference input drifted: {relative}")


def _require_source_contract(sources: dict[str, bytes]) -> None:
    def text(path: str) -> str:
        try:
            return sources[path].decode("utf-8")
        except UnicodeError as exc:
            raise NativeParticleMeshReciprocalCPUProfileV1Error(
                f"source is not UTF-8: {path}"
            ) from exc

    header = text("include/betelgeuze/particle_mesh_reciprocal.h")
    for required in (
        "BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MAJOR UINT32_C(1)",
        "BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MINOR UINT32_C(0)",
        "BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION UINT32_C(1)",
        "typedef struct bg_particle_mesh_reciprocal_model_v1",
        "bg_particle_mesh_reciprocal_model_v1_create",
        "bg_particle_mesh_reciprocal_model_v1_destroy",
        "bg_context_evaluate_particle_mesh_reciprocal_v1",
        "AUTO\n * and both HIP backends fail closed; this function never falls back",
    ):
        if required not in header:
            _fail(f"public particle-mesh reciprocal header contract missing: {required}")

    engine_header = text("include/betelgeuze/engine.h")
    for required in (
        "BG_ABI_VERSION_MAJOR UINT32_C(1)",
        "BG_ABI_VERSION_MINOR UINT32_C(21)",
        "BG_ABI_VERSION UINT32_C(1)",
    ):
        if required not in engine_header:
            _fail(f"frozen Engine ABI identity changed: {required}")

    error_names = (
        "NONE",
        "EMPTY_SYSTEM",
        "CAPACITY_EXCEEDED",
        "CHARGE_COUNT_MISMATCH",
        "NONFINITE_COORDINATE",
        "NONFINITE_CHARGE",
        "NON_NEUTRAL_SYSTEM",
        "INVALID_CELL",
        "INVALID_PARAMETER",
        "INVALID_MESH",
        "NONFINITE_RESULT",
    )
    for code, name in enumerate(error_names):
        required = f"BG_PARTICLE_MESH_RECIPROCAL_ERROR_{name} = {code}"
        if required not in header:
            _fail(f"public particle-mesh reciprocal typed error mapping changed: {required}")

    version_map = text("native/betelgeuze_engine.map")
    comment_free_version_map = re.sub(
        r"/\*.*?\*/", "", version_map, flags=re.DOTALL
    )
    comment_free_version_map = re.sub(
        r"//[^\n]*", "", comment_free_version_map
    )
    node_headers = re.findall(
        r"(?m)^\s*BETELGEUZE_PARTICLE_MESH_RECIPROCAL_1\.0\s*\{",
        comment_free_version_map,
    )
    if len(node_headers) != 1:
        _fail("particle-mesh reciprocal ELF symbol version node is missing or duplicated")
    node = re.search(
        r"^[ \t]*BETELGEUZE_PARTICLE_MESH_RECIPROCAL_1\.0\s*"
        r"\{\s*global:\s*"
        r"(?P<symbols>.*?)\}\s*"
        r"BETELGEUZE_ENGINE_1\.21\s*;",
        comment_free_version_map,
        re.DOTALL | re.MULTILINE,
    )
    if node is None:
        _fail("particle-mesh reciprocal ELF node parent or shape changed")
    node_body = node["symbols"]
    node_symbols = tuple(
        re.findall(r"([A-Za-z_][A-Za-z0-9_]*|\*)\s*;", node_body)
    )
    residue = re.sub(
        r"(?:[A-Za-z_][A-Za-z0-9_]*|\*)\s*;", "", node_body
    )
    if residue.strip():
        _fail("particle-mesh reciprocal ELF node contains an invalid declaration")
    if node_symbols != PUBLIC_SYMBOLS:
        _fail("particle-mesh reciprocal public symbol set or order changed")
    map_symbols = re.findall(
        r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+);[ \t]*$",
        comment_free_version_map,
    )
    if not map_symbols or len(map_symbols) != len(set(map_symbols)):
        _fail("ELF public symbol map must be non-empty and duplicate-free")
    if any(symbol.startswith("bg_rust_") for symbol in map_symbols):
        _fail("private Rust provider entered the ELF public symbol map")
    macho_exports = text("native/betelgeuze_engine.exports").splitlines()
    expected_macho_exports = [f"_{symbol}" for symbol in map_symbols]
    if any(symbol.startswith("_bg_rust_") for symbol in macho_exports):
        _fail("private Rust provider entered the Mach-O public export allowlist")
    if macho_exports != expected_macho_exports:
        _fail("Mach-O public export allowlist changed from the ELF public ABI")

    cmake_source = text("native/CMakeLists.txt")
    for required in (
        "set(BG_ENGINE_APPLE_EXPORTS",
        '"LINKER:-exported_symbols_list,${BG_ENGINE_APPLE_EXPORTS}"',
        "LINK_DEPENDS ${BG_ENGINE_APPLE_EXPORTS}",
        "set(BG_ENGINE_EXPORT_OBJECT_FORMAT MACHO)",
        "if(UNIX AND CMAKE_NM)",
        "-DOBJECT_FORMAT=${BG_ENGINE_EXPORT_OBJECT_FORMAT}",
        "-DPUBLIC_SYMBOLS=${BG_ENGINE_APPLE_EXPORTS}",
    ):
        if required not in cmake_source:
            _fail(f"Mach-O final-link export boundary is missing: {required}")

    export_test = text("native/tests/check_exports.cmake")
    for required in (
        'OBJECT_FORMAT STREQUAL "MACHO"',
        'COMMAND "${NM}" -g -U -j "${LIBRARY}"',
        'unversioned MATCHES "^bg_rust_"',
        "exported symbol set does not exactly match the public allowlist",
    ):
        if required not in export_test:
            _fail(f"Mach-O export regression check is missing: {required}")
    native_test = text("native/tests/particle_mesh_reciprocal.cpp")
    for required in (
        "verify_abi_layout_and_initializers",
        "verify_frozen_fixture_and_lane_repeatability",
        "verify_transactional_failures_and_typed_precedence",
        "verify_oversized_system_capacity_precedence",
        "verify_required_null_alias_suppresses_error_write",
        "verify_static_validation_and_work_cap",
        "verify_alias_rejection_and_fail_closed_backends",
        "verify_periodicity_permutation_and_charge_inversion",
        "verify_analytic_force_finite_differences",
        "verify_mesh_refinement_observation",
        "verify_zero_charge_and_underflow_rescue",
    ):
        if required not in native_test:
            _fail(f"native particle-mesh reciprocal validation is missing: {required}")
    for required in (
        "const double scale = 1.0 +",
        "tolerance * scale",
    ):
        if required not in native_test:
            _fail(
                "native mixed absolute/relative tolerance check is missing: "
                f"{required}"
            )
    model_source = text("native/src/particle_mesh_reciprocal/model.hpp")
    api_source = text("native/src/particle_mesh_reciprocal/api.cpp")
    allocation_free_commit = re.compile(
        r"void\s+commit_error\s*\(.*?std::string_view\s+detail\s*\)\s*noexcept",
        re.DOTALL,
    )
    literal_typed_failure = re.compile(
        r"template\s*<\s*std::size_t\s+Size\s*>\s*"
        r"bg_status\s+typed_failure\s*\(.*?"
        r"const\s+char\s*\(&detail\)\s*\[Size\]",
        re.DOTALL,
    )
    if (
        allocation_free_commit.search(api_source) is None
        or literal_typed_failure.search(api_source) is None
    ):
        _fail("native noexcept typed-error commit is not allocation-free")
    context_source = text("native/src/context.cpp")
    if (
        "context->requested_backend = options->backend;" not in context_source
        or "switch (context->requested_backend)" not in api_source
        or "make_context(BG_BACKEND_AUTO)" not in native_test
    ):
        _fail("native requested-backend fail-closed boundary is missing")
    for required in (
        "atom_count = 0",
        "cell_lengths_angstrom",
        "mesh_dimensions",
        "dielectric",
    ):
        if required not in model_source + api_source:
            _fail(
                "particle-mesh reciprocal owned model configuration is missing: "
                f"{required}"
            )
    for required in (
        "alias_parameters_before",
        "alias_error_before",
        "validate_create_descriptor_overlap",
        "counted_range_overlaps",
    ):
        combined = native_test + api_source
        if required not in combined:
            _fail(f"native create alias guard is missing: {required}")
    stale_error_pattern = re.compile(
        r"BG_STATUS_BUFFER_TOO_SMALL\);\s*"
        r"assert\(error\.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE\);\s*"
        r"assert\(error\.detail\[0\] == '\\0'\);"
    )
    if stale_error_pattern.search(native_test) is None:
        _fail("native particle-mesh reciprocal stale typed-error clearing validation is missing")
    rust_source = text("rust/cpu-kernel/src/particle_mesh_reciprocal.rs")
    if "pub unsafe extern \"C\" fn bg_rust_particle_mesh_reciprocal_evaluate_v1" not in rust_source:
        _fail("Rust particle-mesh reciprocal provider entry point is missing")
    for required in (
        "evaluate_with_force_option",
        "energy_only_skips_inverse_and_gather_without_changing_energy_bits",
        "bg_rust_particle_mesh_reciprocal_provider_abi_version_v1",
        "try_reserve_exact",
    ):
        if required not in rust_source:
            _fail(f"Rust particle-mesh reciprocal energy-only force elision is missing: {required}")
    production_rust_source = rust_source.split("#[cfg(test)]\nmod tests", maxsplit=1)[0]
    for forbidden in ("format!(", ".to_owned(", "Cow", "String", ".sort_by("):
        if forbidden in production_rust_source:
            _fail(
                "Rust particle-mesh reciprocal failure diagnostic may allocate: "
                f"{forbidden}"
            )
    if production_rust_source.count(".sort_unstable_by(") != 2:
        _fail("Rust particle-mesh reciprocal allocation-free sort contract changed")
    for required in (
        "detail: &'static str",
        "production_failure_diagnostics_are_statically_allocated",
    ):
        if required not in rust_source:
            _fail(
                "Rust particle-mesh reciprocal static diagnostic guard is missing: "
                f"{required}"
            )
    rust_adapter = text("native/src/particle_mesh_reciprocal/rust_evaluator.cpp")
    preflight_markers = (
        "if (atom_count == 0U)",
        "if (atom_count > kMaxAtomCount)",
        "if (system.position_y.size() != atom_count",
        "if (bg_rust_particle_mesh_reciprocal_provider_abi_version_v1() !=",
        "force_x.resize(atom_count)",
    )
    try:
        preflight_offsets = tuple(
            rust_adapter.index(marker) for marker in preflight_markers
        )
    except ValueError:
        _fail("Rust adapter allocation-free capacity preflight is missing")
    if preflight_offsets != tuple(sorted(preflight_offsets)):
        _fail("Rust adapter capacity preflight moved after provider or force allocation")
    for legacy_workflow_path in (
        ".github/workflows/ci-engine-v2-native-direct-ewald.yml",
        ".github/workflows/ci-engine-v2-native-direct-ewald-composite.yml",
        ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics.yml",
    ):
        legacy_workflow = text(legacy_workflow_path)
        for required in (
            "frozen=ebbd7a20538cfd7516d9b53adb2e54c6de14bd97",
            "frozen_tree=2ae92801369c7e16147e07cbb16e19c062e52cc9",
            'current_sha="$(git rev-parse HEAD)"',
            'git diff --exit-code "$frozen" --',
            'git checkout --detach --quiet "$frozen"',
            'git checkout --detach --quiet "$current_sha"',
            'test "$(git rev-parse HEAD)" = "$current_sha"',
        ):
            if required not in legacy_workflow:
                _fail(
                    "legacy native evidence workflow is not frozen-object bound: "
                    f"{legacy_workflow_path}: {required}"
                )
        if "--refresh" in legacy_workflow:
            _fail(
                "legacy native evidence workflow must not refresh evidence: "
                f"{legacy_workflow_path}"
            )
    for legacy_unit_path in (
        "tests/unit/test_engine_v2_native_direct_ewald_cpu_v1.py",
        "tests/unit/test_engine_v2_native_direct_ewald_composite_v1.py",
        "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_v1.py",
    ):
        legacy_unit = text(legacy_unit_path)
        for required in (
            "pytest.mark.skipif(",
            "ADDITIVE_RECIPROCAL_EVIDENCE_PRESENT",
            "include/betelgeuze/particle_mesh_reciprocal.h",
            "engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1.json",
            "verify_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py",
            "frozen object",
        ):
            if required not in legacy_unit:
                _fail(
                    "legacy native evidence unit is not descendant-aware: "
                    f"{legacy_unit_path}: {required}"
                )
    nonproduction_paths = {
        REFERENCE_PROFILE_RELATIVE_PATH.as_posix(),
        REFERENCE_MANIFEST_RELATIVE_PATH.as_posix(),
        REFERENCE_SOURCE_RELATIVE_PATH.as_posix(),
        REFERENCE_FFT_RELATIVE_PATH.as_posix(),
        REFERENCE_FIXTURE_RELATIVE_PATH.as_posix(),
        REFERENCE_LOCK_RELATIVE_PATH.as_posix(),
        RUNTIME_FIXTURE_RELATIVE_PATH.as_posix(),
        "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py",
        "tools/verify_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py",
    }
    nonproduction_prefixes = (
        ".github/workflows/",
        "native/tests/",
        "rust/betelgeuze-runtime/tests/",
        "rust/betelgeuze-sys/tests/",
        "tests/unit/",
    )
    production_paths = sorted(
        path
        for path in sources
        if path not in nonproduction_paths
        and not path.startswith(nonproduction_prefixes)
    )
    if "native/CMakeLists.txt" not in production_paths:
        _fail("native particle-mesh reciprocal CMake production input is not source-bound")
    forbidden_reference_tokens = (
        "reference-pme",
        "betelgeuze-reference-pme",
        "betelgeuze_reference_pme",
        "reference_pme::",
    )
    for path in production_paths:
        source = text(path)
        for token in forbidden_reference_tokens:
            if token in source:
                _fail(
                    "standalone particle-mesh reciprocal reference entered production: "
                    f"{path}: {token}"
                )

    sys_source = text("rust/betelgeuze-sys/src/lib.rs")
    for required in (
        "pub const BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION: u32 = 1",
        "pub struct bg_particle_mesh_reciprocal_parameters_v1",
        "pub struct bg_particle_mesh_reciprocal_energy_v1",
        "pub struct bg_particle_mesh_reciprocal_force_soa_v1",
        "pub struct bg_particle_mesh_reciprocal_error_v1",
        "pub fn bg_context_evaluate_particle_mesh_reciprocal_v1",
    ):
        if required not in sys_source:
            _fail(f"Rust raw particle-mesh reciprocal ABI binding is missing: {required}")

    sys_manifest = text("rust/betelgeuze-sys/Cargo.toml")
    sys_build = text("rust/betelgeuze-sys/build.rs")
    for path in (
        "abi/particle_mesh_reciprocal_header_c11.c",
        "abi/particle_mesh_reciprocal_layout_assertions.cpp",
        "vendor/include/betelgeuze/particle_mesh_reciprocal.h",
    ):
        if path not in sys_manifest:
            _fail(f"Rust system package omitted particle-mesh reciprocal input: {path}")
    for required in (
        "particle_mesh_reciprocal_c_header_probe",
        "particle_mesh_reciprocal_cpp_layout_probe",
        "betelgeuze_sys_particle_mesh_reciprocal_header_c11_probe",
        "betelgeuze_sys_particle_mesh_reciprocal_cpp_layout_probe",
    ):
        if required not in sys_build:
            _fail(f"Rust system build omitted particle-mesh reciprocal probe: {required}")

    runtime = text("rust/betelgeuze-runtime/src/particle_mesh_reciprocal.rs")
    for required in (
        "pub struct ParticleMeshReciprocalModel",
        "PhantomData<Rc<()>>",
        "impl Drop for ParticleMeshReciprocalModel",
        "bg_particle_mesh_reciprocal_model_v1_destroy",
        "let guard = NonNull::new(handle).map",
        "drop(guard);",
        "pub enum ParticleMeshReciprocalErrorCode",
        "typed_error_mapping_covers_every_frozen_code",
        "auto_and_hip_lanes_fail_closed",
        "pub detail: Cow<'static, str>",
        "if status_code == ErrorCode::OutOfMemory",
        'detail: Cow::Borrowed("particle-mesh reciprocal allocation failed")',
        "map_err(|_| allocation_free_out_of_memory_error())",
        "out_of_memory_error_materialization_is_allocation_free",
    ):
        if required not in runtime:
            _fail(f"safe Rust particle-mesh reciprocal ownership contract is missing: {required}")
    error_function = runtime.split("fn error_from_call(", maxsplit=1)[1].split(
        "\nfn plain_status(", maxsplit=1
    )[0]
    if error_function.index("if status_code == ErrorCode::OutOfMemory") > min(
        error_function.index("let native = Error::native(status)"),
        error_function.index("let bytes: Vec<u8>"),
    ):
        _fail("safe Rust OOM diagnostic is materialized after a fallible allocation")
    force_allocator = runtime.split("fn allocate_force_channel(", maxsplit=1)[1].split(
        "\n#[cfg(test)]", maxsplit=1
    )[0]
    for forbidden in ("format!(", ".to_owned(", "String::"):
        if forbidden in force_allocator:
            _fail(
                "safe Rust force-reserve OOM diagnostic may allocate: "
                f"{forbidden}"
            )

    runtime_test = text("rust/betelgeuze-runtime/tests/particle_mesh_reciprocal.rs")
    for required in (
        'include_str!("fixtures/particle_mesh_reciprocal_v1.tsv")',
        "rust_cpu_lane_preserves_all_thirteen_frozen_bits",
        "cpp_cpu_lane_is_repeatable_and_matches_the_frozen_reference",
        "energy_only_path_equals_force_path_for_both_cpu_lanes",
        "model_is_deep_owned_and_profile_identity_is_stable",
        "typed_creation_and_evaluation_errors_preserve_statuses",
        "auto_request_fails_closed_even_if_native_context_resolves_it_to_cpu",
        "for _ in 0..32",
    ):
        if required not in runtime_test:
            _fail(f"safe Rust particle-mesh reciprocal validation is missing: {required}")
    if sources[RUNTIME_FIXTURE_RELATIVE_PATH.as_posix()] != sources[
        REFERENCE_FIXTURE_RELATIVE_PATH.as_posix()
    ]:
        _fail("runtime particle-mesh reciprocal fixture drifted from the parent oracle fixture")

    vendor_prefix = "rust/betelgeuze-sys/vendor/"
    canonical_paths = [
        "include/betelgeuze/particle_mesh_reciprocal.h",
        "include/betelgeuze/engine.h",
        "native/src/context.cpp",
        "native/src/internal.hpp",
        "native/src/system.cpp",
        *sorted(
            path
            for path in sources
            if path.startswith("native/src/particle_mesh_reciprocal/")
        ),
    ]
    for canonical_path in canonical_paths:
        vendor_path = vendor_prefix + canonical_path
        if vendor_path not in sources:
            _fail(f"vendored particle-mesh reciprocal source is missing: {vendor_path}")
        if sources[vendor_path] != sources[canonical_path]:
            _fail(f"vendored particle-mesh reciprocal source drifted: {vendor_path}")


def require_profile(
    raw: bytes,
    *,
    source_manifest_raw: bytes,
    source_count: int,
) -> dict[str, object]:
    profile = _load_canonical_object(raw, label="profile")
    _exact_keys(
        profile,
        {
            "abi",
            "authority",
            "implementation",
            "operational_boundary",
            "parent_reference",
            "profile_id",
            "roadmap_issue",
            "schema_id",
            "validation",
        },
        label="profile",
    )
    if profile["schema_id"] != SCHEMA_ID or profile["profile_id"] != PROFILE_ID:
        _fail("profile identity changed")
    if profile["roadmap_issue"] != 434:
        _fail("roadmap issue changed")
    if profile["parent_reference"] != PARENT_REFERENCE:
        _fail("parent reference binding changed")
    if profile["abi"] != ABI_CONTRACT:
        _fail("particle-mesh reciprocal ABI contract changed")
    expected_implementation = {
        **IMPLEMENTATION_CONTRACT_BASE,
        "source_manifest_entry_count": source_count,
        "source_manifest_sha256": _sha256(source_manifest_raw),
    }
    if profile["implementation"] != expected_implementation:
        _fail("native implementation binding changed")
    if profile["operational_boundary"] != OPERATIONAL_BOUNDARY:
        _fail("operational blocker boundary changed")
    if profile["validation"] != VALIDATION_CONTRACT:
        _fail("validation contract changed")
    if profile["authority"] != AUTHORITY_CONTRACT:
        _fail("claim authority changed")
    return profile


def build_profile(
    *, source_manifest_raw: bytes, source_count: int
) -> dict[str, object]:
    return {
        "abi": dict(ABI_CONTRACT),
        "authority": dict(AUTHORITY_CONTRACT),
        "implementation": {
            **IMPLEMENTATION_CONTRACT_BASE,
            "source_manifest_entry_count": source_count,
            "source_manifest_sha256": _sha256(source_manifest_raw),
        },
        "operational_boundary": {
            "blockers": list(OPERATIONAL_BLOCKERS),
            "unresolved_operational_decisions": 32,
        },
        "parent_reference": dict(PARENT_REFERENCE),
        "profile_id": PROFILE_ID,
        "roadmap_issue": 434,
        "schema_id": SCHEMA_ID,
        "validation": dict(VALIDATION_CONTRACT),
    }


def verify(root: Path = ROOT) -> dict[str, object]:
    profile_path = root / PROFILE_RELATIVE_PATH
    manifest_path = root / SOURCE_MANIFEST_RELATIVE_PATH
    profile_raw = _require_regular_file(root, PROFILE_RELATIVE_PATH).read_bytes()
    manifest_raw = _require_regular_file(
        root, SOURCE_MANIFEST_RELATIVE_PATH
    ).read_bytes()
    manifest, sources = require_source_manifest(root, manifest_raw)
    rows = manifest["files"]
    assert isinstance(rows, list)
    require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
    )
    _require_parent_reference(root)
    _require_source_contract(sources)
    return {
        "all_authority_false_except_development_fixture_boundary": True,
        "fixed64_cpu_v7_qualification_invoked": False,
        "hip_device_execution_invoked": False,
        "molecular_execution_invoked": False,
        "operational_blocker_count": len(OPERATIONAL_BLOCKERS),
        "profile_path": profile_path.relative_to(root).as_posix(),
        "profile_sha256": _sha256(profile_raw),
        "source_count": len(rows),
        "source_manifest_path": manifest_path.relative_to(root).as_posix(),
        "source_manifest_sha256": _sha256(manifest_raw),
        "verified": True,
    }


def refresh(root: Path = ROOT) -> dict[str, object]:
    profile_path = _require_regular_file(root, PROFILE_RELATIVE_PATH)
    manifest = build_source_manifest(root)
    manifest_raw = canonical_bytes(manifest)
    rows = manifest["files"]
    assert isinstance(rows, list)
    _, sources = require_source_manifest(root, manifest_raw)
    _require_parent_reference(root)
    _require_source_contract(sources)
    profile = build_profile(
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
    )
    profile_raw = canonical_bytes(profile)
    require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
    )
    (root / SOURCE_MANIFEST_RELATIVE_PATH).write_bytes(manifest_raw)
    profile_path.write_bytes(profile_raw)
    result = verify(root)
    result["refreshed"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "rewrite the source manifest and its profile binding from the "
            "current explicit source closure"
        ),
    )
    arguments = parser.parse_args(argv)
    try:
        result = refresh(ROOT) if arguments.refresh else verify(ROOT)
    except NativeParticleMeshReciprocalCPUProfileV1Error as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
