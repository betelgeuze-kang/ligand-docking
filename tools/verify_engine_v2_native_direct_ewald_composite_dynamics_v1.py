#!/usr/bin/env python3
"""Verify the bounded native direct-Ewald composite dynamics v1 evidence."""

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
    "config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1_sources.json"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_profile_v1_sources.json"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_profile/1.0.0"
)
PROFILE_ID = "engine_v2_native_direct_ewald_composite_dynamics_development_v1"
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_sources/1.0.0"
)
SOURCE_SCOPE = (
    "stateful_direct_ewald_composite_dynamics_v1_owned_and_shared_inputs"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
OID_PATTERN = re.compile(r"[0-9a-f]{40}\Z")

PREDECESSOR = {
    "merge_commit": "f2731176fb913f600349ec6a1fbf3678d399a7c1",
    "merge_tree": "6017cf05e3f437443371966775bb4deb3fc73cab",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "31dc3535d915980b1a7c318839162a4ce62d6a8bbf221b3415a67a98677d57e7"
    ),
    "pull_request": 437,
    "reviewed_head": "454bb9ee6cdb4202cecbc807f78503ce842bdd13",
    "source_manifest_entry_count": 73,
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "53267e95900402f60f4aba13a674e0e9530291d68310765d1a35a17146bf6afb"
    ),
}

FROZEN_PREDECESSOR_PATHS = (
    Path("include/betelgeuze/engine.h"),
    Path("include/betelgeuze/direct_ewald.h"),
    Path("include/betelgeuze/direct_ewald_composite.h"),
    Path("native/src/dynamics/checkpoint.cpp"),
)

ABI_CONTRACT = {
    "abi_version": 1,
    "abi_version_major": 1,
    "abi_version_minor": 0,
    "abi_version_string": "1.0.0",
    "checkpoint_header_size_bytes": 104,
    "checkpoint_magic": "BGDEC001",
    "exported_symbol_count": 13,
    "frozen_direct_ewald_abi_changed": False,
    "frozen_engine_abi_changed": False,
    "frozen_stateless_composite_abi_changed": False,
    "header": "include/betelgeuze/direct_ewald_composite_dynamics.h",
    "profile_id": "betelgeuze.native_direct_ewald_composite_dynamics/1.0.0",
    "reused_dynamics_report_size_64_bit": 104,
    "reused_simulation_options_size_64_bit": 80,
    "separately_versioned_stateful_boundary": True,
    "symbol_version_node": "BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0",
}

IMPLEMENTATION_CONTRACT_BASE = {
    "caller_system_mutated": False,
    "checkpoint_format_cross_compatible_with_legacy": False,
    "cpp_cpu_reference_lane": True,
    "deep_owned_constraints": True,
    "deep_owned_direct_ewald_model": True,
    "deep_owned_forcefield": True,
    "deep_owned_system": True,
    "development_exact_neutral_four_atom_fixture_only": True,
    "exclusion_provenance_preserved": True,
    "explicit_zero_scale_is_exclusion": False,
    "fixed64_cpu_v7_qualification_invoked": False,
    "hip_device_execution_invoked": False,
    "hip_to_cpu_fallback": False,
    "molecular_execution_invoked": False,
    "reuses_frozen_constraints_descriptor": True,
    "reuses_frozen_dynamics_report": True,
    "reuses_frozen_simulation_options": True,
    "rust_cpu_lane": True,
    "shared_velocity_verlet_sha256_pipeline": True,
    "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "stateful_owner_added": True,
    "whole_call_transactional_commit": True,
}

VALIDATION_CONTRACT = {
    "baoab_rejected": True,
    "c11_public_header_probe": True,
    "caller_system_unchanged": True,
    "canonical_vendor_byte_identity": True,
    "checkpoint_corrupt_truncated_appended_rejected": True,
    "checkpoint_cross_format_rejected": True,
    "checkpoint_fingerprint_model_provenance_timestep_checked": True,
    "checkpoint_output_transactionality": True,
    "checkpoint_split_continuation_bit_identity": True,
    "cpp_layout_probe": True,
    "cpp_rust_zero_step_stateless_total_bit_identity": True,
    "deep_ownership_and_stable_views": True,
    "exact_neutral_charge_bits": [0.7, -0.4, -0.6, 0.30000000000000004],
    "failure_output_transactionality": True,
    "hip_fails_closed_before_evaluation": True,
    "mach_o_exact_export_allowlist": True,
    "manual_one_step_velocity_verlet_exact": True,
    "nve_small_step_finite": True,
    "pair_rule_provenance_checked": True,
    "public_symbol_version_checked": True,
    "raw_rust_abi_layout_and_smoke": True,
    "same_lane_bitwise_repeat": True,
    "safe_rust_runtime_wrapper": True,
    "step_overflow_rejected": True,
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
    Path("include/betelgeuze/direct_ewald_composite_dynamics.h"),
    Path("include/betelgeuze/engine.h"),
    Path("native/CMakeLists.txt"),
    Path("native/betelgeuze_engine.exports"),
    Path("native/betelgeuze_engine.map"),
    Path("native/src/composite/direct_ewald.cpp"),
    Path("native/src/composite/direct_ewald_composite_checkpoint.cpp"),
    Path("native/src/composite/direct_ewald_composite_dynamics.cpp"),
    Path("native/src/composite/direct_ewald_composite_dynamics.hpp"),
    Path("native/src/composite/evaluator.hpp"),
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
    Path("native/src/hip/backend.hpp"),
    Path("native/src/hip/evaluator.cpp"),
    Path("native/src/hip/evaluator.hpp"),
    Path("native/src/hip/provider.h"),
    Path("native/src/hip/stub.cpp"),
    Path("native/src/internal.hpp"),
    Path("native/src/dynamics/api.cpp"),
    Path("native/src/dynamics/checkpoint.cpp"),
    Path("native/src/dynamics/common.cpp"),
    Path("native/src/dynamics/dynamics.hpp"),
    Path("native/src/dynamics/integrator.cpp"),
    Path("native/src/dynamics/sha256.cpp"),
    Path("native/src/dynamics/sha256.hpp"),
    Path("native/src/rust/evaluator.cpp"),
    Path("native/src/rust/evaluator.hpp"),
    Path("native/src/rust/provider.h"),
    Path("native/src/system.cpp"),
    Path("native/tests/check_exports.cmake"),
    Path("native/tests/direct_ewald_composite.cpp"),
    Path("native/tests/direct_ewald_composite_dynamics.cpp"),
    Path("rust/Cargo.lock"),
    Path("rust/Cargo.toml"),
    Path("rust/betelgeuze-runtime/Cargo.toml"),
    Path("rust/betelgeuze-runtime/build.rs"),
    Path("rust/betelgeuze-runtime/src/composite.rs"),
    Path("rust/betelgeuze-runtime/src/direct_ewald.rs"),
    Path("rust/betelgeuze-runtime/src/direct_ewald_composite_dynamics.rs"),
    Path("rust/betelgeuze-runtime/src/dynamics.rs"),
    Path("rust/betelgeuze-runtime/src/lib.rs"),
    Path("rust/betelgeuze-runtime/tests/composite.rs"),
    Path("rust/betelgeuze-runtime/tests/direct_ewald_composite_dynamics.rs"),
    Path("rust/betelgeuze-runtime/tests/fixtures/direct_ewald_v1.tsv"),
    Path("rust/betelgeuze-sys/Cargo.toml"),
    Path("rust/betelgeuze-sys/abi/composite_header_c11.c"),
    Path("rust/betelgeuze-sys/abi/composite_layout_assertions.cpp"),
    Path("rust/betelgeuze-sys/abi/direct_ewald_composite_dynamics_header_c11.c"),
    Path("rust/betelgeuze-sys/abi/direct_ewald_composite_dynamics_layout_assertions.cpp"),
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
    Path("tools/verify_engine_v2_native_direct_ewald_composite_dynamics_v1.py"),
)

DISCOVERED_SOURCE_GLOBS = (
    "include/betelgeuze/**/*direct_ewald_composite*",
    "native/src/composite/**/*",
    "native/src/dynamics/**/*",
    "native/tests/**/*direct_ewald_composite*",
    "rust/betelgeuze-runtime/src/**/*composite*",
    "rust/betelgeuze-runtime/tests/**/*composite*",
    "rust/betelgeuze-sys/abi/**/*composite*",
    "rust/betelgeuze-sys/vendor/include/betelgeuze/**/*direct_ewald_composite*",
    "rust/betelgeuze-sys/vendor/native/src/composite/**/*",
    "rust/betelgeuze-sys/vendor/native/src/dynamics/**/*",
)

VENDOR_SHARED_PATHS = (
    "include/betelgeuze/direct_ewald.h",
    "include/betelgeuze/direct_ewald_composite.h",
    "include/betelgeuze/direct_ewald_composite_dynamics.h",
    "include/betelgeuze/engine.h",
    "native/src/composite/direct_ewald.cpp",
    "native/src/composite/direct_ewald_composite_checkpoint.cpp",
    "native/src/composite/direct_ewald_composite_dynamics.cpp",
    "native/src/composite/direct_ewald_composite_dynamics.hpp",
    "native/src/composite/evaluator.hpp",
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
    "native/src/hip/backend.hpp",
    "native/src/hip/evaluator.cpp",
    "native/src/hip/evaluator.hpp",
    "native/src/hip/provider.h",
    "native/src/hip/stub.cpp",
    "native/src/internal.hpp",
    "native/src/dynamics/api.cpp",
    "native/src/dynamics/checkpoint.cpp",
    "native/src/dynamics/common.cpp",
    "native/src/dynamics/dynamics.hpp",
    "native/src/dynamics/integrator.cpp",
    "native/src/dynamics/sha256.cpp",
    "native/src/dynamics/sha256.hpp",
    "native/src/rust/evaluator.cpp",
    "native/src/rust/evaluator.hpp",
    "native/src/rust/provider.h",
    "native/src/system.cpp",
)


class NativeDirectEwaldCompositeDynamicsV1Error(ValueError):
    """The composite-dynamics v1 development evidence failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeDirectEwaldCompositeDynamicsV1Error(message)


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
        raise NativeDirectEwaldCompositeDynamicsV1Error(
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
                    "composite-dynamics discovered source must not be a symlink: "
                    f"{path.relative_to(root)}"
                )
            if path.is_file():
                paths.add(path.relative_to(root))
    excluded = {
        PROFILE_RELATIVE_PATH,
        SOURCE_MANIFEST_RELATIVE_PATH,
        Path("tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_v1.py"),
        Path("docs/engine_v2_native_direct_ewald_composite_dynamics_v1.md"),
        Path(".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics.yml"),
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
        raise NativeDirectEwaldCompositeDynamicsV1Error(
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

    frozen_digests: dict[str, str] = {}
    for relative in FROZEN_PREDECESSOR_PATHS:
        _, historical_raw = _git(
            root,
            ["cat-file", "blob", f"{merge}:{relative.as_posix()}"],
        )
        current_raw = _require_regular_file(root, relative).read_bytes()
        if current_raw != historical_raw:
            _fail(
                "frozen predecessor source bytes changed: "
                f"{relative.as_posix()}"
            )
        frozen_digests[relative.as_posix()] = _sha256(historical_raw)

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
        "frozen_predecessor_paths": frozen_digests,
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
            raise NativeDirectEwaldCompositeDynamicsV1Error(
                f"required composite-dynamics source is unbound: {path}"
            ) from exc
        except UnicodeError as exc:
            raise NativeDirectEwaldCompositeDynamicsV1Error(
                f"composite-dynamics source is not UTF-8: {path}"
            ) from exc

    header = text("include/betelgeuze/direct_ewald_composite_dynamics.h")
    for token in (
        "BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MAJOR UINT32_C(1)",
        "BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MINOR UINT32_C(0)",
        "typedef struct bg_direct_ewald_composite_simulation_v1",
        "Only Velocity-Verlet options are",
        'uses magic "BGDEC001"',
        'legacy "BGDYN001"',
    ):
        if token not in header:
            _fail(f"public composite-dynamics ABI contract is missing: {token}")

    dynamics_symbols = (
        "bg_direct_ewald_composite_dynamics_abi_version",
        "bg_direct_ewald_composite_dynamics_abi_version_major",
        "bg_direct_ewald_composite_dynamics_abi_version_minor",
        "bg_direct_ewald_composite_dynamics_abi_version_string",
        "bg_direct_ewald_composite_dynamics_v1_profile_id",
        "bg_direct_ewald_composite_simulation_v1_create",
        "bg_direct_ewald_composite_simulation_v1_destroy",
        "bg_direct_ewald_composite_simulation_v1_get_particles",
        "bg_direct_ewald_composite_simulation_v1_get_absolute_step",
        "bg_context_integrate_direct_ewald_composite_v1",
        "bg_direct_ewald_composite_simulation_v1_checkpoint_size",
        "bg_direct_ewald_composite_simulation_v1_checkpoint_write",
        "bg_direct_ewald_composite_simulation_v1_checkpoint_load",
    )
    if len(dynamics_symbols) != ABI_CONTRACT["exported_symbol_count"]:
        _fail("composite-dynamics public symbol count changed")
    for symbol in dynamics_symbols:
        occurrences = re.findall(rf"\b{re.escape(symbol)}\s*\(", header)
        if len(occurrences) != 1:
            _fail(
                "public composite-dynamics declaration count changed: "
                f"{symbol}"
            )

    for path, tokens in (
        (
            "include/betelgeuze/engine.h",
            (
                "BG_ABI_VERSION_MINOR UINT32_C(21)",
                "typedef struct bg_distance_constraints_v1",
                "typedef struct bg_simulation_options_v1",
                "typedef struct bg_dynamics_report_v1",
            ),
        ),
        (
            "include/betelgeuze/direct_ewald.h",
            (
                "BG_DIRECT_EWALD_ABI_VERSION_MINOR UINT32_C(0)",
                "BG_DIRECT_EWALD_ABI_VERSION UINT32_C(1)",
            ),
        ),
        (
            "include/betelgeuze/direct_ewald_composite.h",
            (
                "BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MINOR UINT32_C(0)",
                "bg_context_evaluate_direct_ewald_composite_v1",
            ),
        ),
    ):
        source = text(path)
        for token in tokens:
            if token not in source:
                _fail(f"frozen parent ABI identity changed: {path}: {token}")

    implementation = text(
        "native/src/composite/direct_ewald_composite_dynamics.cpp"
    )
    for token in (
        "DynamicStateRollback",
        "evaluate_prevalidated",
        "BG_INTEGRATOR_VELOCITY_VERLET",
        "BG_STATUS_UNSUPPORTED_BACKEND",
        "step_count > UINT64_MAX - legacy->absolute_step",
        "const betelgeuze::native::dynamics::ForceProvider provider",
        "betelgeuze::native::dynamics::integrate(",
        "std::make_unique<bg_direct_ewald_composite_simulation_v1>()",
        "*out_report = report",
    ):
        if token not in implementation:
            _fail(
                "native composite-dynamics implementation contract is missing: "
                f"{token}"
            )

    shared_dynamics = text("native/src/dynamics/dynamics.hpp")
    for token in (
        "using ForceProviderFunction = bg_status (*)(",
        "struct ForceProvider final",
        "bg_status integrate(",
        "const ForceProvider &provider",
    ):
        if token not in shared_dynamics:
            _fail(f"shared dynamics provider seam is missing: {token}")

    checkpoint = text(
        "native/src/composite/direct_ewald_composite_checkpoint.cpp"
    )
    for token in (
        "kCompositeMagic",
        "'B', 'G', 'D', 'E', 'C', '0', '0', '1'",
        "kLegacyMagic",
        "'B', 'G', 'D', 'Y', 'N', '0', '0', '1'",
        "constexpr std::size_t kHeaderSize = 104U",
        "simulation->static_fingerprint",
        "sha256_with_zero_range",
        "bg_simulation_checkpoint_write",
        "bg_simulation_checkpoint_load",
        "std::memmove(buffer, bytes.data(), required)",
    ):
        if token not in checkpoint:
            _fail(f"composite checkpoint contract is missing: {token}")

    version_map = text("native/betelgeuze_engine.map")
    if (
        "BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0"
        not in version_map
    ):
        _fail("composite-dynamics ELF symbol version node is missing")
    for symbol in dynamics_symbols:
        if f"        {symbol};" not in version_map:
            _fail(f"composite-dynamics ELF export is missing: {symbol}")
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
        "src/composite/direct_ewald_composite_checkpoint.cpp",
        "src/composite/direct_ewald_composite_dynamics.cpp",
        "include/betelgeuze/direct_ewald_composite_dynamics.h",
        "betelgeuze_engine_direct_ewald_composite_dynamics",
        "betelgeuze_engine_export_allowlist",
    ):
        if token not in cmake:
            _fail(f"native composite-dynamics build contract is missing: {token}")
    export_test = text("native/tests/check_exports.cmake")
    for symbol in dynamics_symbols:
        if symbol not in export_test:
            _fail(
                "export regression test omitted composite-dynamics symbol: "
                f"{symbol}"
            )

    native_test = text("native/tests/direct_ewald_composite_dynamics.cpp")
    for token in (
        "0.30000000000000004",
        "verify_abi_profile_and_descriptor_transactionality",
        "verify_deep_ownership_and_stable_views",
        "verify_zero_step_matches_stateless",
        "verify_manual_velocity_verlet_and_same_lane_repeat",
        "verify_checkpoint_continuation_and_small_nve",
        "verify_baoab_hip_and_step_overflow_fail_closed",
        "UINT64_MAX",
        "BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE",
        "verify_checkpoint_format_failures_and_output_transactionality",
        "BGDEC001",
        "BGDYN001",
        "verify_checkpoint_fingerprint_mismatches",
    ):
        if token not in native_test:
            _fail(f"composite-dynamics regression coverage is missing: {token}")
    if "ala3" in native_test.lower():
        _fail(
            "non-neutral Ala3 deferral fixture entered composite-dynamics tests"
        )

    sys_source = text("rust/betelgeuze-sys/src/lib.rs")
    for token in (
        "BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION: u32 = 1",
        "pub struct bg_direct_ewald_composite_simulation_v1",
        "pub fn bg_direct_ewald_composite_dynamics_abi_version()",
        "pub fn bg_direct_ewald_composite_simulation_v1_create(",
        "pub fn bg_context_integrate_direct_ewald_composite_v1(",
        "pub fn bg_direct_ewald_composite_simulation_v1_checkpoint_load(",
    ):
        if token not in sys_source:
            _fail(f"Rust raw composite-dynamics ABI binding is missing: {token}")

    sys_manifest = text("rust/betelgeuze-sys/Cargo.toml")
    sys_build = text("rust/betelgeuze-sys/build.rs")
    for token in (
        "abi/direct_ewald_composite_dynamics_header_c11.c",
        "abi/direct_ewald_composite_dynamics_layout_assertions.cpp",
        "vendor/include/betelgeuze/direct_ewald_composite_dynamics.h",
        "vendor/native/src/composite/direct_ewald_composite_dynamics.cpp",
        "vendor/native/src/composite/direct_ewald_composite_checkpoint.cpp",
    ):
        if token not in sys_manifest:
            _fail(f"Rust system package omitted dynamics input: {token}")
    for token in (
        "composite_dynamics_c_header_probe",
        "composite_dynamics_cpp_layout_probe",
    ):
        if token not in sys_build:
            _fail(f"Rust system build omitted dynamics ABI probe: {token}")

    layout_test = text("rust/betelgeuze-sys/tests/layout.rs")
    for token in (
        "direct_ewald_composite_dynamics_reuses_frozen_engine_layouts",
        "size_of::<bg_distance_constraints_v1>(), 104",
        "size_of::<bg_simulation_options_v1>(), 80",
        "size_of::<bg_dynamics_report_v1>(), 104",
        "size_of::<*mut bg_direct_ewald_composite_simulation_v1>()",
    ):
        if token not in layout_test:
            _fail(f"Rust raw composite-dynamics layout coverage is missing: {token}")

    raw_smoke = text("rust/betelgeuze-sys/tests/raw_smoke.rs")
    for token in (
        "direct_ewald_composite_dynamics_identity_and_null_failures_are_transactional",
        "bg_direct_ewald_composite_dynamics_v1_profile_id",
        "bg_context_integrate_direct_ewald_composite_v1",
        "bg_direct_ewald_composite_simulation_v1_checkpoint_write",
    ):
        if token not in raw_smoke:
            _fail(f"Rust raw composite-dynamics smoke coverage is missing: {token}")

    runtime = text(
        "rust/betelgeuze-runtime/src/direct_ewald_composite_dynamics.rs"
    )
    for token in (
        "pub struct DirectEwaldCompositeSimulation",
        "direct_ewald_composite_dynamics_profile_id",
        "BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION",
        "bg_context_integrate_direct_ewald_composite_v1",
        "CHECKPOINT_MAGIC",
        "b\"BGDEC001\"",
    ):
        if token not in runtime:
            _fail(f"safe Rust composite-dynamics boundary is missing: {token}")
    runtime_test = text(
        "rust/betelgeuze-runtime/tests/direct_ewald_composite_dynamics.rs"
    )
    for token in (
        "betelgeuze.native_direct_ewald_composite_dynamics/1.0.0",
        "BGDEC001",
        "checkpoint",
        "integrate",
    ):
        if token not in runtime_test:
            _fail(f"safe Rust composite-dynamics test is missing: {token}")

    for canonical in VENDOR_SHARED_PATHS:
        vendor = f"rust/betelgeuze-sys/vendor/{canonical}"
        if vendor not in sources:
            _fail(f"vendored composite-dynamics dependency is unbound: {vendor}")
        if sources[vendor] != sources[canonical]:
            _fail(f"vendored composite-dynamics dependency drifted: {vendor}")

    production_paths = (
        "native/CMakeLists.txt",
        "native/src/composite/direct_ewald_composite_dynamics.cpp",
        "native/src/composite/direct_ewald_composite_checkpoint.cpp",
        "rust/betelgeuze-runtime/Cargo.toml",
        "rust/betelgeuze-runtime/src/direct_ewald_composite_dynamics.rs",
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
        _fail("composite-dynamics ABI contract changed")
    expected_implementation = {
        **IMPLEMENTATION_CONTRACT_BASE,
        "source_manifest_entry_count": source_count,
        "source_manifest_sha256": _sha256(source_manifest_raw),
    }
    if profile["implementation"] != expected_implementation:
        _fail("composite-dynamics implementation binding changed")
    if profile["validation"] != VALIDATION_CONTRACT:
        _fail("composite-dynamics validation contract changed")
    if profile["authority"] != AUTHORITY_CONTRACT or any(
        value is not False for value in AUTHORITY_CONTRACT.values()
    ):
        _fail("composite-dynamics authority changed")
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
        "frozen_predecessor_file_count": len(
            predecessor["frozen_predecessor_paths"]
        ),
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
            raise NativeDirectEwaldCompositeDynamicsV1Error(
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
        raise NativeDirectEwaldCompositeDynamicsV1Error(
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
            if isinstance(exc, NativeDirectEwaldCompositeDynamicsV1Error):
                details.insert(0, str(exc))
            raise NativeDirectEwaldCompositeDynamicsV1Error(
                "evidence refresh staging failed before commit and temporary "
                "cleanup was incomplete: " + "; ".join(details)
            ) from exc
        if not isinstance(exc, Exception):
            raise
        if isinstance(exc, NativeDirectEwaldCompositeDynamicsV1Error):
            raise
        raise NativeDirectEwaldCompositeDynamicsV1Error(
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
            raise NativeDirectEwaldCompositeDynamicsV1Error(
                "evidence refresh failed and rollback was incomplete: "
                + "; ".join((*rollback_errors, *cleanup_errors))
            ) from exc
        if cleanup_errors:
            raise NativeDirectEwaldCompositeDynamicsV1Error(
                "evidence refresh failed; original evidence was restored but "
                "temporary cleanup was incomplete: "
                + "; ".join(cleanup_errors)
            ) from exc
        if not isinstance(exc, Exception):
            raise
        if isinstance(exc, NativeDirectEwaldCompositeDynamicsV1Error):
            raise
        raise NativeDirectEwaldCompositeDynamicsV1Error(
            "evidence refresh failed; original evidence restored"
        ) from exc

    cleanup_errors = _cleanup_evidence_temporaries((*staged, *rollback))
    if cleanup_errors:
        raise NativeDirectEwaldCompositeDynamicsV1Error(
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
    except NativeDirectEwaldCompositeDynamicsV1Error as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
