#!/usr/bin/env python3
"""Verify the bounded native short-range + direct-Ewald composite v1 evidence."""

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
from typing import Callable, NoReturn


ROOT = Path(__file__).resolve().parents[1]
PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_profile_v1_sources.json"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_cpu_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_cpu_profile_v1_sources.json"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_profile/1.0.0"
)
PROFILE_ID = "engine_v2_native_direct_ewald_composite_development_v1"
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_sources/1.0.0"
)
SOURCE_SCOPE = (
    "stateless_short_range_direct_ewald_composite_v1_owned_and_shared_inputs"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
OID_PATTERN = re.compile(r"[0-9a-f]{40}\Z")

PREDECESSOR = {
    "merge_commit": "074d3b71373088c0738de7a14797fe35d66d986e",
    "merge_tree": "e2763a42f4605d7435514c49f18259ea44f4dd3c",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "5d0a09742e8388938e90988a6a23fd945d5e2613d0fa37e9f2c8c9dd86d89de8"
    ),
    "pull_request": 436,
    "reviewed_head": "60a0047af27acacbce3feed7ee1dcedd8a690176",
    "source_manifest_entry_count": 55,
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "4f2acac517f56ade77b8712bfd24b4312f208f2a5902862f73a807e2a3f7e3ab"
    ),
}

ABI_CONTRACT = {
    "abi_version": 1,
    "abi_version_major": 1,
    "abi_version_minor": 0,
    "abi_version_string": "1.0.0",
    "borrowed_handle_count": 4,
    "energy_component_count": 12,
    "energy_descriptor_size_64_bit": 144,
    "force_descriptor_size_64_bit": 88,
    "frozen_direct_ewald_abi_changed": False,
    "frozen_engine_abi_changed": False,
    "header": "include/betelgeuze/direct_ewald_composite.h",
    "profile_id": "betelgeuze.native_direct_ewald_composite/1.0.0",
    "separately_versioned_stateless_boundary": True,
    "symbol_version_node": "BETELGEUZE_DIRECT_EWALD_COMPOSITE_1.0",
}

IMPLEMENTATION_CONTRACT_BASE = {
    "caller_system_mutated": False,
    "cpp_cpu_reference_lane": True,
    "development_exact_neutral_four_atom_fixture_only": True,
    "direct_ewald_uses_original_charges": True,
    "energy_only_allocates_or_accumulates_forces": False,
    "exclusion_provenance_preserved": True,
    "explicit_zero_scale_is_exclusion": False,
    "fixed64_cpu_v7_qualification_invoked": False,
    "hip_device_execution_invoked": False,
    "hip_to_cpu_fallback": False,
    "molecular_execution_invoked": False,
    "rust_cpu_lane": True,
    "short_range_uses_positive_zero_charge_copy": True,
    "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "stateful_owner_added": False,
    "whole_call_transactional_commit": True,
}

VALIDATION_CONTRACT = {
    "c11_public_header_probe": True,
    "caller_system_unchanged": True,
    "canonical_vendor_byte_identity": True,
    "cpp_layout_probe": True,
    "cpp_rust_cpu_tolerance": 5e-12,
    "energy_only_bit_identity": True,
    "exact_neutral_charge_bits": [0.7, -0.4, -0.6, 0.30000000000000004],
    "failure_output_transactionality": True,
    "finite_difference_force_check": True,
    "hip_fails_closed_before_evaluation": True,
    "mach_o_exact_export_allowlist": True,
    "pair_rule_provenance_checked": True,
    "parent_sum_component_order_checked": True,
    "public_symbol_version_checked": True,
    "raw_rust_abi_layout_and_smoke": True,
    "same_lane_bitwise_repeat": True,
    "safe_rust_runtime_wrapper": True,
    "short_coulomb_is_positive_zero": True,
    "typed_ewald_late_failure_preserved": True,
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
    "qualification_rerun_authorized": False,
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

# This focused closure binds the composite-owned files plus the shared parent
# evaluators, ABI/export policy, Rust bindings, and vendor copies it actually
# depends on. Generated evidence and its unit/doc/workflow consumers are
# intentionally excluded; the verifier itself is included.
REQUIRED_SOURCE_PATHS = (
    Path("include/betelgeuze/direct_ewald.h"),
    Path("include/betelgeuze/direct_ewald_composite.h"),
    Path("include/betelgeuze/engine.h"),
    Path("native/CMakeLists.txt"),
    Path("native/betelgeuze_engine.exports"),
    Path("native/betelgeuze_engine.map"),
    Path("native/src/composite/direct_ewald.cpp"),
    Path("native/src/context.cpp"),
    Path("native/src/cpu/evaluator.cpp"),
    Path("native/src/cpu/evaluator.hpp"),
    Path("native/src/cpu/neighbor_pair.hpp"),
    Path("native/src/evaluator.cpp"),
    Path("native/src/ewald/api.cpp"),
    Path("native/src/ewald/cpp_evaluator.cpp"),
    Path("native/src/ewald/cpp_evaluator.hpp"),
    Path("native/src/ewald/model.hpp"),
    Path("native/src/ewald/rust_evaluator.cpp"),
    Path("native/src/ewald/rust_evaluator.hpp"),
    Path("native/src/ewald/rust_provider.h"),
    Path("native/src/forcefield.cpp"),
    Path("native/src/internal.hpp"),
    Path("native/src/rust/evaluator.cpp"),
    Path("native/src/rust/evaluator.hpp"),
    Path("native/src/rust/provider.h"),
    Path("native/src/system.cpp"),
    Path("native/tests/check_exports.cmake"),
    Path("native/tests/direct_ewald_composite.cpp"),
    Path("rust/Cargo.lock"),
    Path("rust/Cargo.toml"),
    Path("rust/betelgeuze-runtime/Cargo.toml"),
    Path("rust/betelgeuze-runtime/build.rs"),
    Path("rust/betelgeuze-runtime/src/composite.rs"),
    Path("rust/betelgeuze-runtime/src/direct_ewald.rs"),
    Path("rust/betelgeuze-runtime/src/lib.rs"),
    Path("rust/betelgeuze-runtime/tests/composite.rs"),
    Path("rust/betelgeuze-runtime/tests/fixtures/direct_ewald_v1.tsv"),
    Path("rust/betelgeuze-sys/Cargo.toml"),
    Path("rust/betelgeuze-sys/abi/composite_header_c11.c"),
    Path("rust/betelgeuze-sys/abi/composite_layout_assertions.cpp"),
    Path("rust/betelgeuze-sys/build.rs"),
    Path("rust/betelgeuze-sys/src/lib.rs"),
    Path("rust/betelgeuze-sys/tests/layout.rs"),
    Path("rust/betelgeuze-sys/tests/raw_smoke.rs"),
    Path("rust/cpu-kernel/Cargo.toml"),
    Path("rust/cpu-kernel/src/direct_ewald.rs"),
    Path("rust/cpu-kernel/src/kernel.rs"),
    Path("rust/cpu-kernel/src/lib.rs"),
    Path("rust_engine_v2/Cargo.lock"),
    Path("rust_engine_v2/Cargo.toml"),
    Path("tools/__init__.py"),
    Path("tools/verify_engine_v2_native_direct_ewald_composite_v1.py"),
)

DISCOVERED_SOURCE_GLOBS = (
    "include/betelgeuze/**/*direct_ewald_composite*",
    "native/src/composite/**/*",
    "native/tests/**/*direct_ewald_composite*",
    "rust/betelgeuze-runtime/src/**/*composite*",
    "rust/betelgeuze-runtime/tests/**/*composite*",
    "rust/betelgeuze-sys/abi/**/*composite*",
    "rust/betelgeuze-sys/vendor/include/betelgeuze/**/*direct_ewald_composite*",
    "rust/betelgeuze-sys/vendor/native/src/composite/**/*",
)

VENDOR_SHARED_PATHS = (
    "include/betelgeuze/direct_ewald.h",
    "include/betelgeuze/direct_ewald_composite.h",
    "include/betelgeuze/engine.h",
    "native/src/composite/direct_ewald.cpp",
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
    "native/src/rust/evaluator.cpp",
    "native/src/rust/evaluator.hpp",
    "native/src/rust/provider.h",
    "native/src/system.cpp",
)


class NativeDirectEwaldCompositeV1Error(ValueError):
    """The composite v1 development evidence failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeDirectEwaldCompositeV1Error(message)


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
        raise NativeDirectEwaldCompositeV1Error(
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
    paths.update(
        Path("rust/betelgeuze-sys/vendor") / Path(relative)
        for relative in VENDOR_SHARED_PATHS
    )
    for pattern in DISCOVERED_SOURCE_GLOBS:
        for path in root.glob(pattern):
            if path.is_symlink():
                _fail(
                    "composite discovered source must not be a symlink: "
                    f"{path.relative_to(root)}"
                )
            if path.is_file():
                paths.add(path.relative_to(root))
    excluded = {
        PROFILE_RELATIVE_PATH,
        SOURCE_MANIFEST_RELATIVE_PATH,
        Path("tests/unit/test_engine_v2_native_direct_ewald_composite_v1.py"),
        Path("docs/engine_v2_native_direct_ewald_composite_v1.md"),
        Path(".github/workflows/ci-engine-v2-native-direct-ewald-composite.yml"),
    }
    if paths & excluded:
        _fail("generated or consumer evidence entered the acyclic source closure")
    for relative in paths:
        _require_regular_file(root, relative)
    return tuple(sorted(paths, key=lambda value: value.as_posix()))


def build_source_manifest(root: Path) -> dict[str, object]:
    rows = []
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
        if (
            relative.is_absolute()
            or relative.as_posix() != path_value
            or ".." in relative.parts
        ):
            _fail(f"source row {index} path is not normalized")
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
    for row in rows:
        assert isinstance(row, dict)
        path_value = row["path"]
        byte_count = row["byte_count"]
        digest = row["sha256"]
        assert isinstance(path_value, str)
        assert isinstance(byte_count, int)
        assert isinstance(digest, str)
        source_raw = _require_regular_file(root, Path(path_value)).read_bytes()
        if len(source_raw) != byte_count or _sha256(source_raw) != digest:
            _fail(f"source bytes drifted: {path_value}")
        sources[path_value] = source_raw
    return manifest, sources


def _git(
    root: Path,
    arguments: list[str],
    *,
    expected_statuses: tuple[int, ...] = (0,),
) -> tuple[int, bytes]:
    environment = {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    try:
        completed = subprocess.run(
            ["/usr/bin/git", "--no-replace-objects", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            env=environment,
        )
    except OSError as exc:
        raise NativeDirectEwaldCompositeV1Error(
            "historical predecessor Git object inspection failed"
        ) from exc
    if completed.returncode not in expected_statuses or completed.stderr:
        _fail("historical predecessor Git object is unavailable or ambiguous")
    return completed.returncode, completed.stdout


def require_predecessor(
    root: Path,
    *,
    merge_commit: str | None = None,
    reviewed_head: str | None = None,
) -> dict[str, object]:
    merge = merge_commit or str(PREDECESSOR["merge_commit"])
    reviewed = reviewed_head or str(PREDECESSOR["reviewed_head"])
    if OID_PATTERN.fullmatch(merge) is None or OID_PATTERN.fullmatch(reviewed) is None:
        _fail("historical predecessor object identity is invalid")
    if reviewed != PREDECESSOR["reviewed_head"]:
        _fail("historical predecessor reviewed-head metadata changed")
    _, resolved = _git(root, ["rev-parse", "--verify", f"{merge}^{{commit}}"])
    if resolved != f"{merge}\n".encode("ascii"):
        _fail("historical predecessor merge object changed")
    _, merge_tree = _git(root, ["show", "-s", "--format=%T", merge])
    expected_tree = f"{PREDECESSOR['merge_tree']}\n".encode("ascii")
    if merge_tree != expected_tree:
        _fail("merged predecessor tree is not the frozen exact tree")
    _git(root, ["merge-base", "--is-ancestor", merge, "HEAD"])

    _, profile_raw = _git(
        root,
        ["cat-file", "blob", f"{merge}:{PREDECESSOR_PROFILE_RELATIVE_PATH}"],
    )
    _, manifest_raw = _git(
        root,
        ["cat-file", "blob", f"{merge}:{PREDECESSOR_MANIFEST_RELATIVE_PATH}"],
    )
    if _sha256(profile_raw) != PREDECESSOR["profile_sha256"]:
        _fail("historical predecessor profile bytes changed")
    if _sha256(manifest_raw) != PREDECESSOR["source_manifest_sha256"]:
        _fail("historical predecessor source manifest bytes changed")
    profile = _load_canonical_object(profile_raw, label="historical predecessor profile")
    manifest = _load_canonical_object(
        manifest_raw, label="historical predecessor source manifest"
    )
    rows = manifest.get("files")
    if type(rows) is not list or len(rows) != PREDECESSOR["source_manifest_entry_count"]:
        _fail("historical predecessor source manifest count changed")
    paths = [row.get("path") for row in rows if type(row) is dict]
    if len(paths) != len(rows) or paths != sorted(set(paths)):
        _fail("historical predecessor source manifest paths changed")
    implementation = profile.get("implementation")
    if (
        type(implementation) is not dict
        or implementation.get("source_manifest_entry_count") != len(rows)
        or implementation.get("source_manifest_sha256")
        != PREDECESSOR["source_manifest_sha256"]
    ):
        _fail("historical predecessor profile-to-manifest binding changed")
    return {
        "merge_commit": merge,
        "merge_tree": merge_tree.decode("ascii").strip(),
        "profile_sha256": _sha256(profile_raw),
        "reviewed_head": reviewed,
        "source_manifest_entry_count": len(rows),
        "source_manifest_sha256": _sha256(manifest_raw),
    }


def _require_source_contract(sources: dict[str, bytes]) -> None:
    def text(path: str) -> str:
        try:
            return sources[path].decode("utf-8")
        except KeyError as exc:
            raise NativeDirectEwaldCompositeV1Error(
                f"required composite source is unbound: {path}"
            ) from exc
        except UnicodeError as exc:
            raise NativeDirectEwaldCompositeV1Error(
                f"composite source is not UTF-8: {path}"
            ) from exc

    header = text("include/betelgeuze/direct_ewald_composite.h")
    for token in (
        "BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MAJOR UINT32_C(1)",
        "BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MINOR UINT32_C(0)",
        "typedef struct bg_direct_ewald_composite_energy_components_v1",
        "typedef struct bg_direct_ewald_composite_force_soa_v1",
        "bg_context_evaluate_direct_ewald_composite_v1",
        "Rust CPU lanes are supported.  HIP fails before evaluation",
    ):
        if token not in header:
            _fail(f"public composite ABI contract is missing: {token}")
    for path, tokens in (
        (
            "include/betelgeuze/engine.h",
            (
                "BG_ABI_VERSION_MINOR UINT32_C(21)",
                "BG_ABI_VERSION UINT32_C(1)",
            ),
        ),
        (
            "include/betelgeuze/direct_ewald.h",
            (
                "BG_DIRECT_EWALD_ABI_VERSION_MINOR UINT32_C(0)",
                "BG_DIRECT_EWALD_ABI_VERSION UINT32_C(1)",
            ),
        ),
    ):
        source = text(path)
        for token in tokens:
            if token not in source:
                _fail(f"frozen parent ABI identity changed: {path}: {token}")

    implementation = text("native/src/composite/direct_ewald.cpp")
    for token in (
        "validate_pair_rule_projection",
        "validate_output_system_disjoint",
        "observed.is_exclusion",
        "std::fill(short_system.charge.begin(), short_system.charge.end(), 0.0)",
        "ewald::cpp_cpu::evaluate",
        "ewald::rust_cpu::evaluate",
        "BG_STATUS_UNSUPPORTED_BACKEND",
        "CPU fallback is forbidden",
        "*out_energy = committed_energy",
    ):
        if token not in implementation:
            _fail(f"native composite implementation contract is missing: {token}")
    model = text("native/src/ewald/model.hpp")
    api = text("native/src/ewald/api.cpp")
    for token in ("bool is_exclusion = false;",):
        if token not in model:
            _fail(f"direct-Ewald pair provenance storage is missing: {token}")
    for token in ("0.0, true", "scale->second,", "false}"):
        if token not in api:
            _fail(f"direct-Ewald pair provenance construction is missing: {token}")

    version_map = text("native/betelgeuze_engine.map")
    if "BETELGEUZE_DIRECT_EWALD_COMPOSITE_1.0" not in version_map:
        _fail("composite ELF symbol version node is missing")
    composite_symbols = (
        "bg_direct_ewald_composite_abi_version",
        "bg_direct_ewald_composite_abi_version_major",
        "bg_direct_ewald_composite_abi_version_minor",
        "bg_direct_ewald_composite_abi_version_string",
        "bg_direct_ewald_composite_energy_components_v1_init",
        "bg_direct_ewald_composite_force_soa_v1_init",
        "bg_direct_ewald_composite_v1_profile_id",
        "bg_context_evaluate_direct_ewald_composite_v1",
    )
    for symbol in composite_symbols:
        if f"        {symbol};" not in version_map:
            _fail(f"composite ELF export is missing: {symbol}")
    map_symbols = re.findall(
        r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+);[ \t]*$", version_map
    )
    exports = text("native/betelgeuze_engine.exports").splitlines()
    if exports != [f"_{symbol}" for symbol in map_symbols]:
        _fail("Mach-O exports drifted from the exact ELF public symbol set")
    if any(symbol.startswith("_bg_rust_") for symbol in exports):
        _fail("private Rust provider entered the Mach-O public ABI")

    cmake = text("native/CMakeLists.txt")
    for token in (
        "src/composite/direct_ewald.cpp",
        "include/betelgeuze/direct_ewald_composite.h",
        "betelgeuze_engine_direct_ewald_composite",
        "betelgeuze_engine_export_allowlist",
    ):
        if token not in cmake:
            _fail(f"native composite build/test contract is missing: {token}")
    export_test = text("native/tests/check_exports.cmake")
    for token in composite_symbols:
        if token not in export_test:
            _fail(f"export regression test omitted composite symbol: {token}")

    native_test = text("native/tests/direct_ewald_composite.cpp")
    runtime_test = text("rust/betelgeuze-runtime/tests/composite.rs")
    combined_tests = native_test + runtime_test
    for token in (
        "bg_context_evaluate_direct_ewald_composite_v1",
        "0.30000000000000004",
        "energy_only",
        "transaction",
        "verify_central_finite_difference",
        "HIP",
    ):
        if token.lower() not in combined_tests.lower():
            _fail(f"composite regression coverage is missing: {token}")
    if "ala3" in combined_tests.lower():
        _fail("non-neutral Ala3 deferral fixture entered composite execution tests")

    sys_source = text("rust/betelgeuze-sys/src/lib.rs")
    for token in (
        "BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION: u32 = 1",
        "pub struct bg_direct_ewald_composite_energy_components_v1",
        "pub struct bg_direct_ewald_composite_force_soa_v1",
        "pub fn bg_context_evaluate_direct_ewald_composite_v1",
    ):
        if token not in sys_source:
            _fail(f"Rust raw composite ABI binding is missing: {token}")
    sys_manifest = text("rust/betelgeuze-sys/Cargo.toml")
    sys_build = text("rust/betelgeuze-sys/build.rs")
    for token in (
        "abi/composite_header_c11.c",
        "abi/composite_layout_assertions.cpp",
        "vendor/include/betelgeuze/direct_ewald_composite.h",
        "vendor/native/src/composite/direct_ewald.cpp",
    ):
        if token not in sys_manifest:
            _fail(f"Rust system package omitted composite input: {token}")
    for token in (
        "composite_header_c11_probe",
        "composite_cpp_layout_probe",
    ):
        if token not in sys_build:
            _fail(f"Rust system build omitted composite ABI probe: {token}")
    layout_test = text("rust/betelgeuze-sys/tests/layout.rs")
    raw_smoke = text("rust/betelgeuze-sys/tests/raw_smoke.rs")
    for token in ("144", "bg_direct_ewald_composite_energy_components_v1"):
        if token not in layout_test:
            _fail(f"Rust raw composite layout coverage is missing: {token}")
    for token in (
        "direct_ewald_composite_identity_initializers_and_null_failure_are_transactional",
        "bg_direct_ewald_composite_v1_profile_id",
    ):
        if token not in raw_smoke:
            _fail(f"Rust raw composite smoke coverage is missing: {token}")

    runtime = text("rust/betelgeuze-runtime/src/composite.rs")
    for token in (
        "evaluate_direct_ewald_composite",
        "evaluate_direct_ewald_composite_energy",
        "direct_ewald_composite_profile_id",
        "short_coulomb_kcal_per_mol.to_bits()",
        "BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION",
    ):
        if token not in runtime:
            _fail(f"safe Rust composite boundary is missing: {token}")

    for canonical in VENDOR_SHARED_PATHS:
        vendor = f"rust/betelgeuze-sys/vendor/{canonical}"
        if vendor not in sources:
            _fail(f"vendored composite dependency is unbound: {vendor}")
        if sources[vendor] != sources[canonical]:
            _fail(f"vendored composite dependency drifted: {vendor}")

    production_paths = (
        "native/CMakeLists.txt",
        "native/src/composite/direct_ewald.cpp",
        "rust/betelgeuze-runtime/Cargo.toml",
        "rust/betelgeuze-runtime/src/composite.rs",
        "rust/betelgeuze-sys/Cargo.toml",
        "rust_engine_v2/Cargo.toml",
    )
    for path in production_paths:
        source = text(path)
        for forbidden in (
            "reference-ewald",
            "betelgeuze-reference-ewald",
            "qualification_v7_execution",
        ):
            if forbidden in source:
                _fail(f"forbidden production dependency entered {path}: {forbidden}")


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
            "predecessor",
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
    if profile["predecessor"] != PREDECESSOR:
        _fail("historical predecessor binding changed")
    if profile["abi"] != ABI_CONTRACT:
        _fail("composite ABI contract changed")
    expected_implementation = {
        **IMPLEMENTATION_CONTRACT_BASE,
        "source_manifest_entry_count": source_count,
        "source_manifest_sha256": _sha256(source_manifest_raw),
    }
    if profile["implementation"] != expected_implementation:
        _fail("composite implementation binding changed")
    if profile["validation"] != VALIDATION_CONTRACT:
        _fail("composite validation contract changed")
    if profile["authority"] != AUTHORITY_CONTRACT or any(
        value is not False for value in AUTHORITY_CONTRACT.values()
    ):
        _fail("composite authority changed")
    if profile["operational_boundary"] != OPERATIONAL_BOUNDARY:
        _fail("operational blocker boundary changed")
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
        "predecessor": dict(PREDECESSOR),
        "profile_id": PROFILE_ID,
        "roadmap_issue": 434,
        "schema_id": SCHEMA_ID,
        "validation": dict(VALIDATION_CONTRACT),
    }


def verify(root: Path = ROOT) -> dict[str, object]:
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
    predecessor = require_predecessor(root)
    _require_source_contract(sources)
    return {
        "all_authority_false": True,
        "fixed64_cpu_v7_qualification_invoked": False,
        "hip_device_execution_invoked": False,
        "molecular_execution_invoked": False,
        "operational_blocker_count": len(OPERATIONAL_BLOCKERS),
        "predecessor_merge_commit": predecessor["merge_commit"],
        "profile_path": PROFILE_RELATIVE_PATH.as_posix(),
        "profile_sha256": _sha256(profile_raw),
        "source_count": len(rows),
        "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
        "source_manifest_sha256": _sha256(manifest_raw),
        "unresolved_operational_decisions": 32,
        "verified": True,
    }


def _stage_evidence_file(path: Path, raw: bytes, mode: int) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        stream = os.fdopen(descriptor, "wb")
        descriptor = -1
        with stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
    except BaseException as exc:
        cleanup_errors: list[str] = []
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError as close_exc:
                cleanup_errors.append(f"descriptor close: {close_exc}")
        cleanup_errors.extend(_cleanup_evidence_temporaries((temporary,)))
        if cleanup_errors:
            raise NativeDirectEwaldCompositeV1Error(
                "evidence staging failed and temporary cleanup was incomplete: "
                + "; ".join(cleanup_errors)
            ) from exc
        raise
    return temporary


def _cleanup_evidence_temporaries(
    temporaries: tuple[Path | None, ...],
    *,
    preserve: frozenset[Path] = frozenset(),
) -> list[str]:
    errors: list[str] = []
    for temporary in temporaries:
        if temporary is None or temporary in preserve:
            continue
        try:
            temporary.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"{temporary}: {exc}")
    return errors


def _require_evidence_target(root: Path, relative: Path) -> Path:
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in ("", ".", "..") for part in relative.parts)
    ):
        _fail(f"invalid evidence path: {relative}")
    if root.is_symlink() or not root.is_dir():
        _fail(f"evidence root is not a regular directory: {root}")
    try:
        if root.resolve(strict=True) != Path(os.path.abspath(root)):
            _fail(f"evidence root has a symlinked ancestor: {root}")
    except OSError as exc:
        raise NativeDirectEwaldCompositeV1Error(
            f"cannot resolve evidence root: {root}"
        ) from exc

    parent = root
    for part in relative.parts[:-1]:
        parent /= part
        if parent.is_symlink() or not parent.is_dir():
            _fail(
                "evidence path has a symlinked or non-directory ancestor: "
                f"{relative}"
            )
    path = parent / relative.name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        _fail(f"refusing to replace non-regular evidence path: {relative}")
    return path


def _replace_evidence_transactionally(
    root: Path,
    evidence: tuple[tuple[Path, bytes], ...],
    verify_current: Callable[[], dict[str, object]],
) -> dict[str, object]:
    snapshots: list[tuple[Path, bool, bytes, int]] = []
    seen_targets: set[Path] = set()
    for relative, _ in evidence:
        path = _require_evidence_target(root, relative)
        if path in seen_targets:
            _fail(f"duplicate evidence target: {relative}")
        seen_targets.add(path)
        existed = path.exists()
        snapshots.append(
            (
                path,
                existed,
                path.read_bytes() if existed else b"",
                (path.stat().st_mode & 0o777) if existed else 0o644,
            )
        )

    staged: list[Path] = []
    rollback: list[Path | None] = []
    try:
        for (path, existed, previous_raw, mode), (_, new_raw) in zip(
            snapshots, evidence, strict=True
        ):
            staged.append(_stage_evidence_file(path, new_raw, mode))
            rollback.append(
                _stage_evidence_file(path, previous_raw, mode)
                if existed
                else None
            )
    except BaseException as exc:
        cleanup_errors = _cleanup_evidence_temporaries(
            (*staged, *rollback)
        )
        if cleanup_errors:
            details = list(cleanup_errors)
            if isinstance(exc, NativeDirectEwaldCompositeV1Error):
                details.insert(0, str(exc))
            raise NativeDirectEwaldCompositeV1Error(
                "evidence refresh staging failed before commit and temporary "
                "cleanup was incomplete: " + "; ".join(details)
            ) from exc
        if not isinstance(exc, Exception):
            raise
        if isinstance(exc, NativeDirectEwaldCompositeV1Error):
            raise
        raise NativeDirectEwaldCompositeV1Error(
            "evidence refresh staging failed before commit"
        ) from exc

    try:
        for (path, _, _, _), temporary in zip(
            snapshots, staged, strict=True
        ):
            os.replace(temporary, path)
        result = verify_current()
    except BaseException as exc:
        rollback_errors: list[str] = []
        preserved_backups: set[Path] = set()
        for (path, existed, previous_raw, mode), temporary in reversed(
            list(zip(snapshots, rollback, strict=True))
        ):
            try:
                if existed:
                    assert temporary is not None
                    os.replace(temporary, path)
                elif path.is_symlink() or path.exists():
                    path.unlink()
                if existed:
                    if path.is_symlink() or path.read_bytes() != previous_raw:
                        raise OSError("restored bytes do not match snapshot")
                elif path.is_symlink() or path.exists():
                    raise OSError("new evidence path survived rollback")
            except BaseException as rollback_exc:
                backup = temporary
                backup_error = ""
                if existed and (backup is None or not backup.exists()):
                    try:
                        backup = _stage_evidence_file(path, previous_raw, mode)
                    except BaseException as backup_exc:
                        backup = None
                        backup_error = f"; backup recreation failed: {backup_exc}"
                if backup is not None and backup.exists():
                    preserved_backups.add(backup)
                    backup_error += f"; backup preserved at {backup}"
                rollback_errors.append(
                    f"{path}: {rollback_exc}{backup_error}"
                )
        cleanup_errors = _cleanup_evidence_temporaries(
            (*staged, *rollback),
            preserve=frozenset(preserved_backups),
        )
        if rollback_errors:
            raise NativeDirectEwaldCompositeV1Error(
                "evidence refresh failed and rollback was incomplete: "
                + "; ".join((*rollback_errors, *cleanup_errors))
            ) from exc
        if cleanup_errors:
            raise NativeDirectEwaldCompositeV1Error(
                "evidence refresh failed; original evidence was restored but "
                "temporary cleanup was incomplete: "
                + "; ".join(cleanup_errors)
            ) from exc
        if not isinstance(exc, Exception):
            raise
        if isinstance(exc, NativeDirectEwaldCompositeV1Error):
            raise
        raise NativeDirectEwaldCompositeV1Error(
            "evidence refresh failed; original evidence restored"
        ) from exc

    cleanup_errors = _cleanup_evidence_temporaries((*staged, *rollback))
    if cleanup_errors:
        raise NativeDirectEwaldCompositeV1Error(
            "evidence refresh committed and verified but temporary cleanup "
            "was incomplete: " + "; ".join(cleanup_errors)
        )
    return result


def refresh(root: Path = ROOT) -> dict[str, object]:
    require_predecessor(root)
    manifest = build_source_manifest(root)
    manifest_raw = canonical_bytes(manifest)
    rows = manifest["files"]
    assert isinstance(rows, list)
    _, sources = require_source_manifest(root, manifest_raw)
    _require_source_contract(sources)
    profile_raw = canonical_bytes(
        build_profile(source_manifest_raw=manifest_raw, source_count=len(rows))
    )
    require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
    )
    evidence = (
        (SOURCE_MANIFEST_RELATIVE_PATH, manifest_raw),
        (PROFILE_RELATIVE_PATH, profile_raw),
    )
    result = _replace_evidence_transactionally(
        root, evidence, lambda: verify(root)
    )
    result["refreshed"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="explicitly regenerate the acyclic manifest and profile binding",
    )
    arguments = parser.parse_args(argv)
    try:
        result = refresh(ROOT) if arguments.refresh else verify(ROOT)
    except NativeDirectEwaldCompositeV1Error as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
