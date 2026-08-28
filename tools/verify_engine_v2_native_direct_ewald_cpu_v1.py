#!/usr/bin/env python3
"""Verify the immutable native direct-Ewald CPU v1 development evidence."""

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
    "config/engine_v2_native_direct_ewald_cpu_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_cpu_profile_v1_sources.json"
)
REFERENCE_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_direct_ewald_reference_profile_v1.json"
)
REFERENCE_SOURCE_RELATIVE_PATH = Path("rust/reference-ewald/src/lib.rs")
REFERENCE_FIXTURE_RELATIVE_PATH = Path(
    "rust/reference-ewald/fixtures/direct_ewald_v1.tsv"
)
REFERENCE_LOCK_RELATIVE_PATH = Path("rust/reference-ewald/Cargo.lock")
RUNTIME_FIXTURE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/tests/fixtures/direct_ewald_v1.tsv"
)

SCHEMA_ID = "betelgeuze.engine_v2_native_direct_ewald_cpu_profile/1.0.0"
PROFILE_ID = "engine_v2_native_direct_ewald_cpu_development_v1"
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_cpu_sources/1.0.0"
)
SOURCE_SCOPE = (
    "direct_ewald_v1_owned_sources_bindings_tests_and_parent_oracle_inputs"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

PARENT_REFERENCE = {
    "cargo_lock_sha256": (
        "cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d"
    ),
    "fixture_sha256": (
        "a720c83852c79e401cb8838e9e20b2196985b6e424275949f77291b30b3da338"
    ),
    "merge_commit": "ba008fcaa75891bca45e7b3d33b67449d80fb7d4",
    "merge_tree": "0530a50af2cceeff02341ccb6fab141fd8c43726",
    "profile_path": REFERENCE_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "dd2c7460c2c3e7ea800da51e29bdf54d8933497ade086812d882a65cca4f4e6c"
    ),
    "pull_request": 435,
    "reference_schema_id": "betelgeuze.reference_direct_ewald/1.0.0",
    "reviewed_head": "b94e4c008db1c8414f5d0f24fa266c85c828d13c",
    "source_sha256": (
        "2de8d94d69175053ccaf2a8057a385019fe5c398d7d95d96c84dc3d9bfafc99e"
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
    "error_code_maximum": 20,
    "export_version_node": "BETELGEUZE_DIRECT_EWALD_1.0",
    "header": "include/betelgeuze/direct_ewald.h",
    "model_profile_id": "betelgeuze.native_direct_ewald/1.0.0",
    "separately_versioned_boundary": True,
}

IMPLEMENTATION_CONTRACT_BASE = {
    "cpp_cpu_reference_lane": True,
    "deep_copied_model_parameters_and_pair_rules": True,
    "direct_ewald_implemented": True,
    "external_md_engine_dependency": False,
    "fixed64_cpu_v7_qualification_invoked": False,
    "hip_device_implementation": False,
    "hip_to_cpu_fallback": False,
    "independent_parent_reference_linked_into_production": False,
    "pme_implemented": False,
    "pair_rule_exclusion_provenance_preserved": True,
    "rust_cpu_lane": True,
    "runtime_fixture_path": RUNTIME_FIXTURE_RELATIVE_PATH.as_posix(),
    "runtime_fixture_sha256": PARENT_REFERENCE["fixture_sha256"],
    "shared_runtime_dynamics_integrated": False,
    "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
}

VALIDATION_CONTRACT = {
    "c11_public_header_probe": True,
    "canonical_vendor_byte_identity": True,
    "cpp_and_rust_typed_ambiguity_damping_phase_error_parity": True,
    "cpp_cpu_frozen_fixture_against_parent_oracle": True,
    "cpp_cpu_same_input_bitwise_repeat": True,
    "cpp_rust_energy_and_force_relative_tolerance": 5e-12,
    "cpp_struct_layout_probe": True,
    "create_out_model_alias_rejected_before_write": True,
    "create_output_storage_pair_rule_alias_rejected_before_write": True,
    "descriptor_initializer_transactionality": True,
    "energy_component_count": 5,
    "evaluation_failure_output_transactionality": True,
    "force_component_count": 12,
    "hip_backend_fails_closed_without_device_execution": True,
    "model_create_failure_returns_null_handle": True,
    "model_deep_copy_survives_caller_input_mutation": True,
    "model_pair_rule_provenance_source_guard": True,
    "mach_o_public_export_allowlist_enforced": True,
    "public_symbol_version_enforced": True,
    "required_null_input_clears_valid_typed_error": True,
    "rust_safe_abnormal_create_return_handle_guard": True,
    "rust_safe_model_single_owner_drop_contract": True,
    "rust_safe_model_send_sync_disabled": True,
    "rust_safe_runtime_both_cpu_lanes_against_parent_fixture": True,
    "rust_safe_runtime_energy_only_bit_identity": True,
    "rust_cpu_energy_only_skips_force_storage_and_accumulation": True,
    "rust_safe_runtime_failure_recovery": True,
    "rust_safe_runtime_parent_fixture_byte_identity": True,
    "rust_safe_runtime_same_lane_bitwise_repeat": True,
    "rust_safe_runtime_temporary_model_drop_iterations": 32,
    "rust_safe_typed_error_mapping_complete": True,
    "rust_cpu_frozen_fixture_bit_identity_against_parent_oracle": True,
    "rust_cpu_same_input_bitwise_repeat": True,
    "rust_sys_raw_abi_binding": True,
    "stale_typed_error_cleared_before_untyped_failure": True,
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
    Path("include/betelgeuze/direct_ewald.h"),
    Path("include/betelgeuze/engine.h"),
    Path("native/CMakeLists.txt"),
    Path("native/betelgeuze_engine.exports"),
    Path("native/betelgeuze_engine.map"),
    Path("native/src/context.cpp"),
    Path("native/src/internal.hpp"),
    Path("native/src/system.cpp"),
    Path("native/tests/check_exports.cmake"),
    Path("native/tests/direct_ewald.cpp"),
    Path("rust/Cargo.lock"),
    Path("rust/Cargo.toml"),
    Path("rust/betelgeuze-runtime/Cargo.toml"),
    Path("rust/betelgeuze-runtime/build.rs"),
    Path("rust/betelgeuze-runtime/src/direct_ewald.rs"),
    Path("rust/betelgeuze-runtime/src/lib.rs"),
    Path("rust/betelgeuze-runtime/tests/direct_ewald.rs"),
    RUNTIME_FIXTURE_RELATIVE_PATH,
    Path("rust/betelgeuze-sys/Cargo.toml"),
    Path("rust/betelgeuze-sys/abi/direct_ewald_header_c11.c"),
    Path("rust/betelgeuze-sys/abi/direct_ewald_layout_assertions.cpp"),
    Path("rust/betelgeuze-sys/build.rs"),
    Path("rust/betelgeuze-sys/src/lib.rs"),
    Path("rust/betelgeuze-sys/tests/layout.rs"),
    Path("rust/betelgeuze-sys/tests/raw_smoke.rs"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze/direct_ewald.h"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze/engine.h"),
    Path("rust/betelgeuze-sys/vendor/native/src/context.cpp"),
    Path("rust/betelgeuze-sys/vendor/native/src/internal.hpp"),
    Path("rust/betelgeuze-sys/vendor/native/src/system.cpp"),
    Path("rust/cpu-kernel/Cargo.toml"),
    Path("rust/cpu-kernel/src/direct_ewald.rs"),
    Path("rust/cpu-kernel/src/lib.rs"),
    Path("rust_engine_v2/Cargo.lock"),
    Path("rust_engine_v2/Cargo.toml"),
    REFERENCE_PROFILE_RELATIVE_PATH,
    REFERENCE_SOURCE_RELATIVE_PATH,
    REFERENCE_FIXTURE_RELATIVE_PATH,
    REFERENCE_LOCK_RELATIVE_PATH,
    Path("tools/__init__.py"),
    Path("tools/verify_engine_v2_native_direct_ewald_cpu_v1.py"),
)

# New direct-Ewald-specific ABI probes, vendor copies, runtime bindings, and
# tests are discovered automatically. Descendant composite ABIs have their own
# evidence closures and must not become dependencies of this parent profile.
# Adding or removing a parent source makes ordinary verification fail until
# --refresh is explicitly run.
DISCOVERED_SOURCE_GLOBS = (
    "native/src/ewald/**/*",
    "rust/betelgeuze-runtime/src/**/*direct_ewald*",
    "rust/betelgeuze-runtime/tests/**/*direct_ewald*",
    "rust/betelgeuze-sys/abi/**/*direct_ewald*",
    "rust/betelgeuze-sys/tests/**/*direct_ewald*",
    "rust/betelgeuze-sys/vendor/include/betelgeuze/direct_ewald.h",
    "rust/betelgeuze-sys/vendor/native/src/ewald/**/*",
)


class NativeDirectEwaldCPUProfileV1Error(ValueError):
    """The native direct-Ewald CPU v1 evidence failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeDirectEwaldCPUProfileV1Error(message)


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
        raise NativeDirectEwaldCPUProfileV1Error(
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
                    "direct-Ewald discovered source must not be a symlink: "
                    f"{path.relative_to(root)}"
                )
            if path.is_file():
                relative = path.relative_to(root)
                if "direct_ewald_composite" not in relative.name:
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
        REFERENCE_SOURCE_RELATIVE_PATH: PARENT_REFERENCE["source_sha256"],
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
            raise NativeDirectEwaldCPUProfileV1Error(
                f"source is not UTF-8: {path}"
            ) from exc

    header = text("include/betelgeuze/direct_ewald.h")
    for required in (
        "BG_DIRECT_EWALD_ABI_VERSION_MAJOR UINT32_C(1)",
        "BG_DIRECT_EWALD_ABI_VERSION_MINOR UINT32_C(0)",
        "BG_DIRECT_EWALD_ABI_VERSION UINT32_C(1)",
        "typedef struct bg_direct_ewald_model_v1",
        "bg_direct_ewald_model_v1_create",
        "bg_direct_ewald_model_v1_destroy",
        "bg_context_evaluate_direct_ewald_v1",
        "lanes fail closed and never execute or fall back to CPU",
    ):
        if required not in header:
            _fail(f"public direct-Ewald header contract missing: {required}")

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
        "CUTOFF_VIOLATES_MINIMUM_IMAGE",
        "INVALID_PARAMETER",
        "ATOM_INDEX_OUT_OF_RANGE",
        "REPEATED_ATOM_INDEX",
        "DUPLICATE_PAIR_RULE",
        "CONFLICTING_PAIR_RULE",
        "AMBIGUOUS_PAIR_CORRECTION_IMAGE",
        "AMBIGUOUS_REAL_SPACE_CUTOFF",
        "AMBIGUOUS_MINIMUM_PAIR_DISTANCE",
        "PAIR_BELOW_MINIMUM_DISTANCE",
        "DAMPING_UNDERFLOW",
        "PHASE_UNDERFLOW",
        "NONFINITE_RESULT",
    )
    for code, name in enumerate(error_names):
        required = f"BG_DIRECT_EWALD_ERROR_{name} = {code}"
        if required not in header:
            _fail(f"public direct-Ewald typed error mapping changed: {required}")

    version_map = text("native/betelgeuze_engine.map")
    if "BETELGEUZE_DIRECT_EWALD_1.0" not in version_map:
        _fail("direct-Ewald ELF symbol version node is missing")
    map_symbols = re.findall(
        r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+);[ \t]*$", version_map
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
    native_test = text("native/tests/direct_ewald.cpp")
    for required in (
        "verify_initializer_transactionality<bg_direct_ewald_parameters_v1>",
        "verify_initializer_transactionality<\n        bg_direct_ewald_energy_components_v1>",
        "verify_initializer_transactionality<bg_direct_ewald_force_soa_v1>",
        "verify_initializer_transactionality<bg_direct_ewald_error_v1>",
        "verify_frozen_fixture_and_deep_ownership",
        "verify_rust_cpp_cpu_parity",
        "verify_evaluation_transactionality_and_typed_errors",
        "verify_mandatory_null_clears_error",
        "verify_numeric_error_parity",
        "verify_hip_fails_closed_without_device_execution",
    ):
        if required not in native_test:
            _fail(f"native direct-Ewald validation is missing: {required}")
    model_source = text("native/src/ewald/model.hpp")
    api_source = text("native/src/ewald/api.cpp")
    for required in (
        "bool is_exclusion = false;",
        "exclusion->first.atom_j, 0.0, true",
        "scale->second,\n                false",
    ):
        if required not in model_source + api_source:
            _fail(
                "direct-Ewald pair-rule exclusion provenance is missing: "
                f"{required}"
            )
    for required in (
        "alias_parameters_before",
        "alias_error_before",
        "verify_pair_rule_channel_alias",
        "interior_exclusion_i",
        "error_channel_before",
        "validate_create_descriptor_overlap",
        "counted_range_overlaps",
        "channels_may_be_used",
    ):
        combined = native_test + text("native/src/ewald/api.cpp")
        if required not in combined:
            _fail(f"native create alias guard is missing: {required}")
    stale_error_pattern = re.compile(
        r"BG_STATUS_BUFFER_TOO_SMALL\);\s*"
        r"assert\(error\.code == BG_DIRECT_EWALD_ERROR_NONE\);\s*"
        r"assert\(error\.detail\[0\] == '\\0'\);"
    )
    if stale_error_pattern.search(native_test) is None:
        _fail("native direct-Ewald stale typed-error clearing validation is missing")
    rust_source = text("rust/cpu-kernel/src/direct_ewald.rs")
    if "pub unsafe extern \"C\" fn bg_rust_direct_ewald_evaluate_v1" not in rust_source:
        _fail("Rust direct-Ewald provider entry point is missing")
    for required in (
        "evaluate_with_force_option",
        "energy_only_path_has_identical_bits_without_force_storage",
    ):
        if required not in rust_source:
            _fail(f"Rust direct-Ewald energy-only force elision is missing: {required}")
    nonproduction_paths = {
        REFERENCE_PROFILE_RELATIVE_PATH.as_posix(),
        REFERENCE_SOURCE_RELATIVE_PATH.as_posix(),
        REFERENCE_FIXTURE_RELATIVE_PATH.as_posix(),
        REFERENCE_LOCK_RELATIVE_PATH.as_posix(),
        RUNTIME_FIXTURE_RELATIVE_PATH.as_posix(),
        "tools/verify_engine_v2_native_direct_ewald_cpu_v1.py",
    }
    nonproduction_prefixes = (
        "native/tests/",
        "rust/betelgeuze-runtime/tests/",
        "rust/betelgeuze-sys/tests/",
    )
    production_paths = sorted(
        path
        for path in sources
        if path not in nonproduction_paths
        and not path.startswith(nonproduction_prefixes)
    )
    if "native/CMakeLists.txt" not in production_paths:
        _fail("native direct-Ewald CMake production input is not source-bound")
    forbidden_reference_tokens = (
        "reference-ewald",
        "betelgeuze-reference-ewald",
        "betelgeuze_reference_ewald",
        "reference_ewald::",
    )
    for path in production_paths:
        source = text(path)
        for token in forbidden_reference_tokens:
            if token in source:
                _fail(
                    "standalone direct-Ewald reference entered production: "
                    f"{path}: {token}"
                )

    sys_source = text("rust/betelgeuze-sys/src/lib.rs")
    for required in (
        "pub const BG_DIRECT_EWALD_ABI_VERSION: u32 = 1",
        "pub struct bg_direct_ewald_parameters_v1",
        "pub struct bg_direct_ewald_energy_components_v1",
        "pub struct bg_direct_ewald_force_soa_v1",
        "pub struct bg_direct_ewald_error_v1",
        "pub fn bg_context_evaluate_direct_ewald_v1",
    ):
        if required not in sys_source:
            _fail(f"Rust raw direct-Ewald ABI binding is missing: {required}")

    sys_manifest = text("rust/betelgeuze-sys/Cargo.toml")
    sys_build = text("rust/betelgeuze-sys/build.rs")
    for path in (
        "abi/direct_ewald_header_c11.c",
        "abi/direct_ewald_layout_assertions.cpp",
        "vendor/include/betelgeuze/direct_ewald.h",
    ):
        if path not in sys_manifest:
            _fail(f"Rust system package omitted direct-Ewald input: {path}")
    for required in (
        "direct_ewald_c_header_probe",
        "direct_ewald_cpp_layout_probe",
        "betelgeuze_sys_direct_ewald_header_c11_probe",
        "betelgeuze_sys_direct_ewald_cpp_layout_probe",
    ):
        if required not in sys_build:
            _fail(f"Rust system build omitted direct-Ewald probe: {required}")

    runtime = text("rust/betelgeuze-runtime/src/direct_ewald.rs")
    for required in (
        "pub struct DirectEwaldModel",
        "PhantomData<Rc<()>>",
        "impl Drop for DirectEwaldModel",
        "bg_direct_ewald_model_v1_destroy",
        "let model = NonNull::new(handle).map",
        "drop(model);",
        "pub enum DirectEwaldErrorCode",
        "typed_error_mapping_covers_every_frozen_code",
        "unsupported_lanes_fail_closed_without_fallback",
    ):
        if required not in runtime:
            _fail(f"safe Rust direct-Ewald ownership contract is missing: {required}")

    runtime_test = text("rust/betelgeuze-runtime/tests/direct_ewald.rs")
    for required in (
        'include_str!("fixtures/direct_ewald_v1.tsv")',
        "both_cpu_lanes_match_every_frozen_oracle_component_and_force",
        "each_cpu_lane_is_bitwise_repeatable_and_energy_only_is_identical",
        "model_deep_copies_pair_rules_and_drops_independently",
        "typed_creation_and_evaluation_errors_are_preserved_without_poisoning_state",
        "for _ in 0..32",
    ):
        if required not in runtime_test:
            _fail(f"safe Rust direct-Ewald validation is missing: {required}")
    if sources[RUNTIME_FIXTURE_RELATIVE_PATH.as_posix()] != sources[
        REFERENCE_FIXTURE_RELATIVE_PATH.as_posix()
    ]:
        _fail("runtime direct-Ewald fixture drifted from the parent oracle fixture")

    vendor_prefix = "rust/betelgeuze-sys/vendor/"
    canonical_paths = [
        "include/betelgeuze/direct_ewald.h",
        "include/betelgeuze/engine.h",
        "native/src/context.cpp",
        "native/src/internal.hpp",
        "native/src/system.cpp",
        *sorted(
            path
            for path in sources
            if path.startswith("native/src/ewald/")
        ),
    ]
    for canonical_path in canonical_paths:
        vendor_path = vendor_prefix + canonical_path
        if vendor_path not in sources:
            _fail(f"vendored direct-Ewald source is missing: {vendor_path}")
        if sources[vendor_path] != sources[canonical_path]:
            _fail(f"vendored direct-Ewald source drifted: {vendor_path}")


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
        _fail("direct-Ewald ABI contract changed")
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
    except NativeDirectEwaldCPUProfileV1Error as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
