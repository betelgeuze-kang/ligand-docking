#!/usr/bin/env python3
"""Verify native fixed64 CPU v7 activation without consuming it."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import NoReturn

if __package__:
    from .verify_engine_v2_native_fixed64_cpu_profile_v6 import (
        require_archived_profile_v6,
    )
else:
    from verify_engine_v2_native_fixed64_cpu_profile_v6 import (
        require_archived_profile_v6,
    )


SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_cpu_profile/7.0.0"
PROFILE_ID = "engine_v2_native_fixed64_cpu_synthetic_v7"
PROFILE_SHA256 = "50c3e609a23e3bf0641a900f71dc360dcadc1a52c3bde66cdfa74b8c1affcd5d"
BUILD_CONFIGURATION_SHA256 = (
    "6e39e4e07bcb2f9324f242adcf3f48428191b2a91418d34520c6acc1cf046068"
)
SOURCE_MANIFEST_SHA256 = (
    "ecb009ac228652c6c6cbdefcdd70828ce3d9aeea5a5e31d0fff0246d4d5f932e"
)
SOURCE_COUNT = 196
PROFILE_RELATIVE_PATH = Path("config/engine_v2_native_fixed64_cpu_profile_v7.json")
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_fixed64_cpu_profile_v7_sources.json"
)
V6_PROFILE_RELATIVE_PATH = Path("config/engine_v2_native_fixed64_cpu_profile_v6.json")
V6_ARCHIVE_RELATIVE_PATH = Path(
    "config/engine_v2_native_fixed64_cpu_profile_v6_archive.json"
)
QUALIFICATION_SOURCE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/src/qualification.rs"
)
RUNNER_SOURCE_RELATIVE_PATH = Path("rust/betelgeuze-runtime/src/qualification_v7.rs")
BINARY_SOURCE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-qualify-v7.rs"
)
LANE_METRICS_SOURCE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/src/fixed64_lane_metrics.rs"
)
CARGO_MANIFEST_RELATIVE_PATH = Path("rust/betelgeuze-runtime/Cargo.toml")
BUILD_SOURCE_RELATIVE_PATH = Path("rust/betelgeuze-runtime/build.rs")
SYS_BUILD_SOURCE_RELATIVE_PATH = Path("rust/betelgeuze-sys/build.rs")
RUSTC_WRAPPER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_fixed64_cpu_v7_rustc_wrapper.py"
)
CARGO_LOCK_RELATIVE_PATH = Path("rust/Cargo.lock")
PACKAGED_PROFILE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v7.json"
)
PACKAGED_V6_ARCHIVE_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v6_archive.json"
)
PACKAGED_SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/assets/engine_v2_native_fixed64_cpu_profile_v7_sources.json"
)
PACKAGED_CARGO_LOCK_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/assets/workspace-Cargo.lock"
)
PACKAGED_CARGO_MANIFEST_RELATIVE_PATH = Path(
    "rust/betelgeuze-runtime/assets/original-Cargo.toml"
)

FALSE_AUTHORITY_KEYS = {
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "molecular_execution_authorized",
    "product_performance_claim_authorized",
    "public_benchmark_authorized",
    "qualification_authority",
    "reservation_authorized",
    "scientific_claim_authorized",
    "stage0_admission_authorized",
}
FALSE_RESTRICTION_KEYS = {
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
}
RUST_SOURCE_ROOTS = (
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
NATIVE_SOURCE_ROOTS = (
    Path("include/betelgeuze"),
    Path("native/src"),
    Path("rust/betelgeuze-sys/abi"),
    Path("rust/betelgeuze-sys/vendor/include/betelgeuze"),
    Path("rust/betelgeuze-sys/vendor/native/src"),
)
NATIVE_SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".h", ".hip", ".hpp"}
FORBIDDEN_CONFIGURATION_PATHS = (
    Path(".cargo/config"),
    Path(".cargo/config.toml"),
    Path("rust/.cargo/config"),
    Path("rust/.cargo/config.toml"),
    Path("rust-toolchain"),
    Path("rust-toolchain.toml"),
    Path("rust/rust-toolchain"),
    Path("rust/rust-toolchain.toml"),
)
EXPECTED_CARGO_TARGETS = {
    "rust/betelgeuze-docking-search/src/lib.rs",
    "rust/betelgeuze-docking-search/tests/fixed64_allocation.rs",
    "rust/betelgeuze-docking-search/tests/fixed64_geometric_admission.rs",
    "rust/betelgeuze-docking-search/tests/fixed64_placement.rs",
    "rust/betelgeuze-docking-search/tests/fixed64_producer.rs",
    "rust/betelgeuze-docking-search/tests/fixed64_scorer_v1.rs",
    "rust/betelgeuze-docking-search/tests/search_contract.rs",
    "rust/betelgeuze-docking-search/tests/short_range.rs",
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-probe-v5.rs",
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-qualify-v6.rs",
    "rust/betelgeuze-runtime/src/bin/betelgeuze-fixed64-cpu-qualify-v7.rs",
    "rust/betelgeuze-runtime/src/lib.rs",
    "rust/betelgeuze-runtime/build.rs",
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
}
EXPECTED_BUILD_CONFIGURATION = {
    "cargo_binary_sha256": "9548937d530bf439ff1ba47a3b2bd26eeb9c3aff1961c20c01798613de922578",
    "cargo_build_script_panic_env": "unwind",
    "cargo_build_script_profile_env": "release",
    "cargo_codegen_units": 1,
    "cargo_commit_hash": "083ac5135f967fd9dc906ab057a2315861c7a80d",
    "cargo_debug": False,
    "cargo_debug_assertions": False,
    "cargo_incremental": False,
    "cargo_lto": "fat",
    "cargo_opt_level": 3,
    "cargo_overflow_checks": True,
    "cargo_panic": "abort",
    "cargo_profile": "qualification-v7",
    "cargo_release": "1.93.0",
    "cargo_strip": "none",
    "cargo_target_directory": "rust/target/qualification-v7",
    "cpp_compiler_canonical_path": "/usr/bin/x86_64-linux-gnu-g++-11",
    "cpp_compiler_sha256": "2360901d864cf10bfd6296e261cb2c14053552a80377761ab07146ec9ec9a2c0",
    "cpp_dumpfullversion": "11.4.0",
    "cpp_dumpmachine": "x86_64-linux-gnu",
    "cpp_explicit_flags": [
        "-std=c++17",
        "-O3",
        "-m64",
        "-fPIC",
        "-ffunction-sections",
        "-fdata-sections",
        "-fvisibility=hidden",
        "-ffp-contract=off",
        "-fno-fast-math",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
    ],
    "environment_flag_overrides_allowed": False,
    "hip_feature_allowed": False,
    "host_triple": "x86_64-unknown-linux-gnu",
    "qualification_build_opt_in": "BETELGEUZE_V7_QUALIFICATION_BUILD=1",
    "rust_target_features": ["fxsr", "sse", "sse2"],
    "rustc_binary_effective_codegen_flags": [
        "opt-level=3",
        "panic=abort",
        "lto=fat",
        "codegen-units=1",
        "overflow-checks=on",
    ],
    "rustc_binary_sha256": "d32249a7c3bfcfc67b471460386e46323accae7125e344567a12d5664d99bb57",
    "rustc_commit_hash": "254b59607d4417e9dffbc307138ae5c86280fe4c",
    "rustc_library_effective_codegen_flags": [
        "opt-level=3",
        "panic=abort",
        "linker-plugin-lto",
        "codegen-units=1",
        "overflow-checks=on",
    ],
    "rustc_llvm_version": "21.1.8",
    "rustc_release": "1.93.0",
    "rustc_wrapper_cfg": "betelgeuze_v7_effective_rust_flags_verified",
    "rustc_wrapper_interpreter_canonical_path": "/usr/bin/python3.10",
    "rustc_wrapper_interpreter_sha256": "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86",
    "rustc_wrapper_relative_path": "tools/verify_engine_v2_native_fixed64_cpu_v7_rustc_wrapper.py",
    "rustc_wrapper_required": True,
    "rustc_wrapper_sha256": "bb95e65d3de3ba08cda1c022690895f8d9ec986eb3a59ecb6ba4127a2982f088",
    "schema_id": "betelgeuze.engine_v2_native_fixed64_cpu_build_configuration/1.0.0",
    "target_triple": "x86_64-unknown-linux-gnu",
}


class NativeFixed64CPUProfileV7Error(ValueError):
    """The frozen native fixed64 CPU v7 activation failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeFixed64CPUProfileV7Error(message)


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


def _compact_canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _load_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFixed64CPUProfileV7Error(
            f"{label} is not canonical ASCII JSON"
        ) from exc
    if type(value) is not dict or raw != _canonical_bytes(value):
        _fail(f"{label} canonical serialization changed")
    return value


def _exact_keys(value: object, expected: set[str], *, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != expected:
        _fail(f"{label} field set changed")
    return value


def _require_digest(value: object, *, label: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(f"{label} is not a lowercase SHA-256")
    return value


def require_profile_document_v7(
    profile_raw: bytes,
    v6_profile_raw: bytes,
    v6_archive_raw: bytes,
    source_manifest_raw: bytes,
    source_bytes: dict[str, bytes],
) -> dict[str, object]:
    profile = _load_canonical_object(profile_raw, label="v7 profile")
    v6 = _load_canonical_object(v6_profile_raw, label="v6 profile")
    require_archived_profile_v6(v6_profile_raw, v6_archive_raw)
    if hashlib.sha256(profile_raw).hexdigest() != PROFILE_SHA256:
        _fail("v7 profile bytes changed from the frozen activation identity")
    if hashlib.sha256(source_manifest_raw).hexdigest() != SOURCE_MANIFEST_SHA256:
        _fail("v7 transitive source manifest bytes changed")
    if (
        profile.get("schema_id") != SCHEMA_ID
        or profile.get("profile_id") != PROFILE_ID
        or profile.get("status")
        != "native_lane_metrics_activation_frozen_execution_not_consumed"
    ):
        _fail("v7 profile identity or execution state changed")
    expected_top_keys = {
        "authority",
        "backends",
        "build_configuration",
        "change_control",
        "fixtures",
        "gates",
        "host_preflight",
        "measurement_core",
        "numeric_parity",
        "performance",
        "profile_id",
        "restrictions",
        "runner",
        "sampling",
        "schema_id",
        "source_bindings",
        "status",
    }
    _exact_keys(profile, expected_top_keys, label="v7 profile")
    authority = _exact_keys(
        profile["authority"], FALSE_AUTHORITY_KEYS, label="v7 authority"
    )
    restrictions = _exact_keys(
        profile["restrictions"],
        FALSE_RESTRICTION_KEYS,
        label="v7 restrictions",
    )
    if any(value is not False for value in authority.values()):
        _fail("v7 authority is not entirely false")
    if any(value is not False for value in restrictions.values()):
        _fail("v7 restrictions are not entirely false")
    build_configuration = _exact_keys(
        profile["build_configuration"],
        set(EXPECTED_BUILD_CONFIGURATION),
        label="v7 build configuration",
    )
    if (
        build_configuration != EXPECTED_BUILD_CONFIGURATION
        or hashlib.sha256(_compact_canonical_bytes(build_configuration)).hexdigest()
        != BUILD_CONFIGURATION_SHA256
    ):
        _fail("v7 frozen build configuration changed")

    for key in (
        "backends",
        "fixtures",
        "numeric_parity",
        "performance",
        "sampling",
    ):
        if profile[key] != v6[key]:
            _fail(f"v7 changed the frozen v6 scientific {key} contract")

    expected_gates = dict(v6["gates"])
    expected_gates.update(
        {
            "lane_metrics_authority_false_required": True,
            "lane_metrics_candidate_denominator_exact": 64,
            "lane_metrics_decision_sha256_exact_between_cpu_backends_required": True,
            "lane_metrics_full_receipts_recorded_required": True,
            "lane_metrics_lane_count_exact": 10,
            "lane_metrics_observation_count_exact": 64,
            "lane_metrics_rank_mutation_forbidden": True,
            "lane_metrics_receipt_rederivable_required": True,
            "lane_metrics_result_dependent_allocation_forbidden": True,
            "oracle_rmsd_definition": "symmetry_aware_direct_heavy_atom_no_alignment",
            "oracle_rmsd_threshold_angstrom_exact": 2.0,
            "symmetry_permutation_limit_exact": 1024,
            "typed_failures_preserved_in_lane_metrics_required": True,
        }
    )
    if profile["gates"] != expected_gates:
        _fail("v7 lane-metrics scientific gates changed")

    v6_measurement_core = v6["measurement_core"]
    if type(v6_measurement_core) is not dict:
        _fail("v6 measurement core is not an object")
    expected_core = dict(v6_measurement_core)
    expected_core.update(
        {
            "conformer_orientation_pairs": [
                "24:36",
                "25:37",
                "26:38",
                "27:39",
                "28:40",
                "29:41",
                "30:42",
                "31:43",
            ],
            "lane_metrics_downstream_only": True,
            "lane_metrics_observation_schema_id": "betelgeuze.engine_v2_native_fixed64_lane_metric_observation/1.0.0",
            "lane_metrics_reference_materialized": True,
            "lane_metrics_reference_receipt_and_topology_bound": True,
            "lane_metrics_reference_schema_id": "betelgeuze.engine_v2_native_fixed64_lane_metrics_reference/1.0.0",
            "lane_metrics_reports_exact_unique_pose_orientation_penetration_validity_oracle_entropy": True,
            "lane_metrics_schema_id": "betelgeuze.engine_v2_native_fixed64_lane_metrics/1.0.0",
            "lane_metrics_symmetry_mapping": "reference_position_to_candidate_position",
            "lane_metrics_symmetry_permutations_canonical_unique_identity_required": True,
            "native_binary": "betelgeuze-fixed64-cpu-qualify-v7",
        }
    )
    if profile["measurement_core"] != expected_core:
        _fail("v7 changed the frozen v6 graph beyond downstream lane metrics")

    if profile["change_control"] != {
        "candidate_graph_changed": False,
        "evidence_contract_changed": True,
        "fixture_payloads_changed": False,
        "metric_contract_changed": True,
        "numeric_contract_changed": False,
        "predecessor_execution_consumed": False,
        "predecessor_main_commit_oid": "12b220e096665ec5664e729d3d60baf577578c56",
        "predecessor_profile_id": "engine_v2_native_fixed64_cpu_synthetic_v6",
        "predecessor_profile_sha256": "fd83f1f7f7c92bc0fc9ac6581cababb23d3ba5787412174a55b659f97fcc2928",
        "successor_change_reason": "add_rederivable_fixed64_lane_metrics_and_oracle_selection_receipts",
    }:
        _fail("v7 change-control declaration changed")
    if profile["host_preflight"] != {
        "boost_disabled_required": True,
        "boost_state_path": "/sys/devices/system/cpu/cpufreq/boost",
        "cpu_model_exact": "AMD Ryzen 9 5900X 12-Core Processor",
        "linux_only": True,
        "main_branch_clean_checkout_required": True,
        "measurement_cpu_ordinal": 2,
        "process_task_count_exact": 1,
    }:
        _fail("v7 host preflight contract changed")
    if profile["runner"] != {
        "account_scoped_exactly_once": True,
        "artifact_and_terminal_persisted_before_return": True,
        "attempt_created_before_host_preflight": True,
        "build_commit_bound": True,
        "build_source_root_bound": True,
        "caller_supplied_probe_allowed": False,
        "compiled_activation_profile_verified_at_build": True,
        "compiled_transitive_sources_verified_at_build": True,
        "effective_rustc_flags_wrapper_verified_at_build": True,
        "frozen_build_configuration_required": True,
        "live_execution_implemented": True,
        "non_authoritative_package_build_activation_rejected": True,
        "normal_and_ci_build_activation_rejected": True,
        "output_path_utf8_required": True,
        "output_policy": "owner_only_absent_only_single_artifact_plus_terminal",
        "post_measurement_host_revalidation_required": True,
        "qualification_build_opt_in_required": True,
        "state_policy": "login_account_home_nofollow_o_excl",
        "test_only_profile_execution_allowed": False,
    }:
        _fail("v7 exactly-once runner contract changed")

    bindings = _exact_keys(
        profile["source_bindings"],
        {
            "cargo_lock_sha256",
            "cargo_manifest_sha256",
            "lane_metrics_source_sha256",
            "native_binary_source_sha256",
            "native_qualification_source_sha256",
            "native_runner_source_sha256",
            "predecessor_archive_sha256",
            "transitive_source_manifest_sha256",
        },
        label="v7 source bindings",
    )
    expected_bindings = {
        "cargo_lock_sha256": hashlib.sha256(
            source_bytes[CARGO_LOCK_RELATIVE_PATH.as_posix()]
        ).hexdigest(),
        "cargo_manifest_sha256": hashlib.sha256(
            source_bytes[CARGO_MANIFEST_RELATIVE_PATH.as_posix()]
        ).hexdigest(),
        "lane_metrics_source_sha256": hashlib.sha256(
            source_bytes[LANE_METRICS_SOURCE_RELATIVE_PATH.as_posix()]
        ).hexdigest(),
        "native_binary_source_sha256": hashlib.sha256(
            source_bytes[BINARY_SOURCE_RELATIVE_PATH.as_posix()]
        ).hexdigest(),
        "native_qualification_source_sha256": hashlib.sha256(
            source_bytes[QUALIFICATION_SOURCE_RELATIVE_PATH.as_posix()]
        ).hexdigest(),
        "native_runner_source_sha256": hashlib.sha256(
            source_bytes[RUNNER_SOURCE_RELATIVE_PATH.as_posix()]
        ).hexdigest(),
        "predecessor_archive_sha256": hashlib.sha256(v6_archive_raw).hexdigest(),
        "transitive_source_manifest_sha256": hashlib.sha256(
            source_manifest_raw
        ).hexdigest(),
    }
    if bindings != expected_bindings:
        _fail("v7 profile source bindings do not rederive from exact inputs")
    for key, value in bindings.items():
        _require_digest(value, label=f"v7 {key}")
    return profile


def require_source_manifest_document(raw: bytes) -> dict[str, object]:
    document = _load_canonical_object(raw, label="v7 source manifest")
    if hashlib.sha256(raw).hexdigest() != SOURCE_MANIFEST_SHA256:
        _fail("v7 source manifest identity changed")
    if set(document) != {"files", "schema_id", "source_count"}:
        _fail("v7 source manifest field set changed")
    if (
        document["schema_id"]
        != "betelgeuze.engine_v2_native_fixed64_cpu_source_manifest/7.0.0"
        or document["source_count"] != SOURCE_COUNT
        or type(document["files"]) is not list
        or len(document["files"]) != SOURCE_COUNT
    ):
        _fail("v7 source manifest envelope changed")
    paths: list[str] = []
    for row in document["files"]:
        row = _exact_keys(
            row, {"byte_count", "path", "sha256"}, label="source manifest row"
        )
        path = row["path"]
        if (
            type(path) is not str
            or not path
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or type(row["byte_count"]) is not int
            or row["byte_count"] < 1
        ):
            _fail("v7 source manifest row path or size is invalid")
        _require_digest(row["sha256"], label=f"source {path}")
        paths.append(path)
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        _fail("v7 source manifest paths are not unique and sorted")
    return document


def _stable_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def read_bound_source_bytes(root: Path, relative: Path) -> bytes:
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        _fail("bound source path is invalid")
    root = root.absolute()
    try:
        if root.resolve(strict=True) != root:
            _fail("repository root traverses a symlink")
        root_fd = os.open(
            root,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise NativeFixed64CPUProfileV7Error(
            "repository root cannot be opened safely"
        ) from exc
    descriptors = [root_fd]
    try:
        for component in relative.parts[:-1]:
            try:
                descriptor = os.open(
                    component,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptors[-1],
                )
            except OSError as exc:
                raise NativeFixed64CPUProfileV7Error(
                    f"bound source parent cannot be opened safely: {relative}"
                ) from exc
            descriptors.append(descriptor)
        try:
            source_fd = os.open(
                relative.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=descriptors[-1],
            )
        except OSError as exc:
            raise NativeFixed64CPUProfileV7Error(
                f"bound source cannot be opened safely: {relative}"
            ) from exc
        try:
            before = os.fstat(source_fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.geteuid()
                or before.st_nlink != 1
                or not 1 <= before.st_size <= 16 * 1024 * 1024
            ):
                _fail(f"bound source identity is invalid: {relative}")
            chunks: list[bytes] = []
            observed = 0
            while observed <= 16 * 1024 * 1024:
                chunk = os.read(
                    source_fd, min(1 << 20, 16 * 1024 * 1024 + 1 - observed)
                )
                if not chunk:
                    break
                chunks.append(chunk)
                observed += len(chunk)
            after = os.fstat(source_fd)
            raw = b"".join(chunks)
            if observed != before.st_size or _stable_identity(
                before
            ) != _stable_identity(after):
                _fail(f"bound source changed while read: {relative}")
            return raw
        finally:
            os.close(source_fd)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _discover_sources(
    root: Path, trees: tuple[Path, ...], suffixes: set[str]
) -> set[str]:
    observed: set[str] = set()
    for relative_root in trees:
        tree = root / relative_root
        if tree.is_symlink() or not tree.is_dir():
            _fail(f"compiled source root is invalid: {relative_root}")
        for directory, directory_names, filenames in os.walk(tree, followlinks=False):
            directory_path = Path(directory)
            for name in directory_names:
                if (directory_path / name).is_symlink():
                    _fail("compiled source tree contains a symlinked directory")
            for name in filenames:
                path = directory_path / name
                if path.is_symlink():
                    _fail("compiled source tree contains a symlinked file")
                if path.suffix in suffixes:
                    observed.add(path.relative_to(root).as_posix())
    return observed


def require_bound_source_tree(
    root: Path, manifest: dict[str, object]
) -> dict[str, bytes]:
    rows = manifest["files"]
    assert isinstance(rows, list)
    expected = {str(row["path"]): row for row in rows if isinstance(row, dict)}
    rust_expected = {
        path
        for path in expected
        if any(
            path == tree.as_posix() or path.startswith(f"{tree.as_posix()}/")
            for tree in RUST_SOURCE_ROOTS
        )
        and Path(path).suffix == ".rs"
    }
    native_expected = {
        path
        for path in expected
        if any(
            path == tree.as_posix() or path.startswith(f"{tree.as_posix()}/")
            for tree in NATIVE_SOURCE_ROOTS
        )
        and Path(path).suffix in NATIVE_SOURCE_SUFFIXES
    }
    if _discover_sources(root, RUST_SOURCE_ROOTS, {".rs"}) != rust_expected:
        _fail("Rust compiled source tree contains an unbound or missing source")
    if (
        _discover_sources(root, NATIVE_SOURCE_ROOTS, NATIVE_SOURCE_SUFFIXES)
        != native_expected
    ):
        _fail("native compiled source tree contains an unbound or missing source")
    for forbidden in FORBIDDEN_CONFIGURATION_PATHS:
        try:
            (root / forbidden).lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise NativeFixed64CPUProfileV7Error(
                f"forbidden configuration state is ambiguous: {forbidden}"
            ) from exc
        _fail(f"forbidden repository compiler override exists: {forbidden}")
    sources: dict[str, bytes] = {}
    for path, row in expected.items():
        raw = read_bound_source_bytes(root, Path(path))
        if (
            len(raw) != row["byte_count"]
            or hashlib.sha256(raw).hexdigest() != row["sha256"]
        ):
            _fail(f"bound transitive source changed: {path}")
        sources[path] = raw
    return sources


def require_packaged_activation_assets(
    root: Path,
    *,
    profile_raw: bytes,
    v6_archive_raw: bytes,
    source_manifest_raw: bytes,
    cargo_lock_raw: bytes,
    cargo_manifest_raw: bytes,
) -> None:
    expected = {
        PACKAGED_PROFILE_RELATIVE_PATH: profile_raw,
        PACKAGED_V6_ARCHIVE_RELATIVE_PATH: v6_archive_raw,
        PACKAGED_SOURCE_MANIFEST_RELATIVE_PATH: source_manifest_raw,
        PACKAGED_CARGO_LOCK_RELATIVE_PATH: cargo_lock_raw,
        PACKAGED_CARGO_MANIFEST_RELATIVE_PATH: cargo_manifest_raw,
    }
    for relative, canonical_raw in expected.items():
        if read_bound_source_bytes(root, relative) != canonical_raw:
            _fail(f"packaged v7 activation asset drifted: {relative}")


def require_cargo_target_inventory(root: Path) -> None:
    try:
        completed = subprocess.run(
            [
                "cargo",
                "metadata",
                "--offline",
                "--locked",
                "--no-deps",
                "--format-version",
                "1",
            ],
            cwd=root / "rust",
            check=False,
            capture_output=True,
            env={
                "HOME": os.environ.get("HOME", ""),
                "PATH": os.environ.get("PATH", ""),
                "CARGO_HOME": os.environ.get("CARGO_HOME", str(Path.home() / ".cargo")),
                "RUSTUP_HOME": os.environ.get(
                    "RUSTUP_HOME", str(Path.home() / ".rustup")
                ),
            },
        )
    except OSError as exc:
        raise NativeFixed64CPUProfileV7Error("cargo metadata is unavailable") from exc
    if completed.returncode != 0 or completed.stderr:
        _fail("offline locked cargo metadata failed closed")
    try:
        metadata = json.loads(completed.stdout)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFixed64CPUProfileV7Error("cargo metadata is invalid") from exc
    observed: set[str] = set()
    for package in metadata.get("packages", []):
        for target in package.get("targets", []):
            try:
                observed.add(Path(target["src_path"]).relative_to(root).as_posix())
            except (KeyError, TypeError, ValueError) as exc:
                raise NativeFixed64CPUProfileV7Error(
                    "cargo target escaped the repository"
                ) from exc
    if observed != EXPECTED_CARGO_TARGETS:
        _fail("cargo target source inventory changed")


def require_activation_source_contract(sources: dict[str, bytes]) -> None:
    try:
        qualification = sources[QUALIFICATION_SOURCE_RELATIVE_PATH.as_posix()].decode(
            "utf-8"
        )
        lane_metrics = sources[LANE_METRICS_SOURCE_RELATIVE_PATH.as_posix()].decode(
            "utf-8"
        )
        runner = sources[RUNNER_SOURCE_RELATIVE_PATH.as_posix()].decode("utf-8")
        binary = sources[BINARY_SOURCE_RELATIVE_PATH.as_posix()].decode("utf-8")
        build_source = sources[BUILD_SOURCE_RELATIVE_PATH.as_posix()].decode("utf-8")
        sys_build_source = sources[SYS_BUILD_SOURCE_RELATIVE_PATH.as_posix()].decode(
            "utf-8"
        )
        rustc_wrapper_source = sources[RUSTC_WRAPPER_RELATIVE_PATH.as_posix()].decode(
            "utf-8"
        )
    except (KeyError, UnicodeError) as exc:
        raise NativeFixed64CPUProfileV7Error(
            "v7 activation sources are unavailable"
        ) from exc
    if (
        "pub const FIXED64_CPU_V5_LIVE_ACTIVATION_ADMITTED: bool = false;"
        not in qualification
        or "pub(crate) fn run_native_fixed64_cpu_qualification_successor"
        not in qualification
        or "pub fn run_native_fixed64_cpu_qualification_successor" in qualification
    ):
        _fail("v5 fail-closed gate or v7 internal successor boundary changed")
    if runner.count("run_native_fixed64_cpu_qualification_successor(") != 1:
        _fail("v7 native measurement core has an alternate or missing caller")
    for token in (
        "FIXED64_LANE_METRICS_SCHEMA_ID",
        "FIXED64_LANE_METRICS_REFERENCE_SCHEMA_ID",
        "FIXED64_LANE_METRICS_OBSERVATION_SCHEMA_ID",
        "FIXED64_ORACLE_RMSD_THRESHOLD_ANGSTROM: f64 = 2.0",
        "FIXED64_MAX_SYMMETRY_PERMUTATIONS: usize = 1024",
        "Mapping direction is reference-position -> candidate-position",
        "projection.candidate_denominator != FIXED64_CANDIDATE_COUNT",
        "metrics_used_to_change_rank: false",
        "result_dependent_allocation_consumed: false",
        "public_or_scientific_claim_authorized: false",
        "verify_against(&self, pipeline: &Fixed64PipelineReceipt)",
        "canonical_orientation_sha256",
        "symmetry_aware_direct_heavy_atom_rmsd",
        "CONFORMER_ORIENTATION_PAIRS",
        "FIXED64_LANE_RANGES",
        "lane_metrics_decision_sha256",
        "lane_metrics_sha256",
    ):
        if token not in lane_metrics:
            _fail(f"v7 lane-metrics source contract token is missing: {token}")
    for token in (
        "Fixed64LaneMetricsReceipt::build",
        "cpp_metrics.verify_against(&cpp_metrics_receipt)",
        "rust_metrics.verify_against(&rust_metrics_receipt)",
        "lane_metrics_decision_parity",
        "lane_metrics_rederivable",
        "lane_metrics_authority_false",
        "cpp_scientific_projection",
        "rust_scientific_projection",
        "cpp_lane_metrics",
        "rust_lane_metrics",
    ):
        if token not in qualification:
            _fail(f"v7 qualification lane-metrics token is missing: {token}")
    for token in (
        "cpp_rederivable_evidence",
        "rust_rederivable_evidence",
        "backend_rederivable_evidence_json",
        "decision_preimage_json",
        "lane_metrics_json",
        "numeric_projection_json",
        "projection_digest_stream_json",
        "scorer_validity_rows",
    ):
        if token not in runner:
            _fail(f"v7 rederivable evidence token is missing: {token}")
    for token in (
        "bind_compiled_source_graph(&source_root)",
        "BETELGEUZE_V7_SOURCE_ROOT",
        "cargo:rustc-env={COMPILED_MANIFEST_ENV}",
        "cargo:rustc-env={COMPILED_PROFILE_ENV}",
        "cargo:rustc-env={BUILD_COMMIT_ENV}",
        "cargo:rustc-env={BUILD_COMMIT_BOUND_ENV}",
        "cargo:rustc-env={BUILD_CONFIGURATION_SHA256_ENV}",
        "cargo:rustc-env={BUILD_CONFIGURATION_BOUND_ENV}",
        "cargo:rustc-env={VERIFIED_SOURCE_ROOT_ENV}",
        "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD",
        "BETELGEUZE_V7_QUALIFICATION_BUILD",
        "EXPECTED_BUILD_CONFIGURATION_SHA256",
        "EXPECTED_RUSTC_SHA256",
        "EXPECTED_CARGO_SHA256",
        "EXPECTED_CPP_SHA256",
        "EXPECTED_RUSTC_WRAPPER_SHA256",
        "EXPECTED_RUSTC_WRAPPER_INTERPRETER_SHA256",
        "qualification_rustc_wrapper_is_exact",
        "betelgeuze_v7_effective_rust_flags_verified",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_CFG_TARGET_FEATURE",
        "FORBIDDEN_BUILD_ENVIRONMENT",
        "UNBOUND_BUILD_COMMIT_OID",
        "committed_blob(source_root, commit_oid, PROFILE_RELATIVE_PATH)",
        "track_git_commit_inputs(source_root)",
        'git_path(source_root, "HEAD")',
        'git_path(source_root, "packed-refs")',
        'emit_rerun_if_changed(&reference_path, "symbolic HEAD reference")',
        "canonical_profile, PACKAGED_PROFILE_BYTES",
        "cargo:rerun-if-changed={}",
        "sha256_hex(&raw)",
        "row.sha256,",
    ):
        if token not in build_source:
            _fail(f"v7 compile-time source binding token is missing: {token}")
    activation_start = runner.find("pub fn verify_native_fixed64_cpu_v7_activation(")
    activation_end = runner.find("\nfn source_root()", activation_start)
    if activation_start < 0 or activation_end < 0:
        _fail("v7 activation verification entry point is unavailable")
    activation_body = runner[activation_start:activation_end]
    for token in (
        'BUILD_COMMIT_BOUND != "true"',
        "non-authoritative package build cannot activate",
        'BUILD_CONFIGURATION_BOUND != "true"',
        "build configuration is not frozen",
        "build_configuration_sha256",
    ):
        if token not in activation_body:
            _fail(f"v7 non-authoritative package rejection token is missing: {token}")
    for token in (
        "native_lane_metrics_activation_frozen_execution_not_consumed",
        "fd83f1f7f7c92bc0fc9ac6581cababb23d3ba5787412174a55b659f97fcc2928",
        'COMPILED_SOURCE_COUNT != "196"',
        'manifest.matches("\\"source_count\\": 196").count() != 1',
    ):
        if token not in activation_body:
            _fail(f"v7 activation exact identity token is missing: {token}")
    for token in (
        'const QUALIFICATION_CPP_COMPILER: &str = "/usr/bin/x86_64-linux-gnu-g++-11";',
        "const QUALIFICATION_CPP_FLAGS: &[&str]",
        ".no_default_flags(true)",
        ".compiler(QUALIFICATION_CPP_COMPILER)",
        '"-ffp-contract=off"',
        '"-fno-fast-math"',
        '"-Werror"',
        "QUALIFICATION_FORBIDDEN_ENVIRONMENT",
        "v7 CPU qualification build cannot link hip_safe",
        "QUALIFICATION_RUSTC_WRAPPER_RELATIVE_PATH",
        'std::env::var_os("RUSTC_WRAPPER")',
    ):
        if token not in sys_build_source:
            _fail(f"v7 frozen C++ build token is missing: {token}")
    for token in (
        "CONTROLLED_LIBRARY_CRATES",
        "CONTROLLED_CFG_VALUES",
        "ALLOWED_QUERY_ARGUMENTS",
        '"opt-level": "3"',
        'expected["lto"] = "fat"',
        'arguments.extend(["-C", "linker-plugin-lto"])',
        "effective -C option names differ from the frozen profile",
        "cfg values differ from the frozen profile",
        "os.execv(rustc",
        "unstable rustc options are forbidden",
        "betelgeuze_v7_effective_rust_flags_verified",
    ):
        if token not in rustc_wrapper_source:
            _fail(f"v7 effective rustc wrapper token is missing: {token}")
    start = runner.find("pub fn run_native_fixed64_cpu_qualification_v7(")
    end = runner.find("\n#[cfg(test)]", start)
    if start < 0 or end < 0:
        _fail("v7 public transaction entry point is unavailable")
    body = runner[start:end]
    ordered = [
        "deny_github_actions_live_execution()?;",
        "verify_native_fixed64_cpu_v7_activation()?;",
        "validate_absent_output(output_path)?;",
        "open_account_state(&activation.profile_sha256)?;",
        "create_attempt(",
        "preflight_native_fixed64_cpu_v7()?;",
        "execute_measurement(&preflight);",
        "build_artifact(",
    ]
    cursor = -1
    for token in ordered:
        position = body.find(token, cursor + 1)
        if position < 0:
            _fail(f"v7 transaction ordering token is missing: {token}")
        cursor = position
    artifact_publish = body.find("publish_absent_file_at(", cursor + 1)
    terminal_build = body.find("build_terminal(", artifact_publish + 1)
    terminal_publish = body.find("publish_absent_file_at(", terminal_build + 1)
    returned = body.rfind("Ok(Fixed64CpuPersistedQualificationV7")
    if not cursor < artifact_publish < terminal_build < terminal_publish < returned:
        _fail("v7 artifact/terminal/return transaction order changed")
    for token in (
        "libc::O_EXCL",
        "libc::O_NOFOLLOW",
        "libc::linkat",
        "libc::fsync",
        "login_account_home()",
        "STATE_QUALIFICATION_NAME",
        "require_account_state_binding(&state)?;",
        "output cannot cross-wire account state",
        "output parent binding changed",
        "output filename cannot support atomic staging",
        "../assets/original-Cargo.toml",
        "COMPILED_SOURCE_MANIFEST_SHA256",
        "COMPILED_PROFILE_SHA256",
        "BUILD_COMMIT_OID",
        "BUILD_CONFIGURATION_SHA256",
        "v7 qualification effective rustc flags were not wrapper-verified",
        "VERIFIED_SOURCE_ROOT",
        "source commit differs from the verified build commit",
        "post_measurement_host_invariant_failed",
        "path.to_str().is_none()",
        "profile state binding changed",
        "decision_returned_only_after_terminal_persistence",
        'qualification_authority\\":false',
        'hip_device_execution_allowed\\":false',
        'actual_molecular_execution_allowed\\":false',
    ):
        if token not in runner:
            _fail(f"v7 fail-closed transaction token is missing: {token}")
    if (
        "--verify-activation" not in binary
        or "--preflight" not in binary
        or "--run-output" not in binary
        or "run_native_fixed64_cpu_qualification_v7(Path::new(&arguments[2]))"
        not in binary
        or "Fixed64CpuProbeConfigV5" in binary
        or "run_native_fixed64_cpu_probe_v5" in binary
        or "to_string_lossy" in binary
    ):
        _fail("v7 binary accepted a custom probe or lost a sealed operation")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    profile_raw = read_bound_source_bytes(root, PROFILE_RELATIVE_PATH)
    manifest_raw = read_bound_source_bytes(root, SOURCE_MANIFEST_RELATIVE_PATH)
    v6_profile_raw = read_bound_source_bytes(root, V6_PROFILE_RELATIVE_PATH)
    v6_archive_raw = read_bound_source_bytes(root, V6_ARCHIVE_RELATIVE_PATH)
    manifest = require_source_manifest_document(manifest_raw)
    sources = require_bound_source_tree(root, manifest)
    require_packaged_activation_assets(
        root,
        profile_raw=profile_raw,
        v6_archive_raw=v6_archive_raw,
        source_manifest_raw=manifest_raw,
        cargo_lock_raw=sources[CARGO_LOCK_RELATIVE_PATH.as_posix()],
        cargo_manifest_raw=sources[CARGO_MANIFEST_RELATIVE_PATH.as_posix()],
    )
    require_profile_document_v7(
        profile_raw,
        v6_profile_raw,
        v6_archive_raw,
        manifest_raw,
        sources,
    )
    require_cargo_target_inventory(root)
    require_activation_source_contract(sources)
    print(
        json.dumps(
            {
                "all_authority_false": True,
                "compiled_profile_binding_verified": True,
                "build_configuration_sha256": BUILD_CONFIGURATION_SHA256,
                "execution_consumed": False,
                "live_execution_implemented": True,
                "non_consuming_preflight_only": True,
                "profile_id": PROFILE_ID,
                "profile_sha256": PROFILE_SHA256,
                "source_count": SOURCE_COUNT,
                "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
                "status": "native_lane_metrics_activation_frozen_execution_not_consumed",
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
