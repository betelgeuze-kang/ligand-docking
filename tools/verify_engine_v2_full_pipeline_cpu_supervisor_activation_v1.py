#!/usr/bin/env python3
"""Verify the packaged, non-consuming CPU supervisor activation v1 contract."""

from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import struct
import subprocess
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT
    / "config/engine_v2_full_pipeline_cpu_supervisor_activation_v1.json"
)
DEFAULT_ROSTER = (
    REPOSITORY_ROOT
    / "config/engine_v2_full_pipeline_cpu_supervisor_activation_v1_roster.json"
)
DEFAULT_SUPERVISOR_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_full_pipeline_cpu_supervisor_v1.json"
)
DEFAULT_SUPERVISOR_SOURCE = (
    REPOSITORY_ROOT
    / "native/tools/engine_v2_full_pipeline_cpu_supervisor_v1.cpp"
)
DEFAULT_PREFLIGHT = (
    REPOSITORY_ROOT
    / "tools/preflight_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py"
)
DEFAULT_BINARY = (
    REPOSITORY_ROOT
    / "packaging/engine-v2/full-pipeline-cpu-supervisor/1.0.0"
    / "engine-v2-full-pipeline-cpu-supervisor-v1"
)
DEFAULT_SBOM = DEFAULT_BINARY.with_suffix(".spdx.json")
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT
    / "docs/engine_v2_full_pipeline_cpu_supervisor_activation_v1.md"
)
DEFAULT_TESTS = (
    REPOSITORY_ROOT
    / "tests/unit/test_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py",
    REPOSITORY_ROOT
    / "tests/unit/test_verify_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py",
)
DEFAULT_CI_AUDIT = REPOSITORY_ROOT / "tools/audit_engine_v2_ci_authority.py"
DEFAULT_WORKFLOWS = (
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-main.yml",
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml",
    REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml",
)

SCHEMA_ID = "betelgeuze.engine_v2_full_pipeline_cpu_supervisor_activation/1.0.0"
ACTIVATION_ID = "engine_v2_full_pipeline_cpu_supervisor_activation_v1"
STATUS = "frozen_packaged_non_consuming_activation_not_operational"
EXPECTED_BINARY_SHA256 = (
    "c7da6610ea596b3cb9580ebfdfc2f608bd27faca97932cadf25af2ec278bbf1b"
)
EXPECTED_BINARY_SHA1 = "064c551527e107c41ebe7a30e22736b8276d5465"
EXPECTED_PREFLIGHT_SHA256 = (
    "aff270795a85a3e6660b0f3f990a3542f1ee05a7fb3795b9146dc7dd062070b6"
)
EXPECTED_PREFLIGHT_SHA1 = "f8c1d1ba69425748f5d8cdbb4f0974c2829b9066"
EXPECTED_SOURCE_SHA256 = (
    "0fdf424349ff075d0bef0a92718ef69e8213eb59f19d2ef175eccde15d71f5e1"
)
EXPECTED_SOURCE_SHA1 = "f952e0298e0dde9e864c7552454dbe0b742b6a82"
EXPECTED_SUPERVISOR_CONTRACT_SHA256 = (
    "e6002252e240f8086c3051bdb3018b643855b42588ada1c7c1e58bef0fbb0c9a"
)
EXPECTED_ROSTER_SHA256 = (
    "a607613fd6d3a76d1d2d94f7be68d0493c6b23de28c97adfe5193d96732c58e1"
)
EXPECTED_ROSTER_SHA1 = "64ace7107e6e16083ef0baa0287f4604e86b5415"
EXPECTED_SBOM_SHA256 = (
    "82eb88536ecb12467633ff957e4ec532aa0abcc8f4ab04e0ecc439b8a0ad9b51"
)
EXPECTED_PACKAGE_VERIFICATION_CODE = "f1c1555460b9f23da98572f5e41fc9ee6134fc65"
EXPECTED_EXTERNAL_BLOCKERS = [
    "external_reservation_provider_not_operational",
    "external_reservation_endpoint_not_configured",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
]
EXPECTED_LOCAL_BLOCKERS = [
    "supervisor_account_provisioning_receipt_missing",
    "supervisor_root_installation_receipt_missing",
    "supervisor_namespace_trace_qualification_missing",
    "supervisor_performance_preflight_not_bound",
    "supervisor_terminal_downstream_receipt_missing",
    "supervisor_exactly_once_runner_not_bound",
]


class SupervisorActivationContractError(RuntimeError):
    """Raised when the package/roster/handoff activation contract drifts."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise SupervisorActivationContractError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SupervisorActivationContractError(f"bound file unavailable: {path}") from exc


def _load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = _read_bytes(path)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant: {value}")
            ),
        )
    except (UnicodeError, ValueError) as exc:
        raise SupervisorActivationContractError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SupervisorActivationContractError(f"JSON root is not an object: {path}")
    canonical = (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if raw != canonical:
        raise SupervisorActivationContractError(f"JSON is not canonical: {path}")
    return value, raw


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_keys(value: dict[str, Any], expected: set[str], *, name: str) -> None:
    if set(value) != expected:
        raise SupervisorActivationContractError(f"{name} key set drifted")


def _require_false_mapping(value: object, *, name: str) -> dict[str, bool]:
    if not isinstance(value, dict) or not value or any(item is not False for item in value.values()):
        raise SupervisorActivationContractError(f"{name} authority is not entirely false")
    return value


def _require_boolean_mapping(
    value: object,
    expected: dict[str, bool],
    *,
    name: str,
) -> dict[str, bool]:
    if (
        not isinstance(value, dict)
        or set(value) != set(expected)
        or any(value[key] is not expected[key] for key in expected)
    ):
        raise SupervisorActivationContractError(f"{name} boolean contract drifted")
    return value


def _git_bytes(repository_root: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise SupervisorActivationContractError(
            f"git object unavailable: {' '.join(arguments)}"
        ) from exc


def _verify_foundation(document: dict[str, Any], repository_root: Path) -> None:
    expected = {
        "merged_main_commit_object_encoding": "git_cat_file_commit_raw_v1",
        "merged_main_commit_oid": "2d03360e782ec9f06518b704ac4fb498fb3448e6",
        "merged_main_commit_sha256": (
            "054884d6ea57633d4b7e5335b115f91149a0f3967a1366f625d67769d8f1daac"
        ),
        "merged_main_tree_manifest_encoding": "git_ls_tree_r_full_tree_z_v1",
        "merged_main_tree_oid": "e0dd19eb3efab258d88d192440b025d79b6c9802",
        "merged_main_tree_sha256": (
            "315f9ef674fa00c6edd65aa204688344f4de39bc62460979452c914e39a5b151"
        ),
    }
    if document != expected:
        raise SupervisorActivationContractError("merged-main foundation drifted")
    commit = _git_bytes(repository_root, "cat-file", "commit", expected["merged_main_commit_oid"])
    tree = _git_bytes(
        repository_root,
        "ls-tree",
        "-r",
        "--full-tree",
        "-z",
        expected["merged_main_tree_oid"],
    )
    if _sha256(commit) != expected["merged_main_commit_sha256"]:
        raise SupervisorActivationContractError("merged-main commit bytes changed")
    if _sha256(tree) != expected["merged_main_tree_sha256"]:
        raise SupervisorActivationContractError("merged-main tree manifest changed")


def _verify_roster(document: dict[str, Any]) -> None:
    expected = {
        "authority": {
            "installation_authorized": False,
            "qualification_consumption_authorized": False,
            "reservation_authorized": False,
            "runtime_launch_authorized": False,
        },
        "client": {
            "account_name": "betelgeuze-engine-v2-qualification",
            "gid": 64042,
            "group_name": "betelgeuze-engine-v2-qualification",
            "home": "/nonexistent",
            "private_primary_group_required": True,
            "role": "non_consuming_cpu_qualification_client",
            "shell": "/usr/sbin/nologin",
            "supplementary_groups": [],
            "uid": 64042,
        },
        "provisioning": {
            "account_provisioning_receipt_present": False,
            "account_provisioning_state": "not_evidenced",
            "host_identity_collision_check_required": True,
            "repository_account_creation_allowed": False,
            "root_installation_receipt_present": False,
            "systemd_unit_present": False,
        },
        "roster_id": "engine_v2_full_pipeline_cpu_supervisor_activation_v1_roster",
        "schema_id": "betelgeuze.engine_v2_full_pipeline_cpu_supervisor_roster/1.0.0",
        "service": {
            "gid": 0,
            "role": "root_supervisor_service",
            "supplementary_groups_allowed": False,
            "uid": 0,
        },
        "status": "frozen_desired_state_not_provisioned",
    }
    if document != expected:
        raise SupervisorActivationContractError("supervisor roster drifted")

    account_name = expected["client"]["account_name"]
    group_name = expected["client"]["group_name"]
    for lookup, value in (
        (pwd.getpwnam, account_name),
        (pwd.getpwuid, 64042),
        (grp.getgrnam, group_name),
        (grp.getgrgid, 64042),
    ):
        try:
            lookup(value)
        except KeyError:
            continue
        raise SupervisorActivationContractError(
            "desired non-consuming supervisor identity is already provisioned or collides"
        )


def _elf_program_types(raw: bytes) -> set[int]:
    if len(raw) < 64 or raw[:7] != b"\x7fELF\x02\x01\x01":
        raise SupervisorActivationContractError("package binary is not little-endian ELF64")
    executable_type, machine = struct.unpack_from("<HH", raw, 16)
    offset = struct.unpack_from("<Q", raw, 32)[0]
    entry_size, count = struct.unpack_from("<HH", raw, 54)
    if executable_type != 2 or machine != 62 or entry_size < 56 or count == 0:
        raise SupervisorActivationContractError("package binary architecture drifted")
    if offset + entry_size * count > len(raw):
        raise SupervisorActivationContractError("package binary program headers overflow")
    return {
        struct.unpack_from("<I", raw, offset + index * entry_size)[0]
        for index in range(count)
    }


def _verify_package(
    package: dict[str, Any],
    *,
    repository_root: Path,
    binary_path: Path,
    sbom_path: Path,
    source_path: Path,
    preflight_path: Path,
    roster_path: Path,
) -> None:
    binary = _read_bytes(binary_path)
    sbom, sbom_raw = _load_json(sbom_path)
    if (
        _sha256(binary) != EXPECTED_BINARY_SHA256
        or len(binary) != 2_069_736
        or stat.S_IMODE(binary_path.stat().st_mode) != 0o555
        or 2 in _elf_program_types(binary)
        or 3 in _elf_program_types(binary)
    ):
        raise SupervisorActivationContractError("static supervisor package binary drifted")
    if _sha256(sbom_raw) != EXPECTED_SBOM_SHA256 or len(sbom_raw) != 4_586:
        raise SupervisorActivationContractError("supervisor package SBOM drifted")
    if package.get("binary_sha256") != EXPECTED_BINARY_SHA256:
        raise SupervisorActivationContractError("package binary binding drifted")
    if package.get("sbom_sha256") != EXPECTED_SBOM_SHA256:
        raise SupervisorActivationContractError("package SBOM binding drifted")
    if package.get("static_elf_no_dynamic_or_interp") is not True:
        raise SupervisorActivationContractError("package static-ELF gate drifted")
    if package.get("double_build_byte_identity_verified") is not True:
        raise SupervisorActivationContractError("package double-build evidence drifted")
    expected_flags = [
        "-std=c++17",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        "-static",
        "-s",
        "-Wl,--build-id=none",
        "-DBETELGEUZE_ENGINE_V2_SUPERVISOR_CLIENT_UID=64042U",
        "-DBETELGEUZE_ENGINE_V2_SUPERVISOR_CLIENT_GID=64042U",
        (
            '-DBETELGEUZE_ENGINE_V2_SUPERVISOR_PREFLIGHT_SHA256="'
            + EXPECTED_PREFLIGHT_SHA256
            + '"'
        ),
    ]
    expected_package = {
        "binary_mode": "0555",
        "binary_path": (
            "packaging/engine-v2/full-pipeline-cpu-supervisor/1.0.0/"
            "engine-v2-full-pipeline-cpu-supervisor-v1"
        ),
        "binary_sha256": EXPECTED_BINARY_SHA256,
        "binary_size_bytes": 2_069_736,
        "build_flags": expected_flags,
        "compiler_path": "/usr/bin/g++",
        "compiler_sha256": (
            "2360901d864cf10bfd6296e261cb2c14053552a80377761ab07146ec9ec9a2c0"
        ),
        "compiler_version": (
            "g++ (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0"
        ),
        "double_build_byte_identity_verified": True,
        "installation_path": (
            "/usr/local/libexec/"
            "betelgeuze-engine-v2-full-pipeline-cpu-supervisor-v1"
        ),
        "package_id": (
            "engine_v2_full_pipeline_cpu_supervisor_v1_rostered_static_x86_64"
        ),
        "repository_index_mode": "100755",
        "repository_materialization": (
            "explicit_chmod_0555_before_verification"
        ),
        "sbom_path": (
            "packaging/engine-v2/full-pipeline-cpu-supervisor/1.0.0/"
            "engine-v2-full-pipeline-cpu-supervisor-v1.spdx.json"
        ),
        "sbom_sha256": EXPECTED_SBOM_SHA256,
        "sbom_size_bytes": 4_586,
        "static_elf_no_dynamic_or_interp": True,
        "target_triple": "x86_64-linux-gnu",
    }
    if package != expected_package:
        raise SupervisorActivationContractError("package contract drifted")
    index_entry = _git_bytes(
        repository_root,
        "ls-files",
        "--stage",
        "--",
        expected_package["binary_path"],
    ).decode("utf-8")
    index_fields = index_entry.rstrip("\n").split(maxsplit=3)
    if (
        len(index_fields) != 4
        or index_fields[0] != "100755"
        or index_fields[2] != "0"
        or index_fields[3] != expected_package["binary_path"]
    ):
        raise SupervisorActivationContractError("package Git index mode drifted")
    files = {row.get("SPDXID"): row for row in sbom.get("files", []) if isinstance(row, dict)}
    expected_files = {
        "SPDXRef-File-Binary": (
            binary_path,
            EXPECTED_BINARY_SHA1,
            EXPECTED_BINARY_SHA256,
        ),
        "SPDXRef-File-Source": (
            source_path,
            EXPECTED_SOURCE_SHA1,
            EXPECTED_SOURCE_SHA256,
        ),
        "SPDXRef-File-Preflight": (
            preflight_path,
            EXPECTED_PREFLIGHT_SHA1,
            EXPECTED_PREFLIGHT_SHA256,
        ),
        "SPDXRef-File-Roster": (
            roster_path,
            EXPECTED_ROSTER_SHA1,
            EXPECTED_ROSTER_SHA256,
        ),
    }
    if set(files) != set(expected_files):
        raise SupervisorActivationContractError("package SBOM file inventory drifted")
    for spdx_id, (path, sha1_digest, sha256_digest) in expected_files.items():
        checksums = files[spdx_id].get("checksums")
        if checksums != [
            {"algorithm": "SHA1", "checksumValue": sha1_digest},
            {"algorithm": "SHA256", "checksumValue": sha256_digest},
        ]:
            raise SupervisorActivationContractError(f"package SBOM checksum drifted: {spdx_id}")
        raw = _read_bytes(path)
        if (
            hashlib.sha1(raw, usedforsecurity=False).hexdigest() != sha1_digest
            or _sha256(raw) != sha256_digest
        ):
            raise SupervisorActivationContractError(f"package payload drifted: {path}")
    packages = sbom.get("packages")
    if type(packages) is not list or len(packages) != 1 or type(packages[0]) is not dict:
        raise SupervisorActivationContractError("package SBOM package inventory drifted")
    spdx_package = packages[0]
    expected_package_checksums = [
        {"algorithm": "SHA1", "checksumValue": EXPECTED_BINARY_SHA1},
        {"algorithm": "SHA256", "checksumValue": EXPECTED_BINARY_SHA256},
    ]
    derived_verification_code = hashlib.sha1(
        EXPECTED_BINARY_SHA1.encode("ascii"),
        usedforsecurity=False,
    ).hexdigest()
    if (
        spdx_package.get("SPDXID") != "SPDXRef-Package-Supervisor"
        or spdx_package.get("filesAnalyzed") is not True
        or spdx_package.get("hasFiles") != ["SPDXRef-File-Binary"]
        or spdx_package.get("checksums") != expected_package_checksums
        or spdx_package.get("packageVerificationCode")
        != {"packageVerificationCodeValue": EXPECTED_PACKAGE_VERIFICATION_CODE}
        or derived_verification_code != EXPECTED_PACKAGE_VERIFICATION_CODE
    ):
        raise SupervisorActivationContractError(
            "package SBOM verification-code evidence drifted"
        )
    described = subprocess.run(
        [str(binary_path), "--describe-contract"],
        check=True,
        capture_output=True,
        text=True,
    )
    description = json.loads(described.stdout)
    if (
        description.get("authority_false") is not True
        or description.get("client_uid") != 64042
        or description.get("client_gid") != 64042
        or description.get("client_identity_configured") is not True
        or description.get("preflight_sha256") != EXPECTED_PREFLIGHT_SHA256
        or description.get("operational") is not False
        or description.get("installation_authorized") is not False
        or description.get("runtime_launch_authorized") is not False
        or description.get("qualification_consumption_authorized") is not False
    ):
        raise SupervisorActivationContractError("package binary authority drifted")
    rejected = subprocess.run(
        [str(binary_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if rejected.returncode != 125 or "remain unauthorized" not in rejected.stderr:
        raise SupervisorActivationContractError("package service entry did not fail closed")
    socket_path = Path("/run/betelgeuze-engine-v2/full-pipeline-cpu-supervisor-v1.sock")
    installation_path = Path(
        "/usr/local/libexec/betelgeuze-engine-v2-full-pipeline-cpu-supervisor-v1"
    )
    systemd_unit_path = Path(
        "/etc/systemd/system/betelgeuze-engine-v2-full-pipeline-cpu-supervisor-v1.service"
    )
    if os.path.lexists(socket_path):
        raise SupervisorActivationContractError("package service socket unexpectedly exists")
    if os.path.lexists(installation_path) or os.path.lexists(systemd_unit_path):
        raise SupervisorActivationContractError(
            "supervisor package or service unit is unexpectedly installed"
        )


def _verify_handoff(handoff: dict[str, Any], preflight_path: Path) -> None:
    expected_handoff = {
        "actual_handoff_receipt_present": False,
        "descriptor_count": 3,
        "descriptor_roles": [
            "sealed_handoff_receipt",
            "initial_user_namespace",
            "initial_mount_namespace",
        ],
        "expected_flags": [
            "exec_observed",
            "peer_credential_bound",
            "namespace_fds_bound",
        ],
        "handoff_bytes": 464,
        "handoff_magic": "BGV2CPUHANDOF1",
        "namespace_fd_ioctls": [
            "NS_GET_NSTYPE",
            "NS_GET_OWNER_UID",
            "NS_GET_PARENT",
            "NS_GET_USERNS",
        ],
        "peer_pidfd_required": True,
        "preflight_sha256": EXPECTED_PREFLIGHT_SHA256,
        "preflight_size_bytes": 23_361,
        "preflight_source_path": (
            "tools/preflight_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py"
        ),
        "sealed_receipt_mode": "0400",
        "sealed_receipt_required_seals": [
            "F_SEAL_SEAL",
            "F_SEAL_SHRINK",
            "F_SEAL_GROW",
            "F_SEAL_WRITE",
        ],
        "socket_peer_credential_required": (
            "SO_PEERCRED_root_service_socketpair"
        ),
        "terminal_bytes": 96,
        "terminal_magic": "BGV2CPUTERMV1",
        "terminal_parser_implemented": True,
        "version": 1,
    }
    if (
        handoff != expected_handoff
        or type(handoff.get("version")) is not int
        or type(handoff.get("descriptor_count")) is not int
        or type(handoff.get("handoff_bytes")) is not int
        or type(handoff.get("terminal_bytes")) is not int
        or type(handoff.get("preflight_size_bytes")) is not int
        or handoff.get("preflight_sha256") != EXPECTED_PREFLIGHT_SHA256
        or handoff.get("preflight_size_bytes") != len(_read_bytes(preflight_path))
        or handoff.get("handoff_bytes") != 464
        or handoff.get("terminal_bytes") != 96
        or handoff.get("descriptor_count") != 3
        or handoff.get("peer_pidfd_required") is not True
        or handoff.get("terminal_parser_implemented") is not True
        or handoff.get("actual_handoff_receipt_present") is not False
    ):
        raise SupervisorActivationContractError("handoff contract drifted")
    source = _read_bytes(preflight_path).decode("utf-8")
    for token in (
        "SO_PEERPIDFD = 77",
        "socket.SO_PEERCRED",
        "socket.SCM_RIGHTS",
        "socket.MSG_CMSG_CLOEXEC",
        "rights_messages = 0",
        "ancillary_shape_changed = False",
        "NS_GET_NSTYPE",
        "NS_GET_OWNER_UID",
        "NS_GET_PARENT",
        "NS_GET_USERNS",
        "REQUIRED_MEMFD_SEALS",
        "source_digest != preflight_digest",
        "verify_terminal_packet",
        "downstream performance preflight binding is not admitted",
        "GitHub Actions cannot run the supervisor activation preflight",
    ):
        if token not in source:
            raise SupervisorActivationContractError(f"handoff preflight lost invariant: {token}")
    process_gate = source.index("source_sha256 = _require_exact_process_state()")
    receive_call = source.index(
        "with receive_and_verify_handoff(",
        process_gate,
    )
    if source.index("GitHub Actions cannot run") > receive_call:
        raise SupervisorActivationContractError("GitHub Actions rejection moved after handoff")
    receive_definition = source.index("def receive_and_verify_handoff(")
    descriptor_capture = source.index("received.extend(", receive_definition)
    truncation_rejection = source.index(
        "if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):",
        receive_definition,
    )
    if descriptor_capture > truncation_rejection:
        raise SupervisorActivationContractError(
            "truncated ancillary descriptors are not captured for cleanup"
        )


def _verify_workflows(paths: tuple[Path, ...]) -> None:
    required = (
        "config/engine_v2_full_pipeline_cpu_supervisor_activation_v1.json",
        "config/engine_v2_full_pipeline_cpu_supervisor_activation_v1_roster.json",
        "tools/preflight_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py",
        "tools/verify_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py",
        "tests/unit/test_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py",
        "tests/unit/test_verify_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py",
        "docs/engine_v2_full_pipeline_cpu_supervisor_activation_v1.md",
        "engine-v2-full-pipeline-cpu-supervisor-v1.spdx.json",
        (
            "chmod 0555 packaging/engine-v2/full-pipeline-cpu-supervisor/"
            "1.0.0/engine-v2-full-pipeline-cpu-supervisor-v1"
        ),
        (
            "git fetch --no-tags --depth=1 origin "
            "2d03360e782ec9f06518b704ac4fb498fb3448e6"
        ),
        "Verify packaged full-pipeline CPU supervisor activation v1",
    )
    for path in paths:
        source = _read_bytes(path).decode("utf-8")
        if any(token not in source for token in required):
            raise SupervisorActivationContractError(
                f"authoritative workflow lost supervisor activation input: {path.name}"
            )
        for forbidden in (
            "sudo systemctl",
            "--serve-supervisor",
            "full-pipeline-cpu-supervisor-v1.sock --launch",
        ):
            if forbidden in source:
                raise SupervisorActivationContractError(
                    f"authoritative workflow gained service execution: {path.name}"
                )


def _verify_ci_audit(path: Path) -> None:
    source = _read_bytes(path).decode("utf-8")
    for token in (
        "FULL_PIPELINE_CPU_SUPERVISOR_ACTIVATION_CONTRACT_PATHS",
        "FULL_PIPELINE_CPU_SUPERVISOR_ACTIVATION_REQUIRED_TOKEN_COUNTS",
        "_full_pipeline_cpu_supervisor_activation_authority_is_fail_closed",
        "full_pipeline_cpu_supervisor_activation_authority_fail_closed",
        "full_pipeline_cpu_supervisor_activation_in_authoritative_ci",
        EXPECTED_BINARY_SHA256,
        EXPECTED_PREFLIGHT_SHA256,
    ):
        if token not in source:
            raise SupervisorActivationContractError(
                f"CI authority audit lost supervisor activation binding: {token}"
            )


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    roster_path: Path = DEFAULT_ROSTER,
    supervisor_contract_path: Path = DEFAULT_SUPERVISOR_CONTRACT,
    supervisor_source_path: Path = DEFAULT_SUPERVISOR_SOURCE,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    binary_path: Path = DEFAULT_BINARY,
    sbom_path: Path = DEFAULT_SBOM,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
    test_paths: tuple[Path, ...] = DEFAULT_TESTS,
    ci_audit_path: Path = DEFAULT_CI_AUDIT,
    workflow_paths: tuple[Path, ...] = DEFAULT_WORKFLOWS,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    contract, contract_raw = _load_json(contract_path)
    _require_keys(
        contract,
        {
            "activation_id",
            "authority",
            "bindings",
            "downstream_binding",
            "external_authority",
            "foundation",
            "handoff",
            "lifecycle",
            "package",
            "restrictions",
            "roster",
            "schema_id",
            "status",
        },
        name="activation contract",
    )
    if (
        contract["schema_id"] != SCHEMA_ID
        or contract["activation_id"] != ACTIVATION_ID
        or contract["status"] != STATUS
    ):
        raise SupervisorActivationContractError("activation identity drifted")
    _require_boolean_mapping(
        contract["authority"],
        {
            "fresh_holdout_execution_authorized": False,
            "github_actions_production_authority": False,
            "hip_device_execution_authorized": False,
            "installation_authorized": False,
            "molecular_execution_authorized": False,
            "performance_measurement_authorized": False,
            "product_execution_authorized": False,
            "public_benchmark_authorized": False,
            "qualification_consumption_authorized": False,
            "reservation_authorized": False,
            "runtime_launch_authorized": False,
            "scientific_claim_authorized": False,
            "stage0_admission_authorized": False,
            "test_double_production_authority": False,
        },
        name="activation authority",
    )
    _require_boolean_mapping(
        contract["restrictions"],
        {
            "actual_molecular_execution_allowed": False,
            "actual_supervisor_service_execution_allowed": False,
            "fresh_or_historical_case_input_allowed": False,
            "github_actions_service_execution_allowed": False,
            "hip_device_execution_allowed": False,
            "package_installation_allowed": False,
            "performance_measurement_allowed": False,
            "production_credentials_allowed": False,
            "production_endpoint_access_allowed": False,
            "qualification_consumption_allowed": False,
            "reservation_allowed": False,
            "result_dependent_configuration_allowed": False,
            "test_double_production_authority_allowed": False,
        },
        name="activation restriction",
    )
    _verify_foundation(contract["foundation"], repository_root)

    supervisor_contract, supervisor_raw = _load_json(supervisor_contract_path)
    roster, roster_raw = _load_json(roster_path)
    _verify_roster(roster)
    if _sha256(supervisor_raw) != EXPECTED_SUPERVISOR_CONTRACT_SHA256:
        raise SupervisorActivationContractError("supervisor contract binding drifted")
    if _sha256(roster_raw) != EXPECTED_ROSTER_SHA256:
        raise SupervisorActivationContractError("roster binding drifted")
    _require_false_mapping(supervisor_contract.get("authority"), name="supervisor")
    if _sha256(_read_bytes(supervisor_source_path)) != EXPECTED_SOURCE_SHA256:
        raise SupervisorActivationContractError("supervisor source binding drifted")
    if _sha256(_read_bytes(preflight_path)) != EXPECTED_PREFLIGHT_SHA256:
        raise SupervisorActivationContractError("handoff preflight binding drifted")

    bindings = contract["bindings"]
    if bindings != {
        "full_pipeline_performance_activation_sha256": (
            "0c282c168e201eea5ac9315f50d1fd49aa2d825804d1f03b89602c5cbae21325"
        ),
        "full_pipeline_profile_sha256": (
            "385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000"
        ),
        "predecessor_supervisor_contract_sha256": (
            "4f144f83563f6ca48835c4e59432bcb4c8c59feb2a76570961b0cd6887c1c076"
        ),
        "runtime_scope_manifest_sha256": (
            "72b90f500af43c921ce0b8f7d6774c5e99a7e4f3fe366478b3fc33b524b4b404"
        ),
        "supervisor_contract_sha256": EXPECTED_SUPERVISOR_CONTRACT_SHA256,
        "supervisor_source_sha256": EXPECTED_SOURCE_SHA256,
    }:
        raise SupervisorActivationContractError("activation source bindings drifted")

    _verify_package(
        contract["package"],
        repository_root=repository_root,
        binary_path=binary_path,
        sbom_path=sbom_path,
        source_path=supervisor_source_path,
        preflight_path=preflight_path,
        roster_path=roster_path,
    )
    _verify_handoff(contract["handoff"], preflight_path)

    _require_boolean_mapping(
        contract["lifecycle"],
        {
            "account_provisioning_receipt_present": False,
            "activation_operational": False,
            "client_roster_frozen": True,
            "downstream_binding_declared": True,
            "exactly_once_runner_bound": False,
            "handoff_preflight_implemented": True,
            "independent_namespace_trace_qualification_present": False,
            "package_binary_frozen": True,
            "performance_preflight_bound": False,
            "provider_qualified": False,
            "root_installation_receipt_present": False,
            "service_socket_bound": False,
            "supervisor_execution_performed": False,
            "terminal_downstream_receipt_present": False,
        },
        name="activation lifecycle",
    )
    downstream = contract["downstream_binding"]
    expected_downstream = {
        "actual_binding_receipt_present": False,
        "candidate_or_molecular_evidence_allowed": False,
        "qualification_state_write_allowed": False,
        "required_identity_chain": [
            "source_foundation",
            "supervisor_contract",
            "supervisor_source",
            "package_binary",
            "package_sbom",
            "client_roster",
            "preflight_source",
            "performance_profile",
            "runtime_manifest",
            "request_sha256",
            "handoff_packet_sha256",
            "sealed_handoff_receipt_sha256",
            "user_namespace_fd_identity",
            "mount_namespace_fd_identity",
            "terminal_receipt_sha256",
            "qualification_state_transition_sha256",
        ],
        "required_stages": [
            "supervisor_request",
            "kernel_attested_handoff",
            "non_consuming_preflight",
            "terminal_receipt",
            "qualification_state_transition",
        ],
        "result_dependent_binding_allowed": False,
        "schema_id": (
            "betelgeuze.engine_v2_full_pipeline_cpu_supervisor_"
            "downstream_binding/1.0.0"
        ),
        "terminal_must_bind_request_nonce_and_sha256": True,
    }
    if downstream != expected_downstream:
        raise SupervisorActivationContractError("downstream binding drifted")
    external = contract["external_authority"]
    if external != {
        "all_authority_false": True,
        "blockers": EXPECTED_EXTERNAL_BLOCKERS,
        "external_reservation_operational": False,
        "operations_decision_ready": False,
        "unresolved_field_count": 32,
    } or type(external.get("unresolved_field_count")) is not int:
        raise SupervisorActivationContractError("external authority boundary drifted")
    if contract["roster"] != {
        "client_gid": 64042,
        "client_uid": 64042,
        "provisioning_receipt_present": False,
        "roster_path": (
            "config/engine_v2_full_pipeline_cpu_supervisor_activation_v1_roster.json"
        ),
        "roster_sha256": EXPECTED_ROSTER_SHA256,
        "service_gid": 0,
        "service_uid": 0,
    }:
        raise SupervisorActivationContractError("activation roster binding drifted")

    documentation = _read_bytes(documentation_path).decode("utf-8")
    tests = "\n".join(_read_bytes(path).decode("utf-8") for path in test_paths)
    for token in (
        "non-consuming",
        EXPECTED_BINARY_SHA256,
        EXPECTED_PREFLIGHT_SHA256,
        "64042:64042",
        "downstream",
        "does not install",
        "does not launch",
    ):
        if token not in documentation:
            raise SupervisorActivationContractError(f"activation documentation drifted: {token}")
    for token in (
        "test_handoff_verifies_exact_packet_receipt_namespaces_and_peer_pidfd",
        "test_handoff_closes_delivered_descriptors_when_ancillary_overflows",
        "test_terminal_receipt_binds_nonce_and_request",
        "test_package_binary_is_static_rostered_but_still_non_operational",
        "test_supervisor_activation_contract_verifies",
    ):
        if token not in tests:
            raise SupervisorActivationContractError(f"activation regression coverage drifted: {token}")
    _verify_ci_audit(ci_audit_path)
    _verify_workflows(workflow_paths)

    return {
        "activation_id": ACTIVATION_ID,
        "activation_operational": False,
        "all_authority_false": True,
        "contract_sha256": _sha256(contract_raw),
        "external_blockers": EXPECTED_EXTERNAL_BLOCKERS,
        "handoff_preflight_implemented": True,
        "local_blockers": EXPECTED_LOCAL_BLOCKERS,
        "package_binary_sha256": EXPECTED_BINARY_SHA256,
        "package_present": True,
        "performance_measurement_performed": False,
        "qualification_consumed": False,
        "reservation_created": False,
        "roster_frozen": True,
        "schema_id": SCHEMA_ID,
        "status": "verified_packaged_non_consuming_activation_not_operational",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    result = verify(contract_path=arguments.contract)
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
