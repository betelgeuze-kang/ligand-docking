#!/usr/bin/env python3
"""Verify bounded stateless short-range + particle-mesh Ewald CPU v1 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1_sources.json"
)
SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_cpu_profile/1.0.0"
)
PROFILE_ID = "engine_v2_native_particle_mesh_ewald_composite_cpu_development_v1"
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_cpu_sources/1.0.0"
)
SOURCE_SCOPE = (
    "particle_mesh_ewald_composite_v1_owned_sources_bindings_tests_and_frozen_parents"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

PUBLIC_SYMBOLS = (
    "bg_particle_mesh_ewald_composite_abi_version",
    "bg_particle_mesh_ewald_composite_abi_version_major",
    "bg_particle_mesh_ewald_composite_abi_version_minor",
    "bg_particle_mesh_ewald_composite_abi_version_string",
    "bg_particle_mesh_ewald_composite_energy_components_v1_init",
    "bg_particle_mesh_ewald_composite_force_soa_v1_init",
    "bg_particle_mesh_ewald_composite_v1_profile_id",
    "bg_context_evaluate_particle_mesh_ewald_composite_v1",
)

PARENT_REFERENCES = {
    "native_direct_ewald_composite": {
        "merge_commit": "f2731176fb913f600349ec6a1fbf3678d399a7c1",
        "merge_tree": "6017cf05e3f437443371966775bb4deb3fc73cab",
        "profile_path": (
            "config/engine_v2_native_direct_ewald_composite_profile_v1.json"
        ),
        "profile_sha256": (
            "31dc3535d915980b1a7c318839162a4ce62d6a8bbf221b3415a67a98677d57e7"
        ),
        "pull_request": 437,
        "reviewed_head": "454bb9ee6cdb4202cecbc807f78503ce842bdd13",
        "source_manifest_entry_count": 73,
        "source_manifest_path": (
            "config/engine_v2_native_direct_ewald_composite_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "53267e95900402f60f4aba13a674e0e9530291d68310765d1a35a17146bf6afb"
        ),
    },
    "native_particle_mesh_ewald": {
        "merge_commit": "e228f376857ead900bd1ae99cf5b111c8b40cf34",
        "merge_tree": "ae0a6eddd44262eeec633c57a0f5566bf7989361",
        "profile_path": (
            "config/engine_v2_native_particle_mesh_ewald_cpu_profile_v1.json"
        ),
        "profile_sha256": (
            "56c09a61a369fdcebe1e0302ef62fdff51352425529d36d77f7cbce8c3ab9b75"
        ),
        "pull_request": 441,
        "reviewed_head": "59ad72fe57e82106a71df2c88c63c9fe12d014ad",
        "source_manifest_entry_count": 82,
        "source_manifest_path": (
            "config/engine_v2_native_particle_mesh_ewald_cpu_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "c8d04affddc8d968a9b1f7eba7895d09513e375f05461a326d72873bbad2b185"
        ),
    },
}

FROZEN_OBJECTS = {
    reference["merge_commit"]: {
        "tree": reference["merge_tree"],
        "profile_path": reference["profile_path"],
        "profile_sha256": reference["profile_sha256"],
        "source_manifest_entry_count": reference["source_manifest_entry_count"],
        "source_manifest_path": reference["source_manifest_path"],
        "source_manifest_sha256": reference["source_manifest_sha256"],
    }
    for reference in PARENT_REFERENCES.values()
}

ABI_CONTRACT = {
    "abi_version": 1,
    "abi_version_major": 1,
    "abi_version_minor": 0,
    "abi_version_string": "1.0.0",
    "borrowed_handle_count": 5,
    "energy_component_count": 12,
    "energy_layout_size_64_bit": 144,
    "engine_abi_reserved_fields_repurposed": False,
    "engine_abi_version_changed": False,
    "error_layout": "bg_direct_ewald_error_v1",
    "force_layout_size_64_bit": 88,
    "frozen_parent_abis_changed": False,
    "header": "include/betelgeuze/particle_mesh_ewald_composite.h",
    "profile_id": "betelgeuze.native_particle_mesh_ewald_composite/1.0.0",
    "public_symbol_count": 8,
    "separately_versioned_stateless_boundary": True,
    "symbol_version_node": "BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_1.0",
    "symbol_version_parent": "BETELGEUZE_PARTICLE_MESH_EWALD_1.0",
}

IMPLEMENTATION_CONTRACT_BASE = {
    "caller_system_mutated": False,
    "cpp_cpu_reference_lane": True,
    "development_exact_neutral_four_atom_fixture_only": True,
    "direct_reciprocal_bounds_ignored": True,
    "energy_only_allocates_or_accumulates_forces": False,
    "external_md_engine_dependency": False,
    "fixed64_cpu_v7_qualification_invoked": False,
    "hip_device_implementation": False,
    "hip_device_execution_invoked": False,
    "hip_to_cpu_fallback": False,
    "independent_parent_references_linked_into_production": False,
    "molecular_execution_invoked": False,
    "new_model_ownership_introduced": False,
    "pair_rule_provenance_preserved": True,
    "particle_mesh_ewald_parent_uses_original_charges": True,
    "rust_cpu_lane": True,
    "rust_cpu_runtime_fixture_total_bits_hex": "4012dc3129bce12e",
    "shared_runtime_dynamics_integrated": False,
    "short_range_uses_positive_zero_charge_copy": True,
    "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "stateful_checkpoint_integrated": False,
    "virial_implemented": False,
    "whole_call_transactional_commit": True,
}

VALIDATION_CONTRACT = {
    "all_twelve_axes_analytic_force_central_difference": True,
    "auto_backend_fails_closed_before_input_access": True,
    "caller_system_unchanged": True,
    "canonical_vendor_byte_identity": True,
    "charge_inversion_invariance": True,
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
    "energy_component_count": 12,
    "energy_only_bit_identity": True,
    "evaluation_failure_output_transactionality": True,
    "exact_atom_unit_cell_alpha_dielectric_compatibility": True,
    "exact_parent_component_and_force_sum": True,
    "explicit_cpu_requested_resolved_identity": True,
    "force_component_count": 12,
    "hip_backends_fail_closed_without_device_execution": True,
    "mach_o_public_export_allowlist_enforced": True,
    "mesh_8_16_32_direct_composite_total_approach_observed": True,
    "pair_exclusion_and_scaled_pair_provenance": True,
    "periodic_image_invariance": True,
    "public_symbol_version_enforced": True,
    "required_null_alias_suppresses_typed_error_write": True,
    "required_null_input_clears_valid_typed_error": True,
    "rust_cpu_frozen_fixture_total_bits_hex": "4012dc3129bce12e",
    "rust_safe_runtime_both_cpu_lanes": True,
    "rust_sys_c11_and_cpp_layout_probes": True,
    "same_lane_bitwise_repeatability": True,
    "stable_atom_permutation": True,
    "stale_typed_error_cleared_before_write_safe_untyped_failure": True,
    "translation_invariance": True,
}

AUTHORITY_CONTRACT = {
    "acceleration_claim_authorized": False,
    "d1_d2_execution_authorized": False,
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
    Path(".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite.yml"),
    Path(".github/workflows/ci-engine-v2-native-particle-mesh-ewald.yml"),
    Path("CMakeLists.txt"),
    Path("docs/engine_v2_native_particle_mesh_ewald_composite_cpu_v1.md"),
    Path("include/betelgeuze/direct_ewald.h"),
    Path("include/betelgeuze/direct_ewald_composite.h"),
    Path("include/betelgeuze/engine.h"),
    Path("include/betelgeuze/particle_mesh_ewald.h"),
    Path("include/betelgeuze/particle_mesh_ewald_composite.h"),
    Path("include/betelgeuze/particle_mesh_reciprocal.h"),
    Path("native/CMakeLists.txt"),
    Path("native/betelgeuze_engine.exports"),
    Path("native/betelgeuze_engine.map"),
    Path("native/src/composite/direct_ewald.cpp"),
    Path("native/src/composite/evaluator.hpp"),
    Path("native/src/composite/particle_mesh_ewald.cpp"),
    Path("native/src/composite/particle_mesh_ewald_composite.cpp"),
    Path("native/src/context.cpp"),
    Path("native/src/cpu/evaluator.cpp"),
    Path("native/src/cpu/evaluator.hpp"),
    Path("native/src/cpu/neighbor_pair.hpp"),
    Path("native/src/evaluator.cpp"),
    Path("native/src/forcefield.cpp"),
    Path("native/src/internal.hpp"),
    Path("native/src/rust/evaluator.cpp"),
    Path("native/src/rust/evaluator.hpp"),
    Path("native/src/rust/provider.h"),
    Path("native/src/system.cpp"),
    Path("native/tests/check_exports.cmake"),
    Path("native/tests/particle_mesh_ewald_composite.cpp"),
    Path("rust/Cargo.lock"),
    Path("rust/Cargo.toml"),
    Path("rust/cpu-kernel/Cargo.toml"),
    Path("rust/cpu-kernel/src/direct_ewald.rs"),
    Path("rust/cpu-kernel/src/kernel.rs"),
    Path("rust/cpu-kernel/src/lib.rs"),
    Path("rust/cpu-kernel/src/particle_mesh_reciprocal.rs"),
    Path("rust/betelgeuze-sys/Cargo.toml"),
    Path("rust/betelgeuze-sys/build.rs"),
    Path("rust/betelgeuze-sys/src/lib.rs"),
    Path("rust/betelgeuze-sys/tests/layout.rs"),
    Path("rust/betelgeuze-sys/tests/raw_smoke.rs"),
    Path("rust/betelgeuze-sys/abi/particle_mesh_ewald_composite_header_c11.c"),
    Path("rust/betelgeuze-sys/abi/particle_mesh_ewald_composite_layout_assertions.cpp"),
    Path("rust/betelgeuze-sys/abi/particle_mesh_ewald_header_c11.c"),
    Path("rust/betelgeuze-sys/abi/particle_mesh_ewald_layout_assertions.cpp"),
    Path("rust/betelgeuze-runtime/Cargo.toml"),
    Path("rust/betelgeuze-runtime/build.rs"),
    Path("rust/betelgeuze-runtime/src/composite.rs"),
    Path("rust/betelgeuze-runtime/src/direct_ewald.rs"),
    Path("rust/betelgeuze-runtime/src/forcefield.rs"),
    Path("rust/betelgeuze-runtime/src/lib.rs"),
    Path("rust/betelgeuze-runtime/src/particle_mesh_ewald.rs"),
    Path("rust/betelgeuze-runtime/src/particle_mesh_ewald_composite.rs"),
    Path("rust/betelgeuze-runtime/src/particle_mesh_reciprocal.rs"),
    Path("rust/betelgeuze-runtime/tests/fixtures/direct_ewald_v1.tsv"),
    Path("rust/betelgeuze-runtime/tests/fixtures/particle_mesh_reciprocal_v1.tsv"),
    Path("rust/betelgeuze-runtime/tests/particle_mesh_ewald_composite.rs"),
    Path("rust_engine_v2/Cargo.lock"),
    Path("rust_engine_v2/Cargo.toml"),
    Path("tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py"),
    Path("tests/unit/test_engine_v2_native_particle_mesh_ewald_cpu_v1.py"),
    Path("tools/__init__.py"),
    Path("tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py"),
    Path("tools/verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py"),
)

SOURCE_DIRECTORIES = (
    Path("native/src/ewald"),
    Path("native/src/particle_mesh_reciprocal"),
    Path("rust/betelgeuze-sys/vendor/native/src/ewald"),
    Path("rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal"),
)

VENDOR_IDENTICAL_PATHS = (
    "include/betelgeuze/direct_ewald.h",
    "include/betelgeuze/direct_ewald_composite.h",
    "include/betelgeuze/engine.h",
    "include/betelgeuze/particle_mesh_ewald.h",
    "include/betelgeuze/particle_mesh_ewald_composite.h",
    "include/betelgeuze/particle_mesh_reciprocal.h",
    "native/src/composite/direct_ewald.cpp",
    "native/src/composite/evaluator.hpp",
    "native/src/composite/particle_mesh_ewald.cpp",
    "native/src/composite/particle_mesh_ewald_composite.cpp",
    "native/src/context.cpp",
    "native/src/cpu/evaluator.cpp",
    "native/src/cpu/evaluator.hpp",
    "native/src/cpu/neighbor_pair.hpp",
    "native/src/evaluator.cpp",
    "native/src/ewald/api.cpp",
    "native/src/ewald/cpp_evaluator.cpp",
    "native/src/ewald/cpp_evaluator.hpp",
    "native/src/ewald/model.hpp",
    "native/src/ewald/rust_evaluator.cpp",
    "native/src/ewald/rust_evaluator.hpp",
    "native/src/ewald/rust_provider.h",
    "native/src/forcefield.cpp",
    "native/src/internal.hpp",
    "native/src/particle_mesh_reciprocal/api.cpp",
    "native/src/particle_mesh_reciprocal/cpp_evaluator.cpp",
    "native/src/particle_mesh_reciprocal/cpp_evaluator.hpp",
    "native/src/particle_mesh_reciprocal/model.hpp",
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp",
    "native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
    "native/src/particle_mesh_reciprocal/rust_provider.h",
    "native/src/rust/evaluator.cpp",
    "native/src/rust/evaluator.hpp",
    "native/src/rust/provider.h",
    "native/src/system.cpp",
)


class NativeParticleMeshEwaldCompositeCPUProfileV1Error(ValueError):
    """Composite evidence is missing, noncanonical, or outside the contract."""


def _fail(detail: str) -> NoReturn:
    raise NativeParticleMeshEwaldCompositeCPUProfileV1Error(detail)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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


def _canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise NativeParticleMeshEwaldCompositeCPUProfileV1Error(
            f"{label} is not canonical ASCII JSON"
        ) from error
    if type(value) is not dict or canonical_bytes(value) != raw:
        _fail(f"{label} is not canonical sorted ASCII JSON")
    return value


def _regular_file(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        _fail(f"required regular source file is missing: {relative}")
    return path


def discover_source_paths(root: Path) -> tuple[Path, ...]:
    paths = set(REQUIRED_SOURCE_PATHS)
    paths.update(
        Path("rust/betelgeuze-sys/vendor") / Path(path)
        for path in VENDOR_IDENTICAL_PATHS
    )
    for directory in SOURCE_DIRECTORIES:
        absolute = root / directory
        if absolute.is_symlink() or not absolute.is_dir():
            _fail(f"required source directory is missing: {directory}")
        for path in absolute.rglob("*"):
            if path.is_symlink():
                _fail(f"source directory contains a symlink: {path.relative_to(root)}")
            if path.is_file():
                paths.add(path.relative_to(root))
    if PROFILE_RELATIVE_PATH in paths or SOURCE_MANIFEST_RELATIVE_PATH in paths:
        _fail("profile or source manifest entered its own hash closure")
    for relative in paths:
        _regular_file(root, relative)
    return tuple(sorted(paths, key=lambda path: path.as_posix()))


def build_source_manifest(root: Path) -> dict[str, object]:
    files = []
    for relative in discover_source_paths(root):
        raw = _regular_file(root, relative).read_bytes()
        files.append(
            {
                "byte_count": len(raw),
                "path": relative.as_posix(),
                "sha256": _sha256(raw),
            }
        )
    return {"files": files, "schema_id": SOURCE_SCHEMA_ID, "scope": SOURCE_SCOPE}


def require_source_manifest(
    root: Path, raw: bytes
) -> tuple[dict[str, object], dict[str, bytes]]:
    manifest = _canonical_object(raw, label="source manifest")
    if set(manifest) != {"files", "schema_id", "scope"}:
        _fail("source manifest keys changed")
    if manifest["schema_id"] != SOURCE_SCHEMA_ID or manifest["scope"] != SOURCE_SCOPE:
        _fail("source manifest identity changed")
    rows = manifest["files"]
    if type(rows) is not list or not rows:
        _fail("source manifest files must be a non-empty list")
    expected_paths = [path.as_posix() for path in discover_source_paths(root)]
    observed_paths: list[str] = []
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != {"byte_count", "path", "sha256"}:
            _fail(f"source manifest row {index} shape changed")
        path = row["path"]
        byte_count = row["byte_count"]
        digest = row["sha256"]
        if type(path) is not str or not path:
            _fail(f"source manifest row {index} path is invalid")
        relative = Path(path)
        if (
            relative.is_absolute()
            or relative.as_posix() != path
            or ".." in relative.parts
        ):
            _fail(f"source manifest row {index} path is not normalized")
        if type(byte_count) is not int or byte_count < 0:
            _fail(f"source manifest row {index} byte count is invalid")
        if type(digest) is not str or SHA256_PATTERN.fullmatch(digest) is None:
            _fail(f"source manifest row {index} digest is invalid")
        observed_paths.append(path)
    if (
        observed_paths != sorted(set(observed_paths))
        or observed_paths != expected_paths
    ):
        _fail("source manifest path closure must be exact, sorted, and unique")
    sources: dict[str, bytes] = {}
    for row in rows:
        assert isinstance(row, dict)
        path = str(row["path"])
        payload = _regular_file(root, Path(path)).read_bytes()
        if (
            row["byte_count"] != len(payload)
            or row["sha256"] != _sha256(payload)
        ):
            _fail(f"source bytes drifted: {path}")
        sources[path] = payload
    if manifest != build_source_manifest(root):
        _fail("source manifest differs from the current exact closure")
    _require_source_contract(sources)
    return manifest, sources


def _text(sources: dict[str, bytes], path: str) -> str:
    try:
        return sources[path].decode("utf-8")
    except KeyError as error:
        raise NativeParticleMeshEwaldCompositeCPUProfileV1Error(
            f"required composite source is unbound: {path}"
        ) from error
    except UnicodeError as error:
        raise NativeParticleMeshEwaldCompositeCPUProfileV1Error(
            f"required composite source is not UTF-8: {path}"
        ) from error


def _require_tokens(text: str, tokens: tuple[str, ...], *, label: str) -> None:
    for token in tokens:
        if token not in text:
            _fail(f"{label} is missing required contract token: {token}")


def _require_source_contract(sources: dict[str, bytes]) -> None:
    for canonical in VENDOR_IDENTICAL_PATHS:
        vendor = f"rust/betelgeuze-sys/vendor/{canonical}"
        if vendor not in sources or sources[canonical] != sources[vendor]:
            _fail(f"canonical and vendored composite bytes differ: {canonical}")

    header = _text(sources, "include/betelgeuze/particle_mesh_ewald_composite.h")
    _require_tokens(
        header,
        (
            '#include "betelgeuze/particle_mesh_ewald.h"',
            "BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MAJOR UINT32_C(1)",
            "BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MINOR UINT32_C(0)",
            "typedef struct bg_particle_mesh_ewald_composite_energy_components_v1",
            "typedef struct bg_particle_mesh_ewald_composite_force_soa_v1",
            "bg_direct_ewald_error_v1 *out_error",
            *PUBLIC_SYMBOLS,
        ),
        label="public composite header",
    )
    component_fields = (
        "double short_harmonic_bond_kcal_per_mol;",
        "double short_harmonic_angle_kcal_per_mol;",
        "double short_periodic_torsion_kcal_per_mol;",
        "double short_lennard_jones_kcal_per_mol;",
        "double short_coulomb_kcal_per_mol;",
        "double short_total_kcal_per_mol;",
        "double pme_real_space_kcal_per_mol;",
        "double pme_reciprocal_space_kcal_per_mol;",
        "double pme_self_kcal_per_mol;",
        "double pme_pair_correction_kcal_per_mol;",
        "double pme_total_kcal_per_mol;",
        "double total_kcal_per_mol;",
    )
    positions = [header.find(field) for field in component_fields]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        _fail("public composite energy component order changed")

    implementation = _text(
        sources, "native/src/composite/particle_mesh_ewald_composite.cpp"
    )
    _require_tokens(
        implementation,
        (
            "betelgeuze.native_particle_mesh_ewald_composite/1.0.0",
            "std::fill(short_system.charge.begin(), short_system.charge.end(), 0.0)",
            "local_direct_model.reciprocal_max_indices = {{0, 0, 0}}",
            "cpu::evaluate(",
            "rust_cpu::evaluate(",
            "ewald::cpp_cpu::evaluate(",
            "ewald::rust_cpu::evaluate(",
            "particle_mesh_reciprocal::cpp_cpu::evaluate(",
            "particle_mesh_reciprocal::rust_cpu::evaluate(",
            "map_reciprocal_error",
            "context->requested_backend",
            "context->backend != lane",
            "BG_STATUS_UNSUPPORTED_BACKEND",
            "never falls back",
            "*out_energy = committed_energy",
        ),
        label="native composite implementation",
    )
    if "bg_context_evaluate_particle_mesh_ewald_v1(" in implementation:
        _fail("native composite must use bounded internal parents, not public reentry")

    native_test = _text(sources, "native/tests/particle_mesh_ewald_composite.cpp")
    _require_tokens(
        native_test,
        (
            "verify_abi_layout_profile_and_initializers",
            "verify_parent_composition_repeat_parity_and_energy_only",
            "verify_direct_bound_independence_and_mesh_convergence",
            "verify_symmetry_invariances",
            "verify_central_finite_difference",
            "verify_compatibility_transactionality_and_aliases",
            "verify_backend_preflight_precedes_other_arguments",
            "0.30000000000000004",
            "5.0e-12",
            "BG_BACKEND_AUTO",
            "BG_BACKEND_HIP_SAFE",
            "BG_BACKEND_HIP_FAST",
        ),
        label="native composite tests",
    )

    cmake = _text(sources, "native/CMakeLists.txt")
    _require_tokens(
        cmake,
        (
            "src/composite/particle_mesh_ewald_composite.cpp",
            "include/betelgeuze/particle_mesh_ewald_composite.h",
            "tests/particle_mesh_ewald_composite.cpp",
            "betelgeuze_engine_particle_mesh_ewald_composite",
            "betelgeuze_engine_export_allowlist",
        ),
        label="native CMake integration",
    )
    exports = _text(sources, "native/betelgeuze_engine.exports")
    version_map = _text(sources, "native/betelgeuze_engine.map")
    export_test = _text(sources, "native/tests/check_exports.cmake")
    for symbol in PUBLIC_SYMBOLS:
        if f"_{symbol}\n" not in exports:
            _fail(f"Mach-O export allowlist is missing {symbol}")
        if f"        {symbol};" not in version_map or symbol not in export_test:
            _fail(f"ELF/export test contract is missing {symbol}")
    _require_tokens(
        version_map,
        (
            "BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_1.0 {",
            "} BETELGEUZE_PARTICLE_MESH_EWALD_1.0;",
        ),
        label="ELF composite version node",
    )

    sys_lib = _text(sources, "rust/betelgeuze-sys/src/lib.rs")
    _require_tokens(
        sys_lib,
        (
            "BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION",
            "pub struct bg_particle_mesh_ewald_composite_energy_components_v1",
            "pub struct bg_particle_mesh_ewald_composite_force_soa_v1",
            *PUBLIC_SYMBOLS,
        ),
        label="Rust sys binding",
    )
    sys_manifest = _text(sources, "rust/betelgeuze-sys/Cargo.toml")
    sys_build = _text(sources, "rust/betelgeuze-sys/build.rs")
    _require_tokens(
        sys_manifest,
        (
            "abi/particle_mesh_ewald_composite_header_c11.c",
            "abi/particle_mesh_ewald_composite_layout_assertions.cpp",
            "vendor/include/betelgeuze/particle_mesh_ewald_composite.h",
            "vendor/native/src/composite/particle_mesh_ewald_composite.cpp",
        ),
        label="Rust sys package",
    )
    _require_tokens(
        sys_build,
        (
            "particle_mesh_ewald_composite_header_c11_probe",
            "particle_mesh_ewald_composite_cpp_layout_probe",
        ),
        label="Rust sys ABI probes",
    )
    layout = _text(sources, "rust/betelgeuze-sys/tests/layout.rs")
    raw_smoke = _text(sources, "rust/betelgeuze-sys/tests/raw_smoke.rs")
    _require_tokens(
        layout,
        (
            "particle_mesh_ewald_composite_layouts_match_the_c_header",
            "144",
            "88",
            "short_harmonic_bond_kcal_per_mol",
            "total_kcal_per_mol",
        ),
        label="Rust sys layout tests",
    )
    _require_tokens(
        raw_smoke,
        (
            "particle_mesh_ewald_composite_identity_and_null_failure_are_transactional",
            "betelgeuze.native_particle_mesh_ewald_composite/1.0.0",
        ),
        label="Rust sys raw smoke",
    )

    runtime = _text(
        sources, "rust/betelgeuze-runtime/src/particle_mesh_ewald_composite.rs"
    )
    _require_tokens(
        runtime,
        (
            "evaluate_particle_mesh_ewald_composite",
            "evaluate_particle_mesh_ewald_composite_energy",
            "ParticleMeshEwaldCompositeEnergyComponents",
            "DirectEwaldModel",
            "ParticleMeshReciprocalModel",
            "self.requested_backend()",
            "resolved != self.requested_backend()",
            "DirectEwaldResult",
        ),
        label="safe Rust composite runtime",
    )
    runtime_test = _text(
        sources, "rust/betelgeuze-runtime/tests/particle_mesh_ewald_composite.rs"
    )
    _require_tokens(
        runtime_test,
        (
            "0x4012_dc31_29bc_e12e",
            "both_cpu_lanes_equal_the_independent_short_plus_pme_parent_sum",
            "assert_parent_energy_bits",
            "assert_parent_force_sum_bits",
            "typed_failure_length_mismatch_and_auto_request_fail_closed_then_recover",
            "CppCpuReference",
            "RustCpu",
        ),
        label="safe Rust composite tests",
    )

    fixed64_verifier = _text(
        sources, "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py"
    )
    _require_tokens(
        fixed64_verifier,
        ('"rust/betelgeuze-runtime/tests/particle_mesh_ewald_composite.rs"',),
        label="fixed64-v7 source inventory",
    )

    predecessor_workflow = _text(
        sources, ".github/workflows/ci-engine-v2-native-particle-mesh-ewald.yml"
    )
    _require_tokens(
        predecessor_workflow,
        (
            "frozen=e228f376857ead900bd1ae99cf5b111c8b40cf34",
            "frozen_tree=ae0a6eddd44262eeec633c57a0f5566bf7989361",
            'git diff --exit-code "$frozen" --',
            'git checkout --detach --quiet "$frozen"',
            'git checkout --detach --quiet "$current_sha"',
            "refs/pull/441/head",
            "59ad72fe57e82106a71df2c88c63c9fe12d014ad",
        ),
        label="legacy particle-mesh Ewald frozen-object workflow",
    )
    if "--refresh" in predecessor_workflow:
        _fail("legacy particle-mesh Ewald workflow must never refresh frozen evidence")
    predecessor_unit = _text(
        sources, "tests/unit/test_engine_v2_native_particle_mesh_ewald_cpu_v1.py"
    )
    _require_tokens(
        predecessor_unit,
        (
            "pytest.mark.skipif(",
            "engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1.json",
            "verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py",
            "exact frozen object",
        ),
        label="legacy particle-mesh Ewald descendant-aware unit",
    )

    workflow = _text(
        sources,
        ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite.yml",
    )
    _require_tokens(
        workflow,
        (
            "permissions:\n  contents: read",
            "fetch-depth: 0",
            "runs-on: ubuntu-latest",
            "runs-on: macos-15",
            "HIP_VISIBLE_DEVICES: \"\"",
            "refs/pull/437/head",
            "refs/pull/441/head",
            "verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py",
            "test_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py",
            "betelgeuze_engine_particle_mesh_ewald_composite",
            "betelgeuze_engine_export_allowlist",
            "--test particle_mesh_ewald_composite",
            "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1",
        ),
        label="composite evidence workflow",
    )
    for forbidden in (
        "--refresh",
        "self-hosted",
        "workflow_run",
        "pull_request_target",
        "BG_REQUIRE_HIP_DEVICE",
        "fixed64-cpu-qualify-v7",
        "qualification_v7_execution",
    ):
        if forbidden in workflow:
            _fail(f"composite workflow contains forbidden authority token: {forbidden}")

    production_inputs = (
        "native/CMakeLists.txt",
        "native/src/composite/particle_mesh_ewald_composite.cpp",
        "rust/betelgeuze-sys/Cargo.toml",
        "rust/betelgeuze-runtime/Cargo.toml",
        "rust/betelgeuze-runtime/src/particle_mesh_ewald_composite.rs",
        "rust_engine_v2/Cargo.toml",
    )
    for path in production_inputs:
        lowered = _text(sources, path).lower()
        for forbidden in (
            "reference-pme",
            "reference-ewald",
            "qualification_v7_execution",
        ):
            if forbidden in lowered:
                _fail(
                    "independent reference or qualification entered production: "
                    f"{path}"
                )


def _git(root: Path, *arguments: str, expected: tuple[int, ...] = (0,)) -> bytes:
    environment = {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    result = subprocess.run(
        ["/usr/bin/git", "--no-replace-objects", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        env=environment,
    )
    if result.returncode not in expected or result.stderr:
        _fail(f"frozen Git object inspection failed: {' '.join(arguments)}")
    return result.stdout


def require_frozen_parent_objects(root: Path) -> None:
    for commit, contract in FROZEN_OBJECTS.items():
        resolved = _git(root, "rev-parse", "--verify", f"{commit}^{{commit}}")
        if resolved != f"{commit}\n".encode("ascii"):
            _fail(f"frozen parent commit changed: {commit}")
        tree = _git(root, "show", "-s", "--format=%T", commit).decode("ascii").strip()
        if tree != contract["tree"]:
            _fail(f"frozen parent tree changed: {commit}")
        _git(root, "merge-base", "--is-ancestor", commit, "HEAD")
        profile_path = str(contract["profile_path"])
        manifest_path = str(contract["source_manifest_path"])
        profile_raw = _git(root, "show", f"{commit}:{profile_path}")
        manifest_raw = _git(root, "show", f"{commit}:{manifest_path}")
        if _sha256(profile_raw) != contract["profile_sha256"]:
            _fail(f"frozen parent profile changed: {commit}")
        if _sha256(manifest_raw) != contract["source_manifest_sha256"]:
            _fail(f"frozen parent source manifest changed: {commit}")
        manifest = _canonical_object(
            manifest_raw, label=f"frozen manifest {commit}"
        )
        rows = manifest.get("files")
        if (
            type(rows) is not list
            or len(rows) != contract["source_manifest_entry_count"]
        ):
            _fail(f"frozen parent source count changed: {commit}")
        profile = _canonical_object(profile_raw, label=f"frozen profile {commit}")
        implementation = profile.get("implementation")
        if (
            type(implementation) is not dict
            or implementation.get("source_manifest_entry_count") != len(rows)
            or implementation.get("source_manifest_sha256")
            != contract["source_manifest_sha256"]
        ):
            _fail(f"frozen parent profile-to-manifest binding changed: {commit}")


def build_profile(*, manifest_raw: bytes, source_count: int) -> dict[str, object]:
    implementation = dict(IMPLEMENTATION_CONTRACT_BASE)
    implementation["source_manifest_entry_count"] = source_count
    implementation["source_manifest_sha256"] = _sha256(manifest_raw)
    return {
        "abi": dict(ABI_CONTRACT),
        "authority": dict(AUTHORITY_CONTRACT),
        "implementation": implementation,
        "operational_boundary": {
            "blockers": list(OPERATIONAL_BOUNDARY["blockers"]),
            "unresolved_operational_decisions": 32,
        },
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
    if any(value is not False for value in profile["authority"].values()):
        _fail("authority must remain entirely false")
    return profile


def verify(root: Path = ROOT) -> dict[str, object]:
    manifest_raw = _regular_file(root, SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest, _ = require_source_manifest(root, manifest_raw)
    rows = manifest["files"]
    assert isinstance(rows, list)
    profile_raw = _regular_file(root, PROFILE_RELATIVE_PATH).read_bytes()
    require_profile(
        profile_raw, source_manifest_raw=manifest_raw, source_count=len(rows)
    )
    require_frozen_parent_objects(root)
    return {
        "all_authority_false": True,
        "fixed64_cpu_v7_qualification_invoked": False,
        "frozen_parent_count": len(FROZEN_OBJECTS),
        "hip_device_execution_invoked": False,
        "molecular_execution_invoked": False,
        "operational_blocker_count": len(OPERATIONAL_BOUNDARY["blockers"]),
        "profile_path": PROFILE_RELATIVE_PATH.as_posix(),
        "profile_sha256": _sha256(profile_raw),
        "source_count": len(rows),
        "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
        "source_manifest_sha256": _sha256(manifest_raw),
        "unresolved_operational_decisions": 32,
        "verified": True,
    }


def _stage(path: Path, raw: bytes, mode: int) -> Path:
    descriptor, name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _replace_evidence(
    root: Path, evidence: tuple[tuple[Path, bytes], ...]
) -> dict[str, object]:
    snapshots: list[tuple[Path, bool, bytes, int]] = []
    staged: list[Path] = []
    seen: set[Path] = set()
    for relative, _ in evidence:
        if relative.is_absolute() or ".." in relative.parts:
            _fail(f"invalid evidence path: {relative}")
        path = root / relative
        if path in seen:
            _fail(f"duplicate evidence path: {relative}")
        seen.add(path)
        if (
            path.parent.is_symlink()
            or not path.parent.is_dir()
            or path.is_symlink()
            or (path.exists() and not path.is_file())
        ):
            _fail(f"refusing to replace non-regular evidence path: {relative}")
        existed = path.exists()
        mode = (path.stat().st_mode & 0o777) if existed else 0o644
        snapshots.append((path, existed, path.read_bytes() if existed else b"", mode))
    try:
        for (path, _, _, mode), (_, raw) in zip(
            snapshots, evidence, strict=True
        ):
            staged.append(_stage(path, raw, mode))
    except BaseException:
        for temporary in staged:
            temporary.unlink(missing_ok=True)
        raise
    try:
        for (path, _, _, _), temporary in zip(snapshots, staged, strict=True):
            os.replace(temporary, path)
        return verify(root)
    except BaseException as error:
        restoration_errors: list[str] = []
        for path, existed, previous, mode in reversed(snapshots):
            try:
                if existed:
                    os.replace(_stage(path, previous, mode), path)
                else:
                    path.unlink(missing_ok=True)
            except OSError as restore_error:
                restoration_errors.append(f"{path}: {restore_error}")
        if restoration_errors:
            raise NativeParticleMeshEwaldCompositeCPUProfileV1Error(
                "evidence refresh failed and rollback was incomplete: "
                + "; ".join(restoration_errors)
            ) from error
        raise
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)


def refresh(root: Path = ROOT) -> dict[str, object]:
    manifest_raw = canonical_bytes(build_source_manifest(root))
    manifest = _canonical_object(manifest_raw, label="generated source manifest")
    rows = manifest["files"]
    assert isinstance(rows, list)
    profile_raw = canonical_bytes(
        build_profile(manifest_raw=manifest_raw, source_count=len(rows))
    )
    return _replace_evidence(
        root,
        (
            (SOURCE_MANIFEST_RELATIVE_PATH, manifest_raw),
            (PROFILE_RELATIVE_PATH, profile_raw),
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    try:
        report = refresh(ROOT) if arguments.refresh else verify(ROOT)
    except (OSError, NativeParticleMeshEwaldCompositeCPUProfileV1Error) as error:
        print(
            "particle-mesh Ewald composite evidence verification failed: "
            f"{error}",
            file=sys.stderr,
        )
        return 1
    if arguments.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "particle-mesh Ewald composite evidence verified: "
            f"profile={report['profile_sha256']} "
            f"manifest={report['source_manifest_sha256']} "
            f"sources={report['source_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
