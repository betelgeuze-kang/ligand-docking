#!/usr/bin/env python3
"""Verify bounded direct-Ewald composite-dynamics backend preflight v1 evidence."""

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
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile_v1_sources.json"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-"
    "backend-preflight.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_v1.py"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile/1.0.0"
)
PROFILE_ID = (
    "engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_development_v1"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_sources/1.0.0"
)
SOURCE_SCOPE = (
    "direct_ewald_composite_dynamics_backend_preflight_v1_current_sources_"
    "tests_build_export_evidence_and_frozen_predecessor"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
OID_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
PINNED_CHECKOUT_ACTION = (
    "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
)

PREDECESSOR = {
    "merge_commit": "e434295b1711f612e0f7e9fac2d95de92abf19a8",
    "merge_tree": "3546ef29ae708c16c7af1e3be4925d2d7ad1f6b5",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "42aad2692719d3d0233d9b71e24e6b49fe50a27fbc150d31fb4d9688ae84215f"
    ),
    "pull_request": 438,
    "reviewed_head": "581a17a135d75ddf085c4edd29f3763c2f691fcf",
    "source_manifest_entry_count": 113,
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "1a7a284467958e7c153edb0afd86cc5ea4ad07b659266ecf59d9da7549a19d15"
    ),
}

SUCCESSOR_BASE = {
    "commit": "5f6f4e2642dbe5c1272b2a9710288db25db5164f",
    "tree": "95f3d64a553f6c261d59a7ef8bd202561d51c45a",
}

PUBLIC_SYMBOLS = (
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

FROZEN_UNCHANGED_PATHS = (
    Path("include/betelgeuze/engine.h"),
    Path("include/betelgeuze/direct_ewald.h"),
    Path("include/betelgeuze/direct_ewald_composite.h"),
    Path("include/betelgeuze/direct_ewald_composite_dynamics.h"),
    Path("native/src/composite/direct_ewald_composite_checkpoint.cpp"),
    Path(
        "rust/betelgeuze-sys/abi/"
        "direct_ewald_composite_dynamics_header_c11.c"
    ),
    Path(
        "rust/betelgeuze-sys/abi/"
        "direct_ewald_composite_dynamics_layout_assertions.cpp"
    ),
)

SUCCESSOR_EVIDENCE_PATHS = (
    WORKFLOW_RELATIVE_PATH,
    PROFILE_RELATIVE_PATH,
    SOURCE_MANIFEST_RELATIVE_PATH,
    DOC_RELATIVE_PATH,
    UNIT_RELATIVE_PATH,
    VERIFIER_RELATIVE_PATH,
)

SUCCESSOR_SOURCE_PATHS = (
    Path("CMakeLists.txt"),
    WORKFLOW_RELATIVE_PATH,
    DOC_RELATIVE_PATH,
    UNIT_RELATIVE_PATH,
    VERIFIER_RELATIVE_PATH,
    PREDECESSOR_PROFILE_RELATIVE_PATH,
    PREDECESSOR_MANIFEST_RELATIVE_PATH,
)

BOUND_IMPLEMENTATION_DELTAS = {
    "native/src/composite/direct_ewald_composite_dynamics.cpp": {
        "base_byte_count": 35055,
        "base_sha256": "0115c52a7b97cac5cd56a48ce35d3cc2efe76ea4c777fcd97d4ec13a21a8db4f",
        "current_byte_count": 35481,
        "current_sha256": "7d0949d59edefcf188a8d18b95e424fb7361ceaed3f0fc877c9784c03fa3dc0e",
    },
    "native/tests/direct_ewald_composite_dynamics.cpp": {
        "base_byte_count": 70339,
        "base_sha256": "c614b598627358492c350663df6ebeb80f03bf78093d59bb72b1fc94b441d337",
        "current_byte_count": 73642,
        "current_sha256": "b87b139c3e118d98a1b0c6f33e22563824cff191304e23c04a1a202be66d5efc",
    },
    "rust/betelgeuze-runtime/src/direct_ewald_composite_dynamics.rs": {
        "base_byte_count": 24700,
        "base_sha256": "7253fb1efe1e1d054701d0e00b6041ad413d8adc23ef6d4f5ec5b541debf48a9",
        "current_byte_count": 25426,
        "current_sha256": "a3d3168fc98acce341415aa8fcd494923a974e5c42544d8019e57dceb7284fef",
    },
    "rust/betelgeuze-runtime/tests/direct_ewald_composite_dynamics.rs": {
        "base_byte_count": 12084,
        "base_sha256": "7bbdbdba77e417d3c5847c0ed5ebeb549c2e00bcc308aa7a90acf524025e69a4",
        "current_byte_count": 13042,
        "current_sha256": "d9b88b6ab4389f1d98da3473ffbe8e821d46b9c5f48ab47f3ce532816c5de14e",
    },
    "rust/betelgeuze-sys/vendor/native/src/composite/direct_ewald_composite_dynamics.cpp": {
        "base_byte_count": 35055,
        "base_sha256": "0115c52a7b97cac5cd56a48ce35d3cc2efe76ea4c777fcd97d4ec13a21a8db4f",
        "current_byte_count": 35481,
        "current_sha256": "7d0949d59edefcf188a8d18b95e424fb7361ceaed3f0fc877c9784c03fa3dc0e",
    },
}

ORIGINAL_SUCCESSOR_SLICE_PATHS = (
    Path("native/src/composite/direct_ewald_composite_dynamics.cpp"),
    Path("native/tests/direct_ewald_composite_dynamics.cpp"),
    Path("rust/betelgeuze-runtime/src/direct_ewald_composite_dynamics.rs"),
    Path("rust/betelgeuze-runtime/tests/direct_ewald_composite_dynamics.rs"),
    Path(
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "direct_ewald_composite_dynamics.cpp"
    ),
    *SUCCESSOR_EVIDENCE_PATHS,
)

SUCCESSOR_SLICE_CONTRACT = {
    "bound_implementation_delta_count": 5,
    "bound_implementation_deltas": BOUND_IMPLEMENTATION_DELTAS,
    "original_path_count": 11,
    "original_paths": sorted(
        path.as_posix() for path in ORIGINAL_SUCCESSOR_SLICE_PATHS
    ),
    "successor_evidence_path_count": 6,
    "successor_evidence_paths": sorted(
        path.as_posix() for path in SUCCESSOR_EVIDENCE_PATHS
    ),
}

ABI_CONTRACT = {
    "abi_version": 1,
    "abi_version_major": 1,
    "abi_version_minor": 0,
    "abi_version_string": "1.0.0",
    "checkpoint_format_changed": False,
    "checkpoint_header_size_bytes": 104,
    "checkpoint_magic": "BGDEC001",
    "direct_ewald_abi_changed": False,
    "engine_abi_version_changed": False,
    "header": "include/betelgeuze/direct_ewald_composite_dynamics.h",
    "new_public_symbol_added": False,
    "profile_id": "betelgeuze.native_direct_ewald_composite_dynamics/1.0.0",
    "public_symbol_count": 13,
    "public_symbol_set_changed": False,
    "stateful_composite_dynamics_abi_changed": False,
    "stateless_composite_abi_changed": False,
    "symbol_version_node": "BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0",
}

IMPLEMENTATION_CONTRACT_BASE = {
    "auto_request_rejected_even_when_resolved_rust_cpu": True,
    "backend_preflight_only_hardening": True,
    "checkpoint_format_changed": False,
    "cpp_cpu_reference_explicit_request_accepted": True,
    "fixed64_cpu_v7_qualification_invoked": False,
    "hip_device_execution_invoked": False,
    "hip_fast_request_rejected": True,
    "hip_safe_request_rejected": True,
    "hip_to_cpu_fallback": False,
    "molecular_execution_invoked": False,
    "new_model_ownership_introduced": False,
    "new_public_symbol_added": False,
    "preflight_precedes_owner_validation_and_evaluation": True,
    "requested_backend_is_authoritative": True,
    "requested_resolved_cpu_mismatch_rejected": True,
    "requested_resolved_mismatch_status": "BG_STATUS_ABI_MISMATCH",
    "rust_cpu_explicit_request_accepted": True,
    "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "unknown_backend_request_rejected": True,
    "unsupported_request_status": "BG_STATUS_UNSUPPORTED_BACKEND",
    "whole_call_transactional_commit": True,
}

VALIDATION_CONTRACT = {
    "actual_auto_context_requested_auto_resolved_rust_cpu": True,
    "actual_auto_context_rejected": True,
    "actual_auto_rejection_checkpoint_unchanged": True,
    "actual_auto_rejection_report_unchanged": True,
    "actual_auto_rejection_state_unchanged": True,
    "c11_public_header_probe_preserved": True,
    "canonical_vendor_byte_identity": True,
    "cpp_layout_probe_preserved": True,
    "exact_five_implementation_deltas_bound_to_successor_base": True,
    "explicit_cpp_cpu_integration_succeeds": True,
    "explicit_rust_cpu_safe_runtime_covered": True,
    "git_object_probes_lazy_fetch_disabled": True,
    "mach_o_exact_export_allowlist": True,
    "native_mismatch_rejection_report_unchanged": True,
    "native_mismatch_rejection_state_unchanged": True,
    "native_real_auto_rejection": True,
    "optional_local_reviewed_head_tree_checked_when_present": True,
    "public_symbol_version_checked": True,
    "requested_resolved_mismatch_rejected": True,
    "safe_rust_full_preflight_precedes_composite_abi_and_native_integration_call": True,
    "safe_rust_unsupported_request_rejected_before_resolved_backend_query": True,
    "stale_typed_error_cleared_on_native_preflight_rejection": True,
    "standalone_reviewed_head_object_required": False,
    "unsupported_hip_and_unknown_rejection_transactional": True,
    "workflow_all_four_actions_exactly_pinned": True,
    "workflow_global_cpu_only_environment": True,
    "workflow_global_read_only_permissions": True,
    "workflow_no_reservation_supervisor_or_public_benchmark_execution": True,
    "workflow_trigger_covers_bound_tools_init": True,
}

AUTHORITY_CONTRACT = {
    "acceleration_claim_authorized": False,
    "d1_d2_execution_authorized": False,
    "fresh_holdout_execution_authorized": False,
    "hip_device_execution_authorized": False,
    "historical_molecular_ab_execution_authorized": False,
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


class NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error(ValueError):
    """Successor evidence is missing, noncanonical, or outside its boundary."""


def _fail(detail: str) -> NoReturn:
    raise NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error(detail)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            _fail(f"duplicate JSON key: {key}")
        value[key] = item
    return value


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
        raise NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error(
            f"{label} is not canonical ASCII JSON"
        ) from error
    if type(value) is not dict or canonical_bytes(value) != raw:
        _fail(f"{label} is not canonical sorted ASCII JSON")
    return value


def _regular_file(root: Path, relative: Path) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        _fail(f"required regular file is missing: {relative.as_posix()}")
    return path


def _git_environment() -> dict[str, str]:
    return {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }


def _git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["/usr/bin/git", "--no-replace-objects", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        env=_git_environment(),
    )
    if result.returncode != 0 or result.stderr:
        _fail(f"frozen Git object inspection failed: {' '.join(arguments)}")
    return result.stdout


def _reviewed_head_tree_if_present(root: Path, reviewed: str) -> str | None:
    result = subprocess.run(
        [
            "/usr/bin/git",
            "--no-replace-objects",
            "cat-file",
            "--batch-check=%(objectname) %(objecttype)",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        input=f"{reviewed}\n".encode("ascii"),
        env=_git_environment(),
    )
    if result.returncode != 0 or result.stderr:
        _fail("optional reviewed-head Git object inspection failed")
    if result.stdout == f"{reviewed} missing\n".encode("ascii"):
        return None
    if result.stdout != f"{reviewed} commit\n".encode("ascii"):
        _fail("locally present reviewed-head object is not the frozen commit")
    tree = _git(root, "show", "-s", "--format=%T", reviewed).decode("ascii").strip()
    if OID_PATTERN.fullmatch(tree) is None:
        _fail("locally present reviewed-head tree identity is invalid")
    return tree


def require_bound_implementation_deltas(
    root: Path = ROOT,
) -> dict[str, dict[str, object]]:
    base = SUCCESSOR_BASE["commit"]
    tree = SUCCESSOR_BASE["tree"]
    if _git(root, "rev-parse", "--verify", f"{base}^{{commit}}") != (
        f"{base}\n".encode("ascii")
    ):
        _fail("successor base commit changed")
    observed_tree = _git(root, "show", "-s", "--format=%T", base).decode().strip()
    if observed_tree != tree:
        _fail("successor base tree changed")
    _git(root, "merge-base", "--is-ancestor", base, "HEAD")
    if len(BOUND_IMPLEMENTATION_DELTAS) != 5:
        _fail("bound implementation delta definition must contain exactly five paths")
    observed: dict[str, dict[str, object]] = {}
    for path, contract in BOUND_IMPLEMENTATION_DELTAS.items():
        relative = Path(path)
        base_raw = _git(root, "cat-file", "blob", f"{base}:{path}")
        current_raw = _regular_file(root, relative).read_bytes()
        actual = {
            "base_byte_count": len(base_raw),
            "base_sha256": _sha256(base_raw),
            "current_byte_count": len(current_raw),
            "current_sha256": _sha256(current_raw),
        }
        if actual != contract:
            _fail(f"bound implementation delta changed: {path}")
        observed[path] = actual
    return observed


def require_frozen_predecessor(root: Path = ROOT) -> dict[str, object]:
    merge = str(PREDECESSOR["merge_commit"])
    reviewed = str(PREDECESSOR["reviewed_head"])
    if OID_PATTERN.fullmatch(merge) is None or OID_PATTERN.fullmatch(reviewed) is None:
        _fail("frozen predecessor object identity is invalid")
    if _git(root, "rev-parse", "--verify", f"{merge}^{{commit}}") != (
        f"{merge}\n".encode("ascii")
    ):
        _fail("frozen predecessor merge object changed")
    merge_tree = _git(root, "show", "-s", "--format=%T", merge).decode().strip()
    if merge_tree != PREDECESSOR["merge_tree"]:
        _fail("frozen predecessor merge tree changed")
    reviewed_tree = _reviewed_head_tree_if_present(root, reviewed)
    if reviewed_tree is not None and reviewed_tree != merge_tree:
        _fail("locally present reviewed head does not share the frozen merge tree")
    _git(root, "merge-base", "--is-ancestor", merge, "HEAD")

    profile_raw = _git(
        root, "cat-file", "blob", f"{merge}:{PREDECESSOR_PROFILE_RELATIVE_PATH}"
    )
    manifest_raw = _git(
        root, "cat-file", "blob", f"{merge}:{PREDECESSOR_MANIFEST_RELATIVE_PATH}"
    )
    if _sha256(profile_raw) != PREDECESSOR["profile_sha256"]:
        _fail("frozen #438 profile digest changed")
    if _sha256(manifest_raw) != PREDECESSOR["source_manifest_sha256"]:
        _fail("frozen #438 source-manifest digest changed")
    if _regular_file(root, PREDECESSOR_PROFILE_RELATIVE_PATH).read_bytes() != profile_raw:
        _fail("current immutable #438 profile differs from the frozen merge object")
    if _regular_file(root, PREDECESSOR_MANIFEST_RELATIVE_PATH).read_bytes() != manifest_raw:
        _fail("current immutable #438 manifest differs from the frozen merge object")

    profile = _canonical_object(profile_raw, label="frozen #438 profile")
    manifest = _canonical_object(manifest_raw, label="frozen #438 source manifest")
    rows = manifest.get("files")
    if type(rows) is not list or len(rows) != PREDECESSOR["source_manifest_entry_count"]:
        _fail("frozen #438 source count changed")
    paths: list[str] = []
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != {"byte_count", "path", "sha256"}:
            _fail(f"frozen #438 source row {index} shape changed")
        path = row["path"]
        if type(path) is not str:
            _fail(f"frozen #438 source row {index} path changed")
        paths.append(path)
    if paths != sorted(set(paths)):
        _fail("frozen #438 source paths changed")
    implementation = profile.get("implementation")
    if (
        type(implementation) is not dict
        or implementation.get("source_manifest_entry_count") != len(rows)
        or implementation.get("source_manifest_sha256")
        != PREDECESSOR["source_manifest_sha256"]
    ):
        _fail("frozen #438 profile-to-manifest binding changed")

    frozen_digests: dict[str, str] = {}
    for relative in FROZEN_UNCHANGED_PATHS:
        historical = _git(root, "cat-file", "blob", f"{merge}:{relative.as_posix()}")
        current = _regular_file(root, relative).read_bytes()
        if current != historical:
            _fail(f"ABI/checkpoint bytes changed since #438: {relative.as_posix()}")
        frozen_digests[relative.as_posix()] = _sha256(historical)
    return {
        "merge_commit": merge,
        "merge_tree": merge_tree,
        "reviewed_head": reviewed,
        "reviewed_head_locally_present": reviewed_tree is not None,
        "source_paths": tuple(Path(path) for path in paths),
        "frozen_unchanged_digests": frozen_digests,
    }


def discover_source_paths(root: Path = ROOT) -> tuple[Path, ...]:
    predecessor = require_frozen_predecessor(root)
    source_paths = predecessor["source_paths"]
    assert isinstance(source_paths, tuple)
    paths = set(source_paths)
    paths.update(SUCCESSOR_SOURCE_PATHS)
    if PROFILE_RELATIVE_PATH in paths or SOURCE_MANIFEST_RELATIVE_PATH in paths:
        _fail("successor profile or manifest entered its own hash closure")
    for relative in paths:
        _regular_file(root, relative)
    return tuple(sorted(paths, key=lambda path: path.as_posix()))


def build_source_manifest(root: Path = ROOT) -> dict[str, object]:
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
    return {
        "files": files,
        "schema_id": SOURCE_SCHEMA_ID,
        "scope": SOURCE_SCOPE,
        "successor_evidence_paths": sorted(
            path.as_posix() for path in SUCCESSOR_EVIDENCE_PATHS
        ),
    }


def require_source_manifest(
    root: Path, raw: bytes
) -> tuple[dict[str, object], dict[str, bytes]]:
    manifest = _canonical_object(raw, label="successor source manifest")
    if set(manifest) != {
        "files",
        "schema_id",
        "scope",
        "successor_evidence_paths",
    }:
        _fail("successor source-manifest keys changed")
    if manifest["schema_id"] != SOURCE_SCHEMA_ID or manifest["scope"] != SOURCE_SCOPE:
        _fail("successor source-manifest identity changed")
    expected_evidence_paths = sorted(
        path.as_posix() for path in SUCCESSOR_EVIDENCE_PATHS
    )
    if manifest["successor_evidence_paths"] != expected_evidence_paths:
        _fail("successor evidence path metadata changed")
    rows = manifest["files"]
    if type(rows) is not list or not rows:
        _fail("successor source manifest must contain files")
    expected = [path.as_posix() for path in discover_source_paths(root)]
    observed: list[str] = []
    for index, row in enumerate(rows):
        if type(row) is not dict or set(row) != {"byte_count", "path", "sha256"}:
            _fail(f"successor source row {index} shape changed")
        path = row["path"]
        size = row["byte_count"]
        digest = row["sha256"]
        if type(path) is not str or not path:
            _fail(f"successor source row {index} path is invalid")
        relative = Path(path)
        if relative.is_absolute() or relative.as_posix() != path or ".." in relative.parts:
            _fail(f"successor source row {index} path is not normalized")
        if type(size) is not int or size < 0:
            _fail(f"successor source row {index} byte count is invalid")
        if type(digest) is not str or SHA256_PATTERN.fullmatch(digest) is None:
            _fail(f"successor source row {index} digest is invalid")
        observed.append(path)
    if observed != sorted(set(observed)) or observed != expected:
        _fail("successor source path closure must be exact, sorted, and unique")
    sources: dict[str, bytes] = {}
    for row in rows:
        assert isinstance(row, dict)
        path = str(row["path"])
        payload = _regular_file(root, Path(path)).read_bytes()
        if len(payload) != row["byte_count"] or _sha256(payload) != row["sha256"]:
            _fail(f"successor source bytes drifted: {path}")
        sources[path] = payload
    if manifest != build_source_manifest(root):
        _fail("successor source manifest differs from the exact current closure")
    _require_source_contract(sources)
    return manifest, sources


def _text(sources: dict[str, bytes], path: str) -> str:
    try:
        return sources[path].decode("utf-8")
    except KeyError as error:
        raise NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error(
            f"required successor source is unbound: {path}"
        ) from error
    except UnicodeError as error:
        raise NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error(
            f"required successor source is not UTF-8: {path}"
        ) from error


def _require_tokens(text: str, tokens: tuple[str, ...], *, label: str) -> None:
    for token in tokens:
        if token not in text:
            _fail(f"{label} is missing exact contract token: {token}")


def _source_function(text: str, start_token: str) -> str:
    start = text.find(start_token)
    if start < 0:
        _fail(f"native preflight function is missing: {start_token}")
    return text[start:]


def _is_dynamics_symbol(symbol: str) -> bool:
    return (
        symbol.startswith("bg_direct_ewald_composite_dynamics_")
        or symbol.startswith("bg_direct_ewald_composite_simulation_v1_")
        or symbol == "bg_context_integrate_direct_ewald_composite_v1"
    )


def _require_workflow_contract(workflow: str) -> None:
    permission_headers = re.findall(
        r"(?m)^[ \t]*permissions:[ \t]*(?:#.*)?$", workflow
    )
    if (
        len(permission_headers) != 1
        or workflow.count("permissions:") != 1
        or "permissions:\n  contents: read\n\nconcurrency:" not in workflow
        or re.search(r"(?m)^[ \t]+permissions:[ \t]*(?:#.*)?$", workflow)
        is not None
    ):
        _fail("workflow must have exactly one global contents-read permissions block")
    if re.search(
        r"(?m)^[ \t]+(?:actions|checks|contents|deployments|id-token|issues|"
        r"packages|pages|pull-requests|repository-projects|security-events|"
        r"statuses):[ \t]+write(?:-all)?[ \t]*(?:#.*)?$",
        workflow,
    ):
        _fail("workflow contains a write permission scope")

    cpu_environment = (
        'env:\n'
        '  CUDA_VISIBLE_DEVICES: ""\n'
        '  HIP_VISIBLE_DEVICES: ""\n'
        '  ROCR_VISIBLE_DEVICES: ""\n\n'
        'jobs:'
    )
    if workflow.count(cpu_environment) != 1:
        _fail("workflow global CPU-only environment changed")
    for variable in (
        "CUDA_VISIBLE_DEVICES:",
        "HIP_VISIBLE_DEVICES:",
        "ROCR_VISIBLE_DEVICES:",
    ):
        if workflow.count(variable) != 1:
            _fail(f"workflow must set {variable} exactly once and globally")

    configuration_starts = [
        match.start()
        for match in re.finditer(r"(?m)^[ \t]+cmake -S \. -B ", workflow)
    ]
    if len(configuration_starts) != 3:
        _fail("workflow must contain exactly three focused CMake configurations")
    for start in configuration_starts:
        end = workflow.find("\n          cmake --build ", start)
        if end < 0:
            _fail("workflow CMake configuration is not followed by its focused build")
        configuration = workflow[start:end]
        if (
            configuration.count("-DBG_ENABLE_HIP=OFF") != 1
            or configuration.count("-DBG_ENABLE_HIP_SAFE=OFF") != 1
            or "-DBG_ENABLE_HIP=ON" in configuration
            or "-DBG_ENABLE_HIP_SAFE=ON" in configuration
        ):
            _fail("every workflow CMake configuration must disable both HIP lanes")

    uses_lines = re.findall(r"(?m)^[^\n]*\buses:[^\n]*$", workflow)
    parsed_uses: list[str] = []
    for line in uses_lines:
        match = re.fullmatch(
            r"[ ]{8}uses:[ ]+([^# \t]+)(?:[ \t]+#.*)?", line
        )
        if match is None:
            _fail("workflow contains an unparseable uses entry")
        parsed_uses.append(match.group(1))
    if len(parsed_uses) != 4 or any(
        entry != PINNED_CHECKOUT_ACTION for entry in parsed_uses
    ):
        _fail("all four workflow uses entries must equal the exact checkout pin")

    pull_start = workflow.find("  pull_request:\n")
    push_start = workflow.find("  push:\n", pull_start)
    dispatch_start = workflow.find("  workflow_dispatch:\n", push_start)
    if min(pull_start, push_start, dispatch_start) < 0:
        _fail("workflow event path-filter structure changed")
    tools_init_path = '      - "tools/__init__.py"\n'
    pull_section = workflow[pull_start:push_start]
    push_section = workflow[push_start:dispatch_start]
    if (
        pull_section.count(tools_init_path) != 1
        or push_section.count(tools_init_path) != 1
        or workflow.count(tools_init_path) != 2
    ):
        _fail("workflow pull and push filters must both cover bound tools/__init__.py")

    lowered_workflow = workflow.lower()
    for forbidden in (
        "reservation",
        "supervisor",
        "public_benchmark",
        "public-benchmark",
    ):
        if forbidden in lowered_workflow:
            _fail(
                "workflow contains prohibited reservation, root-supervisor, "
                "or public-benchmark token"
            )


def _require_source_contract(sources: dict[str, bytes]) -> None:
    for path, payload in sources.items():
        if path.startswith(("include/", "native/src/")):
            vendor = f"rust/betelgeuze-sys/vendor/{path}"
            if vendor in sources and sources[vendor] != payload:
                _fail(f"canonical and vendored source bytes differ: {path}")

    header = _text(sources, "include/betelgeuze/direct_ewald_composite_dynamics.h")
    _require_tokens(
        header,
        (
            "BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MAJOR UINT32_C(1)",
            "BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MINOR UINT32_C(0)",
            'uses magic "BGDEC001"',
            *PUBLIC_SYMBOLS,
        ),
        label="frozen direct-Ewald composite-dynamics public header",
    )
    declared = tuple(
        symbol
        for symbol in re.findall(r"\b(bg_[a-z0-9_]+)\s*\(", header)
        if _is_dynamics_symbol(symbol)
    )
    if declared != PUBLIC_SYMBOLS or len(PUBLIC_SYMBOLS) != 13:
        _fail("direct-Ewald composite-dynamics public symbol set changed")
    if "backend_preflight" in header:
        _fail("backend preflight introduced a public ABI declaration")

    implementation = _text(
        sources, "native/src/composite/direct_ewald_composite_dynamics.cpp"
    )
    function = _source_function(
        implementation, "bg_context_integrate_direct_ewald_composite_v1("
    )
    native_tokens = (
        "clear_typed_error(out_error);",
        "switch (context->requested_backend)",
        "case BG_BACKEND_CPP_CPU_REFERENCE:",
        "case BG_BACKEND_RUST_CPU:",
        "case BG_BACKEND_AUTO:",
        "case BG_BACKEND_HIP_SAFE:",
        "case BG_BACKEND_HIP_FAST:",
        "BG_STATUS_UNSUPPORTED_BACKEND",
        "direct-Ewald composite dynamics supports only explicitly requested CPU backends",
        "context->backend != context->requested_backend",
        "BG_STATUS_ABI_MISMATCH",
        "direct-Ewald composite dynamics requested and resolved CPU backends must match",
        "validate_owner_invariant(*simulation)",
        "DynamicStateRollback rollback(",
        "betelgeuze::native::dynamics::integrate(",
        "rollback.commit();",
        "*out_report = report;",
    )
    _require_tokens(function, native_tokens, label="native requested-backend preflight")
    positions = [function.find(token) for token in native_tokens]
    ordered = (
        positions[0]
        < positions[1]
        < positions[8]
        < positions[9]
        < positions[11]
        < positions[12]
        < positions[13]
        < positions[14]
        < positions[15]
        < positions[16]
    )
    if not ordered:
        _fail("native preflight no longer precedes owner validation/evaluation/commit")
    if "switch (context->backend)" in function:
        _fail("resolved backend incorrectly replaced the immutable request preflight")

    native_test = _text(sources, "native/tests/direct_ewald_composite_dynamics.cpp")
    _require_tokens(
        native_test,
        (
            "verify_baoab_hip_and_step_overflow_fail_closed",
            "static_cast<bg_backend>(INT32_C(0x7fffffff))",
            "const ContextPtr auto_context = make_context(BG_BACKEND_AUTO);",
            "auto_context->requested_backend == BG_BACKEND_AUTO",
            "auto_context->backend == BG_BACKEND_RUST_CPU",
            "composite dynamics accepted an AUTO request resolved to Rust CPU",
            "std::memcmp(\n            &auto_report, &auto_report_before",
            "AUTO rejection retained a typed Ewald error",
            "AUTO rejection changed state",
            "mismatched_context.requested_backend = BG_BACKEND_CPP_CPU_REFERENCE;",
            "mismatched_context.backend = BG_BACKEND_RUST_CPU;",
            "BG_STATUS_ABI_MISMATCH",
            "requested/resolved mismatch changed report",
            "requested/resolved mismatch changed state",
            "integrate_success(context.get(), simulation.get(), UINT64_C(1));",
        ),
        label="native backend-preflight regression tests",
    )

    runtime = _text(
        sources, "rust/betelgeuze-runtime/src/direct_ewald_composite_dynamics.rs"
    )
    _require_tokens(
        runtime,
        (
            "self.require_direct_ewald_composite_dynamics_backend()?;",
            "ensure_composite_dynamics_abi_compatibility()?;",
            "let requested = self.requested_backend();",
            "require_direct_ewald_backend(requested)?;",
            "let resolved = self.backend().map_err(DirectEwaldError::from)?;",
            "require_direct_ewald_backend(resolved)?;",
            "if resolved != requested",
            "native context resolved {resolved:?} after explicit {requested:?} request",
            "sys::bg_context_integrate_direct_ewald_composite_v1(",
        ),
        label="safe Rust backend preflight",
    )
    integrate_start = runtime.find("pub fn integrate_direct_ewald_composite(")
    helper_start = runtime.find(
        "fn require_direct_ewald_composite_dynamics_backend", integrate_start
    )
    if integrate_start < 0 or helper_start < 0:
        _fail("safe Rust integration/preflight function boundary is missing")
    integrate_function = runtime[integrate_start:helper_start]
    integration_order = (
        "self.require_direct_ewald_composite_dynamics_backend()?;",
        "ensure_composite_dynamics_abi_compatibility()?;",
        "sys::bg_context_integrate_direct_ewald_composite_v1(",
    )
    integration_positions = [
        integrate_function.find(token) for token in integration_order
    ]
    if any(position < 0 for position in integration_positions) or (
        integration_positions != sorted(integration_positions)
    ):
        _fail("safe Rust preflight must precede ABI and native integration access")
    helper_function = runtime[helper_start:]
    helper_order = (
        "let requested = self.requested_backend();",
        "require_direct_ewald_backend(requested)?;",
        "let resolved = self.backend().map_err(DirectEwaldError::from)?;",
        "if resolved != requested",
        "native context resolved {resolved:?} after explicit {requested:?} request",
        "require_direct_ewald_backend(resolved)?;",
    )
    helper_positions = [helper_function.find(token) for token in helper_order]
    if any(position < 0 for position in helper_positions) or (
        helper_positions != sorted(helper_positions)
    ):
        _fail(
            "safe Rust helper must check request, resolve, reject mismatch as ABI, "
            "then validate resolved support"
        )

    runtime_test = _text(
        sources, "rust/betelgeuze-runtime/tests/direct_ewald_composite_dynamics.rs"
    )
    _require_tokens(
        runtime_test,
        (
            "fn auto_request_fails_closed_and_preserves_every_dynamic_byte()",
            "Context::new(ContextOptions::auto(0))",
            "AUTO must not inherit its resolved CPU lane",
            "assert_eq!(error.status, ErrorCode::UnsupportedBackend);",
            "assert_eq!(error.code, None);",
            "assert_eq!(simulation.absolute_step().unwrap(), initial_step);",
            "assert_snapshot_bits(&initial_snapshot, &simulation.snapshot().unwrap());",
            "assert_eq!(simulation.checkpoint().unwrap(), initial_checkpoint);",
        ),
        label="safe Rust real-AUTO transactionality test",
    )

    checkpoint = _text(
        sources, "native/src/composite/direct_ewald_composite_checkpoint.cpp"
    )
    _require_tokens(
        checkpoint,
        (
            "constexpr std::size_t kHeaderSize = 104U",
            "'B', 'G', 'D', 'E', 'C', '0', '0', '1'",
            "sha256_with_zero_range",
        ),
        label="unchanged composite checkpoint",
    )

    version_map = _text(sources, "native/betelgeuze_engine.map")
    exports = _text(sources, "native/betelgeuze_engine.exports")
    export_test = _text(sources, "native/tests/check_exports.cmake")
    mapped = tuple(
        symbol
        for symbol in re.findall(r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+);[ \t]*$", version_map)
        if _is_dynamics_symbol(symbol)
    )
    exported = tuple(
        line[1:]
        for line in exports.splitlines()
        if line.startswith("_") and _is_dynamics_symbol(line[1:])
    )
    if mapped != PUBLIC_SYMBOLS or exported != PUBLIC_SYMBOLS:
        _fail("ELF or Mach-O direct-Ewald composite-dynamics symbol set changed")
    version_node = re.search(
        r"BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1\.0 \{\n"
        r"[ \t]+global:\n(?P<body>.*?)\n"
        r"\} BETELGEUZE_DIRECT_EWALD_COMPOSITE_1\.0;",
        version_map,
        flags=re.DOTALL,
    )
    if version_node is None:
        _fail("exact composite-dynamics ELF version node or parent changed")
    node_symbols = tuple(
        re.findall(
            r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+);[ \t]*$",
            version_node.group("body"),
        )
    )
    if node_symbols != PUBLIC_SYMBOLS:
        _fail("exact composite-dynamics ELF version-node membership changed")
    for symbol in PUBLIC_SYMBOLS:
        if symbol not in export_test:
            _fail(f"export regression test omitted unchanged symbol: {symbol}")
    export_block = re.search(
        r"set\(direct_ewald_composite_dynamics_v1_symbols\n"
        r"(?P<body>.*?)\n\)",
        export_test,
        flags=re.DOTALL,
    )
    if export_block is None:
        _fail("export regression test lost the composite-dynamics symbol group")
    export_block_symbols = tuple(
        re.findall(r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+)[ \t]*$", export_block.group("body"))
    )
    if export_block_symbols != PUBLIC_SYMBOLS:
        _fail("export regression composite-dynamics group membership changed")
    _require_tokens(
        export_test,
        (
            'list(FIND direct_ewald_composite_dynamics_v1_symbols "${unversioned}" direct_ewald_composite_dynamics_v1_index)',
            "elseif(NOT direct_ewald_composite_dynamics_v1_index EQUAL -1)\n"
            '            set(expected_version "BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0")',
            'if(NOT symbol MATCHES "@@${expected_version}$")',
        ),
        label="exact export-version regression mapping",
    )
    if "backend_preflight" in version_map or "backend_preflight" in exports:
        _fail("backend preflight introduced an exported symbol")

    cmake = _text(sources, "native/CMakeLists.txt")
    sys_manifest = _text(sources, "rust/betelgeuze-sys/Cargo.toml")
    sys_build = _text(sources, "rust/betelgeuze-sys/build.rs")
    _require_tokens(
        cmake,
        (
            "src/composite/direct_ewald_composite_dynamics.cpp",
            "tests/direct_ewald_composite_dynamics.cpp",
            "betelgeuze_engine_direct_ewald_composite_dynamics",
            "betelgeuze_engine_export_allowlist",
        ),
        label="focused native build integration",
    )
    _require_tokens(
        sys_manifest,
        (
            "abi/direct_ewald_composite_dynamics_header_c11.c",
            "abi/direct_ewald_composite_dynamics_layout_assertions.cpp",
            "vendor/native/src/composite/direct_ewald_composite_dynamics.cpp",
        ),
        label="Rust sys packaged source integration",
    )
    _require_tokens(
        sys_build,
        (
            "composite_dynamics_c_header_probe",
            "composite_dynamics_cpp_layout_probe",
            "abi/direct_ewald_composite_dynamics_header_c11.c",
            "abi/direct_ewald_composite_dynamics_layout_assertions.cpp",
        ),
        label="Rust sys ABI probes",
    )

    workflow = _text(sources, WORKFLOW_RELATIVE_PATH.as_posix())
    _require_tokens(
        workflow,
        (
            "permissions:\n  contents: read",
            PINNED_CHECKOUT_ACTION,
            "fetch-depth: 0",
            str(PREDECESSOR["merge_commit"]),
            str(PREDECESSOR["merge_tree"]),
            str(PREDECESSOR["reviewed_head"]),
            str(PREDECESSOR["profile_sha256"]),
            str(PREDECESSOR["source_manifest_sha256"]),
            "git fetch --no-tags --depth=1 origin refs/pull/438/head\n"
            '          test "$(git rev-parse FETCH_HEAD)" = "$reviewed"\n'
            '          test "$(git rev-parse FETCH_HEAD^{tree})" = "$tree"',
            str(SUCCESSOR_BASE["commit"]),
            str(SUCCESSOR_BASE["tree"]),
            VERIFIER_RELATIVE_PATH.as_posix(),
            UNIT_RELATIVE_PATH.as_posix(),
            "betelgeuze_engine_direct_ewald_composite_dynamics",
            "betelgeuze_engine_export_allowlist",
            "--test direct_ewald_composite_dynamics",
            "cargo doc --manifest-path rust/Cargo.toml --locked",
            "runs-on: macos-15",
            '      - "tools/__init__.py"',
            'CUDA_VISIBLE_DEVICES: ""',
            'HIP_VISIBLE_DEVICES: ""',
            'ROCR_VISIBLE_DEVICES: ""',
            "-DBG_ENABLE_HIP=OFF",
            "-DBG_ENABLE_HIP_SAFE=OFF",
        ),
        label="pinned successor workflow",
    )
    _require_workflow_contract(workflow)
    for forbidden in (
        "--refresh",
        "self-hosted",
        "pull_request_target",
        "workflow_run",
        "fixed64-cpu-qualify",
        "qualification_v7_execution",
        "BG_REQUIRE_HIP_DEVICE",
        "molecular_execution",
    ):
        if forbidden in workflow:
            _fail(f"successor workflow contains prohibited authority token: {forbidden}")

    documentation = _text(sources, DOC_RELATIVE_PATH.as_posix())
    _require_tokens(
        documentation,
        (
            "requested backend is authoritative",
            "real `AUTO` context",
            "`BG_STATUS_ABI_MISMATCH`",
            "report, typed-error, and dynamic-state transactionality",
            "No ABI, public-symbol, owner, or checkpoint-format change",
            "all 32 unresolved operational decisions",
            "A shallow standalone checkout may omit that reviewed",
            "if the object is locally present, its tree must equal",
            "`GIT_NO_LAZY_FETCH=1`",
            "explicitly fetches `refs/pull/438/head`",
        ),
        label="successor boundary documentation",
    )


def build_profile(*, manifest_raw: bytes, source_count: int) -> dict[str, object]:
    implementation = dict(IMPLEMENTATION_CONTRACT_BASE)
    implementation["source_manifest_entry_count"] = source_count
    implementation["source_manifest_sha256"] = _sha256(manifest_raw)
    return {
        "abi": dict(ABI_CONTRACT),
        "authority": dict(AUTHORITY_CONTRACT),
        "implementation": implementation,
        "operational_boundary": {
            "blockers": list(OPERATIONAL_BLOCKERS),
            "unresolved_operational_decisions": 32,
        },
        "predecessor": dict(PREDECESSOR),
        "profile_id": PROFILE_ID,
        "roadmap_issue": 434,
        "schema_id": SCHEMA_ID,
        "successor_base": dict(SUCCESSOR_BASE),
        "successor_slice": {
            "bound_implementation_delta_count": 5,
            "bound_implementation_deltas": {
                path: dict(contract)
                for path, contract in BOUND_IMPLEMENTATION_DELTAS.items()
            },
            "original_path_count": 11,
            "original_paths": list(SUCCESSOR_SLICE_CONTRACT["original_paths"]),
            "successor_evidence_path_count": 6,
            "successor_evidence_paths": list(
                SUCCESSOR_SLICE_CONTRACT["successor_evidence_paths"]
            ),
        },
        "validation": dict(VALIDATION_CONTRACT),
    }


def require_profile(
    raw: bytes, *, source_manifest_raw: bytes, source_count: int
) -> dict[str, object]:
    profile = _canonical_object(raw, label="successor profile")
    expected = build_profile(
        manifest_raw=source_manifest_raw, source_count=source_count
    )
    if profile != expected:
        _fail("successor profile contract or source binding changed")
    if any(value is not False for value in profile["authority"].values()):
        _fail("successor authority must remain entirely false")
    return profile


def verify(root: Path = ROOT) -> dict[str, object]:
    deltas = require_bound_implementation_deltas(root)
    predecessor = require_frozen_predecessor(root)
    manifest_raw = _regular_file(root, SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest, _ = require_source_manifest(root, manifest_raw)
    rows = manifest["files"]
    assert isinstance(rows, list)
    profile_raw = _regular_file(root, PROFILE_RELATIVE_PATH).read_bytes()
    require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
    )
    return {
        "all_authority_false": True,
        "fixed64_cpu_v7_qualification_invoked": False,
        "frozen_predecessor_merge_commit": predecessor["merge_commit"],
        "frozen_predecessor_source_count": PREDECESSOR["source_manifest_entry_count"],
        "frozen_reviewed_head_locally_present": predecessor[
            "reviewed_head_locally_present"
        ],
        "hip_device_execution_invoked": False,
        "molecular_execution_invoked": False,
        "operational_blocker_count": len(OPERATIONAL_BLOCKERS),
        "profile_path": PROFILE_RELATIVE_PATH.as_posix(),
        "profile_sha256": _sha256(profile_raw),
        "source_count": len(rows),
        "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
        "source_manifest_sha256": _sha256(manifest_raw),
        "successor_base_commit": SUCCESSOR_BASE["commit"],
        "bound_implementation_delta_count": len(deltas),
        "original_successor_slice_path_count": 11,
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
            _fail(f"invalid evidence path: {relative.as_posix()}")
        path = root / relative
        if path in seen:
            _fail(f"duplicate evidence path: {relative.as_posix()}")
        seen.add(path)
        if path.parent.is_symlink() or not path.parent.is_dir() or path.is_symlink():
            _fail(f"unsafe evidence target: {relative.as_posix()}")
        existed = path.exists()
        if existed and not path.is_file():
            _fail(f"evidence target is not a regular file: {relative.as_posix()}")
        snapshots.append(
            (
                path,
                existed,
                path.read_bytes() if existed else b"",
                (path.stat().st_mode & 0o777) if existed else 0o644,
            )
        )
    try:
        for (path, _, _, mode), (_, raw) in zip(snapshots, evidence, strict=True):
            staged.append(_stage(path, raw, mode))
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
            raise NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error(
                "evidence refresh failed and rollback was incomplete: "
                + "; ".join(restoration_errors)
            ) from error
        raise
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)


def refresh(root: Path = ROOT) -> dict[str, object]:
    require_bound_implementation_deltas(root)
    require_frozen_predecessor(root)
    manifest_raw = canonical_bytes(build_source_manifest(root))
    manifest = _canonical_object(manifest_raw, label="generated successor manifest")
    rows = manifest["files"]
    assert isinstance(rows, list)
    profile_raw = canonical_bytes(
        build_profile(manifest_raw=manifest_raw, source_count=len(rows))
    )
    result = _replace_evidence(
        root,
        (
            (SOURCE_MANIFEST_RELATIVE_PATH, manifest_raw),
            (PROFILE_RELATIVE_PATH, profile_raw),
        ),
    )
    result["refreshed"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="explicitly regenerate the acyclic successor manifest and profile",
    )
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        report = refresh(ROOT) if arguments.refresh else verify(ROOT)
    except (OSError, NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error) as error:
        print(f"backend-preflight evidence verification failed: {error}", file=sys.stderr)
        return 1
    if arguments.json:
        print(json.dumps(report, allow_nan=False, indent=2, sort_keys=True))
    else:
        print(
            "direct-Ewald composite-dynamics backend preflight verified: "
            f"profile={report['profile_sha256']} "
            f"manifest={report['source_manifest_sha256']} "
            f"sources={report['source_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
