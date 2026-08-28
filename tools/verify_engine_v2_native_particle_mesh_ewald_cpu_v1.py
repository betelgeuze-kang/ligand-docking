#!/usr/bin/env python3
"""Verify the immutable stateless particle-mesh Ewald CPU v1 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_cpu_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_cpu_profile_v1_sources.json"
)
SCHEMA_ID = "betelgeuze.engine_v2_native_particle_mesh_ewald_cpu_profile/1.0.0"
PROFILE_ID = "engine_v2_native_particle_mesh_ewald_cpu_development_v1"
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_cpu_sources/1.0.0"
)
SOURCE_SCOPE = "particle_mesh_ewald_v1_owned_sources_bindings_tests_and_frozen_parents"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

PUBLIC_SYMBOLS = (
    "bg_particle_mesh_ewald_abi_version",
    "bg_particle_mesh_ewald_abi_version_major",
    "bg_particle_mesh_ewald_abi_version_minor",
    "bg_particle_mesh_ewald_abi_version_string",
    "bg_particle_mesh_ewald_energy_components_v1_init",
    "bg_particle_mesh_ewald_force_soa_v1_init",
    "bg_particle_mesh_ewald_v1_profile_id",
    "bg_context_evaluate_particle_mesh_ewald_v1",
)

PARENT_REFERENCES = {
    "direct_ewald_reference": {
        "cargo_lock_sha256": (
            "cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d"
        ),
        "fixture_sha256": (
            "a720c83852c79e401cb8838e9e20b2196985b6e424275949f77291b30b3da338"
        ),
        "merge_commit": "ba008fcaa75891bca45e7b3d33b67449d80fb7d4",
        "merge_tree": "0530a50af2cceeff02341ccb6fab141fd8c43726",
        "profile_sha256": (
            "dd2c7460c2c3e7ea800da51e29bdf54d8933497ade086812d882a65cca4f4e6c"
        ),
        "pull_request": 435,
        "reviewed_head": "b94e4c008db1c8414f5d0f24fa266c85c828d13c",
        "source_sha256": (
            "2de8d94d69175053ccaf2a8057a385019fe5c398d7d95d96c84dc3d9bfafc99e"
        ),
    },
    "native_direct_ewald": {
        "merge_commit": "074d3b71373088c0738de7a14797fe35d66d986e",
        "merge_tree": "e2763a42f4605d7435514c49f18259ea44f4dd3c",
        "profile_sha256": (
            "5d0a09742e8388938e90988a6a23fd945d5e2613d0fa37e9f2c8c9dd86d89de8"
        ),
        "pull_request": 436,
        "reviewed_head": "60a0047af27acacbce3feed7ee1dcedd8a690176",
        "source_manifest_sha256": (
            "4f2acac517f56ade77b8712bfd24b4312f208f2a5902862f73a807e2a3f7e3ab"
        ),
    },
    "particle_mesh_reciprocal_reference": {
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
        "profile_sha256": (
            "d867651e8d6ce0ec1ead0c0e22dc684b4a0b6247ee35f2bcc9e17105f4c244d3"
        ),
        "pull_request": 439,
        "reviewed_head": "62d309c82aab9b4cfa45c4c3e6d11c93b3bd3786",
        "source_manifest_sha256": (
            "da6d669c85d63236936ba1f1324937b90e7cf57cc6dd58b16ab7d43d6278b296"
        ),
        "source_sha256": (
            "9579d213ec47fc75f70dbb4df76ff951de4a51518dc9216233c663a3e43e53c4"
        ),
    },
    "native_particle_mesh_reciprocal": {
        "merge_commit": "735883551510cbef91adc3e57dc131a1234b67fb",
        "merge_tree": "6c2b6f3960b6df0592b78bb44e429389aa58bcbb",
        "profile_sha256": (
            "ea1a3c92bab2f6a9901aba9f296f7cb59aad2b9ebf4f5a0fa9bf35b7a0f153f7"
        ),
        "pull_request": 440,
        "reviewed_head": "098bce0d726dbed6e4bf7b533e0445f81e244ea2",
        "source_manifest_sha256": (
            "2b60fd079ed8f2af6d023f0b57a0627b449dea4e4037d8ed6d323d4467c940a2"
        ),
    },
}

FROZEN_OBJECTS = {
    "ba008fcaa75891bca45e7b3d33b67449d80fb7d4": {
        "tree": "0530a50af2cceeff02341ccb6fab141fd8c43726",
        "files": {
            "config/engine_v2_direct_ewald_reference_profile_v1.json": (
                "dd2c7460c2c3e7ea800da51e29bdf54d8933497ade086812d882a65cca4f4e6c"
            ),
            "rust/reference-ewald/src/lib.rs": (
                "2de8d94d69175053ccaf2a8057a385019fe5c398d7d95d96c84dc3d9bfafc99e"
            ),
            "rust/reference-ewald/fixtures/direct_ewald_v1.tsv": (
                "a720c83852c79e401cb8838e9e20b2196985b6e424275949f77291b30b3da338"
            ),
            "rust/reference-ewald/Cargo.lock": (
                "cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d"
            ),
        },
    },
    "074d3b71373088c0738de7a14797fe35d66d986e": {
        "tree": "e2763a42f4605d7435514c49f18259ea44f4dd3c",
        "files": {
            "config/engine_v2_native_direct_ewald_cpu_profile_v1.json": (
                "5d0a09742e8388938e90988a6a23fd945d5e2613d0fa37e9f2c8c9dd86d89de8"
            ),
            "config/engine_v2_native_direct_ewald_cpu_profile_v1_sources.json": (
                "4f2acac517f56ade77b8712bfd24b4312f208f2a5902862f73a807e2a3f7e3ab"
            ),
        },
    },
    "ebbd7a20538cfd7516d9b53adb2e54c6de14bd97": {
        "tree": "2ae92801369c7e16147e07cbb16e19c062e52cc9",
        "files": {
            "config/engine_v2_pme_reciprocal_reference_profile_v1.json": (
                "d867651e8d6ce0ec1ead0c0e22dc684b4a0b6247ee35f2bcc9e17105f4c244d3"
            ),
            "config/engine_v2_pme_reciprocal_reference_profile_v1_sources.json": (
                "da6d669c85d63236936ba1f1324937b90e7cf57cc6dd58b16ab7d43d6278b296"
            ),
            "rust/reference-pme/src/lib.rs": (
                "9579d213ec47fc75f70dbb4df76ff951de4a51518dc9216233c663a3e43e53c4"
            ),
            "rust/reference-pme/src/fft.rs": (
                "e65c2a4f3837ae25ce32883671462120c6a2ac9af60c27bbe78e92d502c58c01"
            ),
            "rust/reference-pme/fixtures/pme_reciprocal_v1.tsv": (
                "669e4409ba56897061976c38fbf53985fb1f744e8e5b3613512b0f957951deef"
            ),
            "rust/reference-pme/Cargo.lock": (
                "98d90148a16d2a7fc3f20b27a0cc9ab570c47759c2666ea7a9a0193067c94d80"
            ),
        },
    },
    "735883551510cbef91adc3e57dc131a1234b67fb": {
        "tree": "6c2b6f3960b6df0592b78bb44e429389aa58bcbb",
        "files": {
            "config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1.json": (
                "ea1a3c92bab2f6a9901aba9f296f7cb59aad2b9ebf4f5a0fa9bf35b7a0f153f7"
            ),
            "config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1_sources.json": (
                "2b60fd079ed8f2af6d023f0b57a0627b449dea4e4037d8ed6d323d4467c940a2"
            ),
        },
    },
}

ABI_CONTRACT = {
    "abi_version": 1,
    "abi_version_major": 1,
    "abi_version_minor": 0,
    "abi_version_string": "1.0.0",
    "borrowed_direct_ewald_model": True,
    "borrowed_particle_mesh_reciprocal_model": True,
    "energy_layout_size": 88,
    "engine_abi_reserved_fields_repurposed": False,
    "engine_abi_version_changed": False,
    "error_layout": "bg_direct_ewald_error_v1",
    "export_version_node": "BETELGEUZE_PARTICLE_MESH_EWALD_1.0",
    "export_version_parent": "BETELGEUZE_PARTICLE_MESH_RECIPROCAL_1.0",
    "force_layout_size": 88,
    "header": "include/betelgeuze/particle_mesh_ewald.h",
    "profile_id": "betelgeuze.native_particle_mesh_ewald/1.0.0",
    "public_symbol_count": 8,
    "separately_versioned_boundary": True,
}

IMPLEMENTATION_CONTRACT_BASE = {
    "cpp_cpu_reference_lane": True,
    "direct_reciprocal_bounds_ignored": True,
    "external_md_engine_dependency": False,
    "fixed64_cpu_v7_qualification_invoked": False,
    "hip_device_implementation": False,
    "hip_to_cpu_fallback": False,
    "independent_parent_references_linked_into_production": False,
    "mesh_reciprocal_component_implemented": True,
    "new_model_ownership_introduced": False,
    "pair_rule_provenance_preserved": True,
    "real_self_pair_total_composition_implemented": True,
    "rust_cpu_runtime_fixture_total_bits_hex": "c0186145396def20",
    "rust_cpu_lane": True,
    "shared_runtime_dynamics_integrated": False,
    "short_range_composite_integrated": False,
    "stateful_checkpoint_integrated": False,
    "virial_implemented": False,
    "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
}

VALIDATION_CONTRACT = {
    "all_twelve_axes_analytic_force_central_difference": True,
    "auto_backend_fails_closed_before_input_access": True,
    "canonical_vendor_byte_identity": True,
    "charge_inversion_invariance": True,
    "cpp_and_rust_parent_composition_parity": True,
    "cpp_rust_energy_and_force_mixed_tolerance": {
        "absolute_tolerance": 5e-12,
        "formula": (
            "abs(observed - expected) <= absolute_tolerance + "
            "relative_tolerance * max(abs(observed), abs(expected))"
        ),
        "relative_tolerance": 5e-12,
    },
    "descriptor_initializer_transactionality": True,
    "direct_reciprocal_bound_independence": True,
    "energy_component_count": 5,
    "energy_only_bit_identity": True,
    "evaluation_failure_output_transactionality": True,
    "exact_atom_unit_cell_alpha_dielectric_compatibility": True,
    "explicit_cpu_requested_resolved_identity": True,
    "force_component_count": 12,
    "rust_cpu_frozen_fixture_total_bits_hex": "c0186145396def20",
    "hip_backends_fail_closed_without_device_execution": True,
    "mach_o_public_export_allowlist_enforced": True,
    "mesh_8_16_32_direct_total_approach_observed": True,
    "pair_exclusion_and_scaled_pair_provenance": True,
    "periodic_image_invariance": True,
    "public_symbol_version_enforced": True,
    "required_null_alias_suppresses_typed_error_write": True,
    "required_null_input_clears_valid_typed_error": True,
    "rust_safe_runtime_both_cpu_lanes": True,
    "rust_sys_c11_and_cpp_layout_probes": True,
    "same_lane_bitwise_repeatability": True,
    "stable_atom_permutation": True,
    "stale_typed_error_cleared_before_write_safe_untyped_failure": True,
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

OPERATIONAL_BOUNDARY = {
    "blockers": [
        "external_reservation_endpoint_not_configured",
        "external_reservation_provider_not_operational",
        "external_reservation_trust_anchor_not_configured",
        "historical_execution_operational_authority_false",
    ],
    "unresolved_operational_decisions": 32,
}

REQUIRED_SOURCE_PATHS = (
    Path(".github/workflows/ci-engine-v2-native-particle-mesh-ewald.yml"),
    Path(".github/workflows/ci-engine-v2-native-particle-mesh-reciprocal.yml"),
    Path("CMakeLists.txt"),
    Path("docs/engine_v2_native_particle_mesh_ewald_cpu_v1.md"),
    Path("include/betelgeuze/engine.h"),
    Path("include/betelgeuze/direct_ewald.h"),
    Path("include/betelgeuze/particle_mesh_reciprocal.h"),
    Path("include/betelgeuze/particle_mesh_ewald.h"),
    Path("native/CMakeLists.txt"),
    Path("native/betelgeuze_engine.exports"),
    Path("native/betelgeuze_engine.map"),
    Path("native/src/context.cpp"),
    Path("native/src/internal.hpp"),
    Path("native/src/system.cpp"),
    Path("native/src/composite/particle_mesh_ewald.cpp"),
    Path("native/tests/check_exports.cmake"),
    Path("native/tests/particle_mesh_ewald.cpp"),
    Path("rust/Cargo.lock"),
    Path("rust/Cargo.toml"),
    Path("rust/cpu-kernel/Cargo.toml"),
    Path("rust/cpu-kernel/src/lib.rs"),
    Path("rust/cpu-kernel/src/direct_ewald.rs"),
    Path("rust/cpu-kernel/src/particle_mesh_reciprocal.rs"),
    Path("rust/betelgeuze-sys/Cargo.toml"),
    Path("rust/betelgeuze-sys/build.rs"),
    Path("rust/betelgeuze-sys/src/lib.rs"),
    Path("rust/betelgeuze-sys/tests/layout.rs"),
    Path("rust/betelgeuze-sys/tests/raw_smoke.rs"),
    Path("rust/betelgeuze-sys/abi/particle_mesh_ewald_header_c11.c"),
    Path("rust/betelgeuze-sys/abi/particle_mesh_ewald_layout_assertions.cpp"),
    Path("rust/betelgeuze-runtime/Cargo.toml"),
    Path("rust/betelgeuze-runtime/build.rs"),
    Path("rust/betelgeuze-runtime/src/lib.rs"),
    Path("rust/betelgeuze-runtime/src/direct_ewald.rs"),
    Path("rust/betelgeuze-runtime/src/particle_mesh_reciprocal.rs"),
    Path("rust/betelgeuze-runtime/src/particle_mesh_ewald.rs"),
    Path("rust/betelgeuze-runtime/tests/particle_mesh_ewald.rs"),
    Path("rust/betelgeuze-runtime/tests/fixtures/direct_ewald_v1.tsv"),
    Path("rust/betelgeuze-runtime/tests/fixtures/particle_mesh_reciprocal_v1.tsv"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze/engine.h"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze/direct_ewald.h"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze/particle_mesh_reciprocal.h"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze/particle_mesh_ewald.h"),
    Path("rust/betelgeuze-sys/vendor/native/src/context.cpp"),
    Path("rust/betelgeuze-sys/vendor/native/src/internal.hpp"),
    Path("rust/betelgeuze-sys/vendor/native/src/system.cpp"),
    Path("rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald.cpp"),
    Path("rust_engine_v2/Cargo.lock"),
    Path("rust_engine_v2/Cargo.toml"),
    Path("tests/unit/test_engine_v2_native_particle_mesh_ewald_cpu_v1.py"),
    Path("tests/unit/test_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py"),
    Path("tools/__init__.py"),
    Path("tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py"),
    Path("tools/verify_engine_v2_native_particle_mesh_ewald_cpu_v1.py"),
)

SOURCE_DIRECTORIES = (
    Path("native/src/ewald"),
    Path("native/src/particle_mesh_reciprocal"),
    Path("rust/betelgeuze-sys/vendor/native/src/ewald"),
    Path("rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal"),
)


class NativeParticleMeshEwaldCPUProfileV1Error(ValueError):
    """Evidence is missing, noncanonical, or outside the frozen contract."""


def _fail(detail: str) -> NoReturn:
    raise NativeParticleMeshEwaldCPUProfileV1Error(detail)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "ascii"
    )


def _canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(f"{label} is not valid UTF-8 JSON: {error}")
    if not isinstance(value, dict):
        _fail(f"{label} must be a JSON object")
    if canonical_bytes(value) != raw:
        _fail(f"{label} is not canonical sorted ASCII JSON")
    return value


def discover_source_paths(root: Path) -> tuple[Path, ...]:
    paths = set(REQUIRED_SOURCE_PATHS)
    for directory in SOURCE_DIRECTORIES:
        absolute = root / directory
        if not absolute.is_dir():
            _fail(f"required source directory is missing: {directory}")
        paths.update(path.relative_to(root) for path in absolute.rglob("*") if path.is_file())
    for relative in paths:
        absolute = root / relative
        if not absolute.is_file() or absolute.is_symlink():
            _fail(f"required regular source file is missing: {relative}")
    if PROFILE_RELATIVE_PATH in paths or SOURCE_MANIFEST_RELATIVE_PATH in paths:
        _fail("profile or source manifest entered its own hash closure")
    return tuple(sorted(paths, key=lambda path: path.as_posix()))


def build_source_manifest(root: Path) -> dict[str, object]:
    rows = []
    for relative in discover_source_paths(root):
        raw = (root / relative).read_bytes()
        rows.append(
            {
                "byte_count": len(raw),
                "path": relative.as_posix(),
                "sha256": _sha256(raw),
            }
        )
    return {"files": rows, "schema_id": SOURCE_SCHEMA_ID, "scope": SOURCE_SCOPE}


def require_source_manifest(
    root: Path, raw: bytes
) -> tuple[dict[str, object], dict[str, bytes]]:
    manifest = _canonical_object(raw, label="source manifest")
    if set(manifest) != {"files", "schema_id", "scope"}:
        _fail("source manifest keys changed")
    if manifest["schema_id"] != SOURCE_SCHEMA_ID or manifest["scope"] != SOURCE_SCOPE:
        _fail("source manifest identity changed")
    rows = manifest["files"]
    if not isinstance(rows, list):
        _fail("source manifest files must be a list")
    expected_paths = [path.as_posix() for path in discover_source_paths(root)]
    observed_paths = [row.get("path") if isinstance(row, dict) else None for row in rows]
    if any(not isinstance(path, str) for path in observed_paths):
        _fail("source manifest rows must contain string paths")
    if observed_paths != expected_paths or observed_paths != sorted(set(observed_paths)):
        _fail("source manifest path closure must be exact, sorted, and unique")
    sources: dict[str, bytes] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"byte_count", "path", "sha256"}:
            _fail("source manifest row shape changed")
        path = row["path"]
        digest = row["sha256"]
        if not isinstance(path, str) or not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            _fail("source manifest row has an invalid path or digest")
        payload = (root / path).read_bytes()
        if row["byte_count"] != len(payload) or digest != _sha256(payload):
            _fail(f"source bytes drifted: {path}")
        sources[path] = payload
    if manifest != build_source_manifest(root):
        _fail("source manifest differs from the current exact closure")
    _require_source_contract(sources)
    return manifest, sources


def _text(sources: dict[str, bytes], path: str) -> str:
    try:
        return sources[path].decode("utf-8")
    except UnicodeDecodeError:
        _fail(f"required source is not UTF-8: {path}")


def _require_tokens(text: str, tokens: tuple[str, ...], *, label: str) -> None:
    for token in tokens:
        if token not in text:
            _fail(f"{label} is missing required contract token: {token}")


def _require_source_contract(sources: dict[str, bytes]) -> None:
    canonical_header = sources["include/betelgeuze/particle_mesh_ewald.h"]
    vendor_header = sources[
        "rust/betelgeuze-sys/vendor/include/betelgeuze/particle_mesh_ewald.h"
    ]
    canonical_source = sources["native/src/composite/particle_mesh_ewald.cpp"]
    vendor_source = sources[
        "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald.cpp"
    ]
    if canonical_header != vendor_header or canonical_source != vendor_source:
        _fail("canonical and vendored particle-mesh Ewald bytes differ")

    header = canonical_header.decode("utf-8")
    _require_tokens(
        header,
        (
            '#include "betelgeuze/direct_ewald.h"',
            '#include "betelgeuze/particle_mesh_reciprocal.h"',
            "BG_PARTICLE_MESH_EWALD_ABI_VERSION",
            "bg_particle_mesh_ewald_energy_components_v1",
            "bg_particle_mesh_ewald_force_soa_v1",
            *PUBLIC_SYMBOLS,
        ),
        label="public header",
    )
    source = canonical_source.decode("utf-8")
    _require_tokens(
        source,
        (
            "betelgeuze.native_particle_mesh_ewald/1.0.0",
            "reciprocal_max_indices",
            "BG_BACKEND_CPP_CPU_REFERENCE",
            "BG_BACKEND_RUST_CPU",
            "requested_backend",
            "context->backend != lane",
            "cpp_cpu::evaluate",
            "rust_cpu::evaluate",
            "particle_mesh_reciprocal",
            "real_space",
            "pair_correction",
        ),
        label="native composition",
    )
    native_test = _text(sources, "native/tests/particle_mesh_ewald.cpp")
    _require_tokens(
        native_test,
        (
            "verify_exact_parent_composition",
            "verify_mesh_8_16_32_approaches_direct_total",
            "verify_direct_reciprocal_bounds_are_ignored",
            "verify_all_force_finite_differences",
            "verify_transformations_and_pair_rules",
            "BG_BACKEND_AUTO, BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST",
            "BG_STATUS_ABI_MISMATCH",
            "5.0e-12",
        ),
        label="native composition tests",
    )

    direct_kernel = _text(sources, "rust/cpu-kernel/src/direct_ewald.rs")
    _require_tokens(
        direct_kernel,
        (
            "reciprocal_max_indices != [0; 3]",
            "internal_all_zero_reciprocal_bounds_preserve_local_terms_and_forces",
            "mixed_zero_reciprocal_bounds_remain_invalid",
        ),
        label="internal direct-Ewald local-only sentinel",
    )

    cmake = _text(sources, "native/CMakeLists.txt")
    _require_tokens(
        cmake,
        (
            "src/composite/particle_mesh_ewald.cpp",
            "tests/particle_mesh_ewald.cpp",
            "include/betelgeuze/particle_mesh_ewald.h",
            "betelgeuze_engine_particle_mesh_ewald",
        ),
        label="native CMake integration",
    )
    exports = _text(sources, "native/betelgeuze_engine.exports")
    version_map = _text(sources, "native/betelgeuze_engine.map")
    export_test = _text(sources, "native/tests/check_exports.cmake")
    for symbol in PUBLIC_SYMBOLS:
        if f"_{symbol}\n" not in exports:
            _fail(f"Mach-O export allowlist is missing {symbol}")
        if symbol not in version_map or symbol not in export_test:
            _fail(f"ELF/export test contract is missing {symbol}")
    _require_tokens(
        version_map,
        (
            "BETELGEUZE_PARTICLE_MESH_EWALD_1.0",
            "BETELGEUZE_PARTICLE_MESH_RECIPROCAL_1.0;",
        ),
        label="ELF version node",
    )

    sys_lib = _text(sources, "rust/betelgeuze-sys/src/lib.rs")
    runtime = _text(sources, "rust/betelgeuze-runtime/src/particle_mesh_ewald.rs")
    _require_tokens(
        sys_lib,
        (
            "BG_PARTICLE_MESH_EWALD_ABI_VERSION",
            "bg_particle_mesh_ewald_energy_components_v1",
            "bg_particle_mesh_ewald_force_soa_v1",
            *PUBLIC_SYMBOLS,
        ),
        label="Rust sys binding",
    )
    _require_tokens(
        runtime,
        (
            "evaluate_particle_mesh_ewald",
            "evaluate_particle_mesh_ewald_energy",
            "ParticleMeshEwaldEnergyComponents",
            "ParticleMeshReciprocalModel",
            "DirectEwaldModel",
            "requested_backend",
        ),
        label="safe Rust runtime",
    )
    runtime_test = _text(sources, "rust/betelgeuze-runtime/tests/particle_mesh_ewald.rs")
    _require_tokens(
        runtime_test,
        ("c018_6145_396d_ef20", "CppCpuReference", "RustCpu", "energy"),
        label="safe runtime tests",
    )

    production_inputs = (
        "native/CMakeLists.txt",
        "rust/betelgeuze-sys/Cargo.toml",
        "rust/betelgeuze-runtime/Cargo.toml",
        "rust_engine_v2/Cargo.toml",
    )
    for path in production_inputs:
        lowered = _text(sources, path).lower()
        if "reference-pme" in lowered or "reference-ewald" in lowered:
            _fail(f"independent reference entered production inputs: {path}")

    legacy_workflow = _text(
        sources, ".github/workflows/ci-engine-v2-native-particle-mesh-reciprocal.yml"
    )
    _require_tokens(
        legacy_workflow,
        (
            "frozen=735883551510cbef91adc3e57dc131a1234b67fb",
            "frozen_tree=6c2b6f3960b6df0592b78bb44e429389aa58bcbb",
            'git diff --exit-code "$frozen" --',
            'git checkout --detach --quiet "$frozen"',
            'git checkout --detach --quiet "$current_sha"',
        ),
        label="legacy reciprocal frozen-object workflow",
    )
    if "--refresh" in legacy_workflow:
        _fail("legacy reciprocal workflow must never refresh frozen evidence")
    legacy_unit = _text(
        sources, "tests/unit/test_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py"
    )
    _require_tokens(
        legacy_unit,
        (
            "pytest.mark.skipif(",
            "engine_v2_native_particle_mesh_ewald_cpu_profile_v1.json",
            "verify_engine_v2_native_particle_mesh_ewald_cpu_v1.py",
            "exact frozen object",
        ),
        label="legacy reciprocal descendant-aware unit",
    )

    workflow = _text(
        sources, ".github/workflows/ci-engine-v2-native-particle-mesh-ewald.yml"
    )
    _require_tokens(
        workflow,
        (
            "permissions:\n  contents: read",
            "fetch-depth: 0",
            "HIP_VISIBLE_DEVICES: \"\"",
            "verify_engine_v2_native_particle_mesh_ewald_cpu_v1.py",
            "test_engine_v2_native_particle_mesh_ewald_cpu_v1.py",
            "betelgeuze_engine_export_allowlist",
            "735883551510cbef91adc3e57dc131a1234b67fb",
            "074d3b71373088c0738de7a14797fe35d66d986e",
            "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1",
            "patch.crates-io.betelgeuze-sys.path",
        ),
        label="new evidence workflow",
    )


def _git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", *arguments], cwd=root, check=False, capture_output=True
    )
    if result.returncode != 0:
        _fail(
            f"git {' '.join(arguments)} failed: "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return result.stdout


def require_frozen_parent_objects(root: Path) -> None:
    for commit, contract in FROZEN_OBJECTS.items():
        tree = _git(root, "rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()
        if tree != contract["tree"]:
            _fail(f"frozen parent tree changed: {commit}")
        files = contract["files"]
        assert isinstance(files, dict)
        for path, expected in files.items():
            payload = _git(root, "show", f"{commit}:{path}")
            if _sha256(payload) != expected:
                _fail(f"frozen parent artifact changed: {commit}:{path}")


def build_profile(*, manifest_raw: bytes, source_count: int) -> dict[str, object]:
    implementation = dict(IMPLEMENTATION_CONTRACT_BASE)
    implementation["source_manifest_entry_count"] = source_count
    implementation["source_manifest_sha256"] = _sha256(manifest_raw)
    return {
        "abi": ABI_CONTRACT,
        "authority": AUTHORITY_CONTRACT,
        "implementation": implementation,
        "operational_boundary": OPERATIONAL_BOUNDARY,
        "parent_references": PARENT_REFERENCES,
        "profile_id": PROFILE_ID,
        "roadmap_issue": 434,
        "schema_id": SCHEMA_ID,
        "validation": VALIDATION_CONTRACT,
    }


def require_profile(
    raw: bytes, *, source_manifest_raw: bytes, source_count: int
) -> dict[str, object]:
    profile = _canonical_object(raw, label="profile")
    expected = build_profile(
        manifest_raw=source_manifest_raw, source_count=source_count
    )
    if profile != expected:
        _fail("profile contract or source binding changed")
    return profile


def verify(root: Path = ROOT) -> dict[str, object]:
    manifest_raw = (root / SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest, _ = require_source_manifest(root, manifest_raw)
    rows = manifest["files"]
    assert isinstance(rows, list)
    profile_raw = (root / PROFILE_RELATIVE_PATH).read_bytes()
    require_profile(
        profile_raw, source_manifest_raw=manifest_raw, source_count=len(rows)
    )
    require_frozen_parent_objects(root)
    return {
        "profile_path": PROFILE_RELATIVE_PATH.as_posix(),
        "profile_sha256": _sha256(profile_raw),
        "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
        "source_manifest_sha256": _sha256(manifest_raw),
        "source_count": len(rows),
        "frozen_parent_count": len(FROZEN_OBJECTS),
        "authority": AUTHORITY_CONTRACT,
        "operational_boundary": OPERATIONAL_BOUNDARY,
    }


def refresh(root: Path = ROOT) -> dict[str, object]:
    manifest = build_source_manifest(root)
    manifest_raw = canonical_bytes(manifest)
    (root / SOURCE_MANIFEST_RELATIVE_PATH).write_bytes(manifest_raw)
    rows = manifest["files"]
    assert isinstance(rows, list)
    profile = build_profile(manifest_raw=manifest_raw, source_count=len(rows))
    (root / PROFILE_RELATIVE_PATH).write_bytes(canonical_bytes(profile))
    return verify(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    try:
        report = refresh(ROOT) if arguments.refresh else verify(ROOT)
    except (OSError, NativeParticleMeshEwaldCPUProfileV1Error) as error:
        print(f"particle-mesh Ewald evidence verification failed: {error}", file=sys.stderr)
        return 1
    if arguments.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "particle-mesh Ewald evidence verified: "
            f"profile={report['profile_sha256']} "
            f"manifest={report['source_manifest_sha256']} "
            f"sources={report['source_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
