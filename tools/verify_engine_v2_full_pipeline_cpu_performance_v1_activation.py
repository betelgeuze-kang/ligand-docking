#!/usr/bin/env python3
"""Verify the exact-main, non-consuming full-pipeline CPU activation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTIVATION = (
    REPOSITORY_ROOT
    / "config/engine_v2_full_pipeline_cpu_performance_v1_activation.json"
)
DEFAULT_STDLIB_CLOSURE = (
    REPOSITORY_ROOT
    / "config/engine_v2_full_pipeline_cpu_performance_v1_stdlib_closure.json"
)
DEFAULT_DYNAMIC_CLOSURE = (
    REPOSITORY_ROOT
    / "config/engine_v2_full_pipeline_cpu_performance_v1_dynamic_library_closure.json"
)
DEFAULT_PREINIT_CLOSURE = (
    REPOSITORY_ROOT
    / "config/engine_v2_full_pipeline_cpu_performance_v1_preinit_executable_closure.json"
)
DEFAULT_PROFILE = (
    REPOSITORY_ROOT / "config/engine_v2_full_pipeline_cpu_performance_v1.json"
)
DEFAULT_PROFILE_VERIFIER = (
    REPOSITORY_ROOT / "tools/verify_engine_v2_full_pipeline_cpu_performance_v1.py"
)
DEFAULT_MEASUREMENT_CORE = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/full_pipeline_cpu_performance_v1.py"
)
DEFAULT_RUNNER = (
    REPOSITORY_ROOT / "tools/run_engine_v2_full_pipeline_cpu_performance_v1.py"
)
DEFAULT_NATIVE_CONSUMER = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/native_fixed64_consumers.py"
)
DEFAULT_NATIVE_PARITY = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/native_cpu_parity.py"
)
DEFAULT_HOST_PREFLIGHT = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/performance_host_preflight_v3.py"
)
DEFAULT_ACTIVATION_MODULE = (
    REPOSITORY_ROOT
    / "betelgeuze_engine_v2/docking/full_pipeline_cpu_performance_v1_activation.py"
)
DEFAULT_PREFLIGHT_TOOL = (
    REPOSITORY_ROOT
    / "tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py"
)
DEFAULT_TEST = (
    REPOSITORY_ROOT
    / "tests/unit/test_verify_engine_v2_full_pipeline_cpu_performance_v1_activation.py"
)
DEFAULT_PREFLIGHT_TEST = (
    REPOSITORY_ROOT
    / "tests/unit/test_engine_v2_full_pipeline_cpu_performance_v1_activation.py"
)
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_full_pipeline_cpu_performance_v1_activation.md"
)
DEFAULT_WORKFLOWS = (
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-main.yml",
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml",
    REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml",
)

ACTIVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_full_pipeline_cpu_performance_activation/1.0.0"
)
ACTIVATION_ID = "engine_v2_full_pipeline_cpu_performance_v1_activation"
PROFILE_ID = "engine_v2_full_pipeline_cpu_performance_v1"
PROFILE_SHA256 = "385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000"
ACTIVATION_SHA256 = "1090ae48ccd5d11dbc904ebbf43b8b3dddf4cf608a25b0b24bf3f1cc3996b0fa"
STDLIB_CLOSURE_SHA256 = (
    "d892595cc2bb59aae3fbf7100da9e6b52809082dd5cbc2edb2646811d0b58e35"
)
DYNAMIC_CLOSURE_SHA256 = (
    "a5c56fd7ac0c26224e2282f88e54ff3a4e19c6a1d52263407f03d156199e7352"
)
PREINIT_CLOSURE_SHA256 = (
    "282e17c72a82f0dc3e968e74fc2072371d7673dacf84b18985b2c2253c305558"
)
FOUNDATION_COMMIT_OID = "38c16136a1e2cc126517ff9b50a05f06c5795adb"
FOUNDATION_COMMIT_SHA256 = (
    "1b478ee3b9737e9d50fc854fb4bde93cbd1efd48015a27df52199a698d17e82e"
)
FOUNDATION_TREE_OID = "e36d1cf0915350556ac4202e11d6176fabf5e797"
FOUNDATION_TREE_SHA256 = (
    "69998e9df4740c927568b41e21eb8b94185d4fa3b9dd5fa37d71bcbbd5060579"
)

SOURCE_BINDINGS = {
    "profile_sha256": PROFILE_SHA256,
    "profile_verifier_sha256": (
        "b05d9e9710cc9594eba4a0630420dfbc1204dba9e89c63332a0f10bbc541e880"
    ),
    "measurement_core_sha256": (
        "c27657f104248973f11f6da498fc08da460cb6d4823719139762ce76b0cd18d7"
    ),
    "runner_tool_sha256": (
        "bfaf4bc25b2161a43e1e01418394c716d4b762fd39ec6708a01791159916e6e8"
    ),
    "native_consumer_sha256": (
        "ea4fb7953d2bb2c1e4e16380dd3ad362d4fa8265bf0c11d26d69dfed3cc8df25"
    ),
    "native_cpu_parity_sha256": (
        "cbff9243caea510e070067663e7c36c216afc84e226b9ade3e37b03e6ac30f75"
    ),
    "host_preflight_sha256": (
        "236496cb7342040191db51f6c801948ab1c6b859d09a85b35e3c8a9c00a38adf"
    ),
    "merged_main_commit_sha256": FOUNDATION_COMMIT_SHA256,
    "merged_main_tree_sha256": FOUNDATION_TREE_SHA256,
    "stdlib_import_closure_manifest_sha256": STDLIB_CLOSURE_SHA256,
    "preinit_executable_closure_manifest_sha256": PREINIT_CLOSURE_SHA256,
    "dynamic_library_closure_manifest_sha256": DYNAMIC_CLOSURE_SHA256,
}
SOURCE_PATHS = {
    "profile_sha256": DEFAULT_PROFILE,
    "profile_verifier_sha256": DEFAULT_PROFILE_VERIFIER,
    "measurement_core_sha256": DEFAULT_MEASUREMENT_CORE,
    "runner_tool_sha256": DEFAULT_RUNNER,
    "native_consumer_sha256": DEFAULT_NATIVE_CONSUMER,
    "native_cpu_parity_sha256": DEFAULT_NATIVE_PARITY,
    "host_preflight_sha256": DEFAULT_HOST_PREFLIGHT,
    "stdlib_import_closure_manifest_sha256": DEFAULT_STDLIB_CLOSURE,
    "preinit_executable_closure_manifest_sha256": DEFAULT_PREINIT_CLOSURE,
    "dynamic_library_closure_manifest_sha256": DEFAULT_DYNAMIC_CLOSURE,
}

AUTHORITY_KEYS = frozenset(
    {
        "fresh_holdout_execution_authorized",
        "hip_device_execution_authorized",
        "historical_ab_execution_authorized",
        "molecular_execution_authorized",
        "product_execution_authorized",
        "product_performance_claim_authorized",
        "public_benchmark_authorized",
        "reservation_authorized",
        "scientific_claim_authorized",
        "stage0_admission_authorized",
        "synthetic_cpu_performance_qualification_authorized",
    }
)


class FullPipelineCPUActivationContractError(RuntimeError):
    """Raised when the activation contract or exact source binding drifts."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FullPipelineCPUActivationContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_pretty_json(path: Path, *, name: str) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        document = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                FullPipelineCPUActivationContractError(
                    f"non-finite JSON constant: {value}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FullPipelineCPUActivationContractError(
            f"invalid {name} JSON: {exc}"
        ) from exc
    if type(document) is not dict:
        raise FullPipelineCPUActivationContractError(f"{name} must be an object")
    canonical = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if raw != canonical:
        raise FullPipelineCPUActivationContractError(
            f"{name} is not canonical indented JSON"
        )
    return document, raw


def _compact_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_exact(value: object, expected: object, *, name: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise FullPipelineCPUActivationContractError(f"{name} changed")


def _require_snippets(path: Path, snippets: Sequence[str]) -> None:
    raw = path.read_text(encoding="utf-8")
    missing = [value for value in snippets if value not in raw]
    if missing:
        raise FullPipelineCPUActivationContractError(
            f"{path.name} missing frozen snippets: {missing}"
        )


def _require_ordered_snippets(path: Path, snippets: Sequence[str]) -> None:
    raw = path.read_text(encoding="utf-8")
    cursor = 0
    for value in snippets:
        observed = raw.find(value, cursor)
        if observed < 0:
            raise FullPipelineCPUActivationContractError(
                f"{path.name} missing ordered frozen snippet: {value}"
            )
        cursor = observed + len(value)


def _require_workflow_trigger_path_occurrences(
    path: Path,
    *,
    relative_path: str,
    expected_count: int,
) -> None:
    raw = path.read_text(encoding="utf-8")
    trigger_region, separator, _jobs = raw.partition("\njobs:")
    if not separator:
        raise FullPipelineCPUActivationContractError(
            f"{path.name} jobs boundary is absent"
        )
    needle = f'      - "{relative_path}"'
    observed_count = sum(line == needle for line in trigger_region.splitlines())
    if observed_count != expected_count:
        raise FullPipelineCPUActivationContractError(
            f"{path.name} trigger path count changed for {relative_path}: "
            f"observed {observed_count}, expected {expected_count}"
        )


def _require_non_negative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise FullPipelineCPUActivationContractError(
            f"{name} must be a non-negative exact integer"
        )
    return value


def _require_digest(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FullPipelineCPUActivationContractError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_relative_path(value: object, *, name: str) -> str:
    if type(value) is not str or not value or not value.isascii():
        raise FullPipelineCPUActivationContractError(f"{name} is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise FullPipelineCPUActivationContractError(f"{name} is not canonical")
    return value


def _validate_stdlib_closure(document: dict[str, Any]) -> None:
    _require_exact(
        frozenset(document),
        frozenset(
            {
                "cached_bytecode_file_count",
                "cached_bytecode_total_bytes",
                "file_backed_module_count",
                "file_backed_total_bytes",
                "module_count",
                "rows",
                "rows_sha256",
                "schema_id",
            }
        ),
        name="standard-library closure keys",
    )
    rows = document["rows"]
    if type(rows) is not list or not rows:
        raise FullPipelineCPUActivationContractError(
            "standard-library closure rows changed"
        )
    identities: list[str] = []
    file_count = 0
    total_bytes = 0
    cached_bytecode_file_count = 0
    cached_bytecode_total_bytes = 0
    for row in rows:
        if type(row) is not dict:
            raise FullPipelineCPUActivationContractError(
                "standard-library closure row is not an exact object"
            )
        module = row.get("module")
        origin = row.get("origin")
        if (
            type(module) is not str
            or not module
            or not module.isascii()
            or type(origin) is not str
        ):
            raise FullPipelineCPUActivationContractError(
                "standard-library closure module identity changed"
            )
        identities.append(module)
        if origin in {"built-in", "frozen"}:
            _require_exact(
                frozenset(row),
                frozenset({"module", "origin"}),
                name="built-in standard-library closure row keys",
            )
            continue
        if origin != "stdlib_file":
            raise FullPipelineCPUActivationContractError(
                "standard-library closure origin changed"
            )
        expected_row_keys = {"module", "origin", "path", "sha256", "size_bytes"}
        if "cached_bytecode" in row:
            expected_row_keys.add("cached_bytecode")
        _require_exact(
            frozenset(row),
            frozenset(expected_row_keys),
            name="file-backed standard-library closure row keys",
        )
        _require_relative_path(row["path"], name="standard-library closure path")
        _require_digest(row["sha256"], name="standard-library closure file digest")
        total_bytes += _require_non_negative_int(
            row["size_bytes"], name="standard-library closure file size"
        )
        file_count += 1
        cached = row.get("cached_bytecode")
        if str(row["path"]).endswith(".py") and type(cached) is not dict:
            raise FullPipelineCPUActivationContractError(
                "source-backed standard-library row lacks bytecode identity"
            )
        if cached is not None:
            if type(cached) is not dict:
                raise FullPipelineCPUActivationContractError(
                    "standard-library bytecode identity is not an exact object"
                )
            present = cached.get("present")
            cached_path = _require_relative_path(
                cached.get("path"), name="standard-library bytecode cache path"
            )
            if not cached_path.endswith(".pyc") or type(present) is not bool:
                raise FullPipelineCPUActivationContractError(
                    "standard-library bytecode cache identity changed"
                )
            expected_cached_keys = {"path", "present"}
            if present:
                expected_cached_keys.update({"sha256", "size_bytes"})
            _require_exact(
                frozenset(cached),
                frozenset(expected_cached_keys),
                name="standard-library bytecode cache row keys",
            )
            if present:
                _require_digest(
                    cached["sha256"], name="standard-library bytecode cache digest"
                )
                cached_size = _require_non_negative_int(
                    cached["size_bytes"],
                    name="standard-library bytecode cache size",
                )
                if cached_size == 0:
                    raise FullPipelineCPUActivationContractError(
                        "standard-library bytecode cache size must be positive"
                    )
                cached_bytecode_file_count += 1
                cached_bytecode_total_bytes += cached_size
    if identities != sorted(identities) or len(set(identities)) != len(identities):
        raise FullPipelineCPUActivationContractError(
            "standard-library closure rows are not canonical unique order"
        )
    _require_exact(document["module_count"], len(rows), name="module count")
    _require_exact(
        document["file_backed_module_count"],
        file_count,
        name="file-backed module count",
    )
    _require_exact(
        document["file_backed_total_bytes"],
        total_bytes,
        name="file-backed module byte total",
    )
    _require_exact(
        document["cached_bytecode_file_count"],
        cached_bytecode_file_count,
        name="cached bytecode file count",
    )
    _require_exact(
        document["cached_bytecode_total_bytes"],
        cached_bytecode_total_bytes,
        name="cached bytecode byte total",
    )


def _validate_dynamic_closure(document: dict[str, Any]) -> None:
    _require_exact(
        frozenset(document),
        frozenset(
            {
                "executable_file_count",
                "rows",
                "rows_sha256",
                "schema_id",
                "total_bytes",
                "virtual_executable_mappings",
            }
        ),
        name="executable-mapping closure keys",
    )
    rows = document["rows"]
    if type(rows) is not list or not rows:
        raise FullPipelineCPUActivationContractError(
            "executable-mapping closure rows changed"
        )
    virtual_mappings = document["virtual_executable_mappings"]
    if (
        type(virtual_mappings) is not list
        or any(
            type(value) is not str or value not in {"[vdso]", "[vsyscall]"}
            for value in virtual_mappings
        )
        or virtual_mappings != sorted(set(virtual_mappings))
    ):
        raise FullPipelineCPUActivationContractError(
            "virtual executable mapping closure changed"
        )
    identities: list[str] = []
    total_bytes = 0
    for row in rows:
        if type(row) is not dict:
            raise FullPipelineCPUActivationContractError(
                "executable-mapping closure row is not an exact object"
            )
        _require_exact(
            frozenset(row),
            frozenset({"path", "sha256", "size_bytes"}),
            name="executable-mapping closure row keys",
        )
        identity = row["path"]
        if (
            type(identity) is not str
            or not identity.isascii()
            or not identity.startswith(
                (
                    "qualified_site_packages/",
                    "sealed_memfd:",
                    "stdlib/",
                    "system:/",
                )
            )
            or ".." in PurePosixPath(identity.removeprefix("system:")).parts
        ):
            raise FullPipelineCPUActivationContractError(
                "executable-mapping closure identity changed"
            )
        identities.append(identity)
        _require_digest(row["sha256"], name="executable mapping digest")
        size = _require_non_negative_int(
            row["size_bytes"], name="executable mapping size"
        )
        if size == 0:
            raise FullPipelineCPUActivationContractError(
                "executable mapping size must be positive"
            )
        total_bytes += size
    if identities != sorted(identities) or len(set(identities)) != len(identities):
        raise FullPipelineCPUActivationContractError(
            "executable-mapping closure rows are not canonical unique order"
        )
    _require_exact(
        document["executable_file_count"],
        len(rows),
        name="executable file count",
    )
    _require_exact(
        document["total_bytes"], total_bytes, name="executable file byte total"
    )


def load_closure_manifest(
    path: Path, *, expected_schema_id: str
) -> tuple[dict[str, Any], bytes]:
    document, raw = _load_pretty_json(path, name="runtime closure manifest")
    if document.get("schema_id") != expected_schema_id:
        raise FullPipelineCPUActivationContractError(
            "runtime closure manifest schema changed"
        )
    rows = document.get("rows")
    if type(rows) is not list or not rows or any(type(row) is not dict for row in rows):
        raise FullPipelineCPUActivationContractError(
            "runtime closure manifest rows changed"
        )
    observed_rows_sha256 = hashlib.sha256(_compact_json_bytes(rows)).hexdigest()
    if document.get("rows_sha256") != observed_rows_sha256:
        raise FullPipelineCPUActivationContractError(
            "runtime closure row receipt changed"
        )
    if expected_schema_id == (
        "betelgeuze.engine_v2_python_stdlib_import_closure/1.0.0"
    ):
        _validate_stdlib_closure(document)
    elif expected_schema_id == (
        "betelgeuze.engine_v2_executable_mapping_closure/1.0.0"
    ):
        _validate_dynamic_closure(document)
    else:
        raise FullPipelineCPUActivationContractError(
            "unsupported runtime closure manifest schema"
        )
    return document, raw


def _require_exact_native_initialization_delta(
    preinit: dict[str, Any], dynamic: dict[str, Any]
) -> None:
    preinit_rows = {str(row["path"]): row for row in preinit["rows"]}
    dynamic_rows = {str(row["path"]): row for row in dynamic["rows"]}
    native_identity = "sealed_memfd:engine-v2-native-extension-v1"
    if (
        native_identity in preinit_rows
        or set(dynamic_rows) != set(preinit_rows) | {native_identity}
        or preinit["virtual_executable_mappings"]
        != dynamic["virtual_executable_mappings"]
    ):
        raise FullPipelineCPUActivationContractError(
            "native initialization executable mapping delta changed"
        )
    for path, row in preinit_rows.items():
        _require_exact(
            dynamic_rows[path], row, name="pre-initialized dependency mapping"
        )
    _require_exact(
        dynamic_rows[native_identity],
        {
            "path": native_identity,
            "sha256": (
                "ff7b5e6ba7c0e250cf739292d34c562d0bd142d5f7f6c842c5c191d42b2504e1"
            ),
            "size_bytes": 2_599_704,
        },
        name="sealed native initialization mapping",
    )


def _git_bytes(repository_root: Path, arguments: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FullPipelineCPUActivationContractError(
            "frozen merged-main Git object is unavailable"
        ) from exc
    return completed.stdout


def _verify_foundation(repository_root: Path) -> None:
    commit_type = _git_bytes(repository_root, ("cat-file", "-t", FOUNDATION_COMMIT_OID))
    if commit_type != b"commit\n":
        raise FullPipelineCPUActivationContractError(
            "merged-main foundation object is not a commit"
        )
    commit_raw = _git_bytes(
        repository_root, ("cat-file", "commit", FOUNDATION_COMMIT_OID)
    )
    if hashlib.sha256(commit_raw).hexdigest() != FOUNDATION_COMMIT_SHA256:
        raise FullPipelineCPUActivationContractError(
            "merged-main foundation commit bytes changed"
        )
    tree_oid = (
        _git_bytes(
            repository_root,
            ("show", "-s", "--format=%T", FOUNDATION_COMMIT_OID),
        )
        .decode("ascii")
        .strip()
    )
    if tree_oid != FOUNDATION_TREE_OID:
        raise FullPipelineCPUActivationContractError(
            "merged-main foundation tree OID changed"
        )
    tree_manifest = _git_bytes(
        repository_root,
        ("ls-tree", "-r", "--full-tree", "-z", FOUNDATION_COMMIT_OID),
    )
    if hashlib.sha256(tree_manifest).hexdigest() != FOUNDATION_TREE_SHA256:
        raise FullPipelineCPUActivationContractError(
            "merged-main foundation tree manifest changed"
        )


def verify(
    *,
    repository_root: Path = REPOSITORY_ROOT,
    activation_path: Path | None = None,
) -> dict[str, object]:
    repository_root = repository_root.resolve(strict=True)
    activation_path = activation_path or (
        repository_root
        / "config/engine_v2_full_pipeline_cpu_performance_v1_activation.json"
    )
    document, raw = _load_pretty_json(activation_path, name="activation contract")
    activation_sha256 = hashlib.sha256(raw).hexdigest()
    if activation_sha256 != ACTIVATION_SHA256:
        raise FullPipelineCPUActivationContractError(
            "activation contract SHA-256 changed"
        )
    _require_exact(
        frozenset(document),
        frozenset(
            {
                "activation_id",
                "authority",
                "closure_manifests",
                "preflight",
                "profile_id",
                "profile_sha256",
                "restrictions",
                "runner",
                "runtime_binding",
                "schema_id",
                "source_bindings",
                "source_foundation",
                "status",
            }
        ),
        name="activation keys",
    )
    _require_exact(document["schema_id"], ACTIVATION_SCHEMA_ID, name="schema_id")
    _require_exact(document["activation_id"], ACTIVATION_ID, name="activation_id")
    _require_exact(document["profile_id"], PROFILE_ID, name="profile_id")
    _require_exact(document["profile_sha256"], PROFILE_SHA256, name="profile_sha256")
    _require_exact(
        document["status"],
        "frozen_non_consuming_exact_main_preflight_execution_not_activated",
        name="status",
    )
    authority = document["authority"]
    if (
        type(authority) is not dict
        or frozenset(authority) != AUTHORITY_KEYS
        or any(value is not False for value in authority.values())
    ):
        raise FullPipelineCPUActivationContractError(
            "activation authority is not all false"
        )
    restrictions = document["restrictions"]
    if (
        type(restrictions) is not dict
        or not restrictions
        or any(value is not False for value in restrictions.values())
    ):
        raise FullPipelineCPUActivationContractError(
            "activation restrictions granted authority"
        )
    _require_exact(document["source_bindings"], SOURCE_BINDINGS, name="source bindings")
    _require_exact(
        document["source_foundation"],
        {
            "merged_main_commit_oid": FOUNDATION_COMMIT_OID,
            "merged_main_commit_object_encoding": "git_cat_file_commit_raw_v1",
            "merged_main_commit_sha256": FOUNDATION_COMMIT_SHA256,
            "merged_main_tree_manifest_encoding": "git_ls_tree_r_full_tree_z_v1",
            "merged_main_tree_oid": FOUNDATION_TREE_OID,
            "merged_main_tree_sha256": FOUNDATION_TREE_SHA256,
        },
        name="source foundation",
    )
    _verify_foundation(repository_root)

    actual_paths = {
        key: repository_root / path.relative_to(REPOSITORY_ROOT)
        for key, path in SOURCE_PATHS.items()
    }
    for key, expected in SOURCE_BINDINGS.items():
        if key in {"merged_main_commit_sha256", "merged_main_tree_sha256"}:
            continue
        if _sha256(actual_paths[key]) != expected:
            raise FullPipelineCPUActivationContractError(
                f"activation source binding changed: {key}"
            )

    stdlib_path = actual_paths["stdlib_import_closure_manifest_sha256"]
    preinit_path = actual_paths["preinit_executable_closure_manifest_sha256"]
    dynamic_path = actual_paths["dynamic_library_closure_manifest_sha256"]
    stdlib, stdlib_raw = load_closure_manifest(
        stdlib_path,
        expected_schema_id="betelgeuze.engine_v2_python_stdlib_import_closure/1.0.0",
    )
    dynamic, dynamic_raw = load_closure_manifest(
        dynamic_path,
        expected_schema_id="betelgeuze.engine_v2_executable_mapping_closure/1.0.0",
    )
    preinit, preinit_raw = load_closure_manifest(
        preinit_path,
        expected_schema_id="betelgeuze.engine_v2_executable_mapping_closure/1.0.0",
    )
    _require_exact_native_initialization_delta(preinit, dynamic)
    _require_exact(
        document["closure_manifests"],
        {
            "dynamic_library_closure": {
                "executable_file_count": dynamic["executable_file_count"],
                "manifest_sha256": hashlib.sha256(dynamic_raw).hexdigest(),
                "path": "config/engine_v2_full_pipeline_cpu_performance_v1_dynamic_library_closure.json",
                "total_bytes": dynamic["total_bytes"],
                "virtual_executable_mappings": dynamic["virtual_executable_mappings"],
            },
            "preinit_executable_closure": {
                "executable_file_count": preinit["executable_file_count"],
                "manifest_sha256": hashlib.sha256(preinit_raw).hexdigest(),
                "path": "config/engine_v2_full_pipeline_cpu_performance_v1_preinit_executable_closure.json",
                "total_bytes": preinit["total_bytes"],
                "virtual_executable_mappings": preinit["virtual_executable_mappings"],
            },
            "stdlib_import_closure": {
                "cached_bytecode_file_count": stdlib["cached_bytecode_file_count"],
                "cached_bytecode_total_bytes": stdlib["cached_bytecode_total_bytes"],
                "file_backed_module_count": stdlib["file_backed_module_count"],
                "file_backed_total_bytes": stdlib["file_backed_total_bytes"],
                "manifest_sha256": hashlib.sha256(stdlib_raw).hexdigest(),
                "module_count": stdlib["module_count"],
                "path": "config/engine_v2_full_pipeline_cpu_performance_v1_stdlib_closure.json",
            },
        },
        name="closure manifest projection",
    )
    _require_exact(
        document["runtime_binding"],
        {
            "abi": "cp310-cp310",
            "artifact_contract_sha256": (
                "195abc14487ccec4d0f8065fa0e642337ce42691cebee4f47106b94bd2d0ebe8"
            ),
            "artifact_id": 9213296947,
            "artifact_run_attempt": 1,
            "artifact_run_id": 31785070195,
            "artifact_workflow_head_sha": ("3330faa43c7fc8640d89babd84ac444c5959157c"),
            "native_extension_sha256": (
                "ff7b5e6ba7c0e250cf739292d34c562d0bd142d5f7f6c842c5c191d42b2504e1"
            ),
            "python_executable_sha256": (
                "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86"
            ),
            "python_shared_library_sha256": (
                "1ece943a1641101b1c678b553a7a0fbb6683ff0ad76f7ebce9f8844354e3f153"
            ),
            "runtime_scope_manifest_sha256": (
                "72b90f500af43c921ce0b8f7d6774c5e99a7e4f3fe366478b3fc33b524b4b404"
            ),
        },
        name="runtime binding",
    )
    runner = document["runner"]
    _require_exact(
        runner,
        {
            "activation_contract_allows_live_execution": False,
            "activation_contract_present": True,
            "exactly_once_local_synthetic_attempt_required": True,
            "github_actions_live_execution_allowed": False,
            "live_synthetic_local_execution_implemented": False,
            "profile_change_after_activation_allowed": False,
            "qualification_attempt_consumed": False,
            "reservation_created": False,
            "runner_remains_fail_closed": True,
        },
        name="runner boundary",
    )
    preflight = document["preflight"]
    _require_exact(
        preflight,
        {
            "activation_module_sha256": _sha256(
                repository_root
                / "betelgeuze_engine_v2/docking/full_pipeline_cpu_performance_v1_activation.py"
            ),
            "bootstrap_flags": ["-I", "-S", "-B"],
            "caller_science_input_allowed": False,
            "exact_dynamic_loader_path": (
                "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"
            ),
            "exact_loader_environment": {
                "CUDA_VISIBLE_DEVICES": "",
                "HIP_VISIBLE_DEVICES": "",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "ROCR_VISIBLE_DEVICES": "",
            },
            "exact_loader_kernel_process_identity": {
                "proc_cmdline_exact": True,
                "proc_exe_exact": True,
                "stage0_argument_vector_bound": True,
                "stage0_source_sha256": (
                    "c8075347e3df061636efd00421497341f9bde0d8d6befbc592cd39ea73a44a2f"
                ),
            },
            "immutable_bootstrap_snapshot": {
                "descriptor_cloexec": False,
                "descriptor_mode": "0400",
                "descriptor_name": "engine-v2-preflight-bootstrap-v1",
                "descriptor_seals": [
                    "F_SEAL_SEAL",
                    "F_SEAL_SHRINK",
                    "F_SEAL_GROW",
                    "F_SEAL_WRITE",
                ],
                "exact_source_sha256_required": True,
                "launched_from_snapshot_required": True,
                "zero_link_count_required": True,
            },
            "exact_loader_inhibit_cache": True,
            "exact_loader_library_path": (
                "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
            ),
            "exact_loader_preload_paths": [
                "/usr/lib/x86_64-linux-gnu/libstdc++.so.6.0.30",
                "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1",
                "/usr/lib/x86_64-linux-gnu/libpthread.so.0",
                "/usr/lib/x86_64-linux-gnu/libm.so.6",
                "/usr/lib/x86_64-linux-gnu/libdl.so.2",
                "/usr/lib/x86_64-linux-gnu/libc.so.6",
            ],
            "exact_native_extension_import_required": True,
            "exact_preinit_closure_required": True,
            "github_actions_preflight_allowed": False,
            "host_preflight_required": True,
            "molecular_input_allowed": False,
            "performance_measurement_allowed": False,
            "performance_sidecar_sha256": _sha256(
                repository_root / "betelgeuze_engine_v2/docking/performance_sidecar.py"
            ),
            "preflight_tool_sha256": _sha256(
                repository_root
                / "tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py"
            ),
            "native_initialization_delta_exact": True,
            "qualification_state_write_allowed": False,
            "reservation_allowed": False,
        },
        name="preflight boundary",
    )

    _require_snippets(
        repository_root / "tools/run_engine_v2_full_pipeline_cpu_performance_v1.py",
        (
            "run_live_full_pipeline_cpu_performance_v1",
            "inactive execution does not accept runtime paths",
            "GitHub Actions cannot execute full-pipeline CPU qualification",
        ),
    )
    _require_snippets(
        repository_root
        / "tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
        (
            "GitHub Actions cannot run the exact-runtime activation preflight",
            "ActivationPreflightEvidenceV1",
            "_authenticate_bound_sources",
            "bound source changed before import",
            "_exact_json_equal",
            "activation contract exact projection changed",
            "_require_native_extension",
            "_require_exact_loader_bootstrap",
            "_EXACT_LOADER_STAGE0_TEMPLATE",
            "_render_exact_loader_stage0",
            "_read_exact_proc_cmdline",
            "kernel process identity does not prove the exact loader invocation",
            "_validate_bootstrap_snapshot",
            "exact_loader_process_identity_validated",
            "immutable_bootstrap_snapshot_validated",
            "--inhibit-cache",
            "--glibc-hwcaps-mask",
            "--preload",
            "preinit_executable_closure_manifest_sha256",
            "require_exact_native_initialization_delta",
            "ExtensionFileLoader",
            "/proc/self/fd/",
            "_require_native_descriptor_stable",
            "memfd_create",
            "F_ADD_SEALS",
            "F_SEAL_WRITE",
            "_require_native_snapshot_sealed",
            "_populate_native_package",
            "_remove_loaded_native_extension",
            "required_executable_file_identity",
            "native_fixed64_prepare_repository_synthetic_d0_session_v1",
            "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
            "derive_host_preflight_evidence_v3",
        ),
    )
    _require_snippets(
        repository_root
        / "betelgeuze_engine_v2/docking/full_pipeline_cpu_performance_v1_activation.py",
        (
            '"performance_measurement_performed": False',
            '"qualification_consumed": False',
            '"reservation_created": False',
            "line.split(maxsplit=5)",
            "deleted executable file mapping is forbidden",
            "unexpected anonymous executable mapping",
            "expected_mapping_identity=mapping_identity",
            "SEALED_NATIVE_EXTENSION_MAP_PATH",
            "sealed_executable_descriptor",
            "require_exact_native_initialization_delta",
        ),
    )
    _require_snippets(
        repository_root
        / "tests/unit/test_verify_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
        (
            "test_full_pipeline_cpu_activation_contract_verifies",
            "test_full_pipeline_cpu_activation_rejects_authority_drift",
        ),
    )
    _require_snippets(
        repository_root
        / "tests/unit/test_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
        (
            "test_stdlib_import_closure_is_rederivable",
            "test_dynamic_library_closure_is_rederivable",
            "test_loader_stage0_argument_vector_binds_every_loader_option",
            "test_loader_bootstrap_requires_kernel_identity_and_immutable_snapshot",
            "test_loader_bootstrap_rejects_direct_path_invocation",
            "test_loader_bootstrap_rejects_github_actions_before_source_validation",
            "test_native_extension_failure_cleanup_removes_public_and_submodule",
            "test_native_initialization_delta_rejects_a_late_dependency",
        ),
    )
    _require_snippets(
        repository_root
        / "docs/engine_v2_full_pipeline_cpu_performance_v1_activation.md",
        (
            "exact merged-main foundation",
            "non-consuming preflight",
            "does not activate the exactly-once runner",
            "exact typed",
            "126 imported standard-library module identities",
            "85 file-backed",
            "79 declared bytecode-cache files",
            "21 file-backed executable mappings",
            "20 pre-initialization executable mappings",
            "exact glibc dynamic loader",
            "kernel-maintained `/proc/self/exe`",
            "authenticated immutable bootstrap snapshot",
            "Direct pathname execution",
            "before native initialization",
            "descriptor-bound native",
            "sealed memfd",
            "public package",
        ),
    )
    workflow_tokens = (
        "config/engine_v2_full_pipeline_cpu_performance_v1_activation.json",
        "config/engine_v2_full_pipeline_cpu_performance_v1_stdlib_closure.json",
        "config/engine_v2_full_pipeline_cpu_performance_v1_dynamic_library_closure.json",
        "config/engine_v2_full_pipeline_cpu_performance_v1_preinit_executable_closure.json",
        "betelgeuze_engine_v2/docking/full_pipeline_cpu_performance_v1_activation.py",
        "tools/verify_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
        "tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
        "tests/unit/test_verify_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
        "tests/unit/test_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
        "docs/engine_v2_full_pipeline_cpu_performance_v1_activation.md",
        "betelgeuze_engine_v2/docking/performance_host_preflight_v3.py",
        "betelgeuze_engine_v2/docking/performance_sidecar.py",
    )
    for relative in (
        ".github/workflows/ci-engine-v2-main.yml",
        ".github/workflows/ci-engine-v2-release-candidate.yml",
        ".github/workflows/ci-native-compute-abi.yml",
    ):
        workflow_path = repository_root / relative
        _require_snippets(workflow_path, workflow_tokens)
        expected_count = 2 if relative.endswith("ci-native-compute-abi.yml") else 1
        for bound_trigger in (
            "betelgeuze_engine_v2/docking/performance_host_preflight_v3.py",
            "betelgeuze_engine_v2/docking/performance_sidecar.py",
        ):
            _require_workflow_trigger_path_occurrences(
                workflow_path,
                relative_path=bound_trigger,
                expected_count=expected_count,
            )
    preflight_tool = (
        repository_root
        / "tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py"
    )
    _require_ordered_snippets(
        preflight_tool,
        (
            "def derive_preflight(",
            "observed_preinit = activation.derive_dynamic_library_closure(",
            'name="pre-initialization executable-file mapping closure"',
            "_require_native_extension(",
            "require_exact_native_initialization_delta(",
        ),
    )
    return {
        "schema_id": ACTIVATION_SCHEMA_ID,
        "activation_id": ACTIVATION_ID,
        "activation_sha256": activation_sha256,
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "foundation_commit_oid": FOUNDATION_COMMIT_OID,
        "foundation_tree_oid": FOUNDATION_TREE_OID,
        "stdlib_import_closure_manifest_sha256": hashlib.sha256(stdlib_raw).hexdigest(),
        "preinit_executable_closure_manifest_sha256": hashlib.sha256(
            preinit_raw
        ).hexdigest(),
        "dynamic_library_closure_manifest_sha256": hashlib.sha256(
            dynamic_raw
        ).hexdigest(),
        "all_authority_false": True,
        "execution_activated": False,
        "preflight_implemented": True,
        "performance_measurement_performed": False,
        "qualification_consumed": False,
        "reservation_created": False,
        "status": "verified_non_consuming_activation_execution_not_activated",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--activation", type=Path, default=DEFAULT_ACTIVATION)
    arguments = parser.parse_args()
    print(
        json.dumps(
            verify(activation_path=arguments.activation),
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
