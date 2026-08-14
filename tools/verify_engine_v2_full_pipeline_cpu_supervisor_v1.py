#!/usr/bin/env python3
"""Verify the reviewable, non-operational full-pipeline CPU supervisor v1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_full_pipeline_cpu_supervisor_v1.json"
)
DEFAULT_SOURCE = (
    REPOSITORY_ROOT
    / "native/tools/engine_v2_full_pipeline_cpu_supervisor_v1.cpp"
)
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_full_pipeline_cpu_supervisor_v1.md"
)
DEFAULT_TEST = (
    REPOSITORY_ROOT
    / "tests/unit/test_verify_engine_v2_full_pipeline_cpu_supervisor_v1.py"
)
DEFAULT_CI_AUDIT = REPOSITORY_ROOT / "tools/audit_engine_v2_ci_authority.py"
DEFAULT_WORKFLOWS = (
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-main.yml",
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml",
    REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml",
)

SCHEMA_ID = "betelgeuze.engine_v2_full_pipeline_cpu_supervisor/1.0.0"
SUPERVISOR_ID = "engine_v2_full_pipeline_cpu_supervisor_v1"
STATUS = "implemented_reviewable_not_installed_not_operational"

EXPECTED_AUTHORITY = {
    "fresh_holdout_execution_authorized": False,
    "github_actions_production_authority": False,
    "hip_device_execution_authorized": False,
    "installation_authorized": False,
    "molecular_execution_authorized": False,
    "product_execution_authorized": False,
    "public_benchmark_authorized": False,
    "qualification_consumption_authorized": False,
    "reservation_authorized": False,
    "runtime_launch_authorized": False,
    "scientific_claim_authorized": False,
    "stage0_admission_authorized": False,
    "test_double_production_authority": False,
}
EXPECTED_BUILD = {
    "binary_identity_frozen": False,
    "compile_only_ci_allowed": True,
    "compiler_flags": [
        "-std=c++17",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        "-static",
        "-s",
        "-Wl,--build-id=none",
    ],
    "packaged_binary_present": False,
    "static_elf_no_dynamic_or_interp_required": True,
}
EXPECTED_FOUNDATION = {
    "activation_contract_sha256": (
        "c9f77a76c0d7687d1c4195f06d50529ce66d915dd1a79f48e9a2827570af9ea2"
    ),
    "foundation_commit_oid": "c15b46e4a93e157826677165642b8788b75f20c7",
    "foundation_commit_sha256": (
        "a8c477a252b12d0306eeb4b70d0159d9de3823fcae285fe697b22d19d237ba93"
    ),
    "foundation_tree_oid": "28361485778537401731d6d085480ae6e613dbc5",
    "foundation_tree_sha256": (
        "e28fb3eabc81cb71bae3c1f0b51ce58642be6164454538c14e39c34b776fee43"
    ),
    "preflight_sha256": (
        "aca96d31bb1ca09d9eb83a10bb7a8a91192fc1405a9eaa8011d94453a28a306e"
    ),
    "profile_sha256": (
        "385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000"
    ),
    "runtime_scope_manifest_sha256": (
        "72b90f500af43c921ce0b8f7d6774c5e99a7e4f3fe366478b3fc33b524b4b404"
    ),
}
EXPECTED_IMPLEMENTATION = {
    "compiled_service_path": (
        "/usr/local/libexec/betelgeuze-engine-v2-full-pipeline-cpu-supervisor-v1"
    ),
    "dynamic_loader_path": "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
    "dynamic_loader_sha256": (
        "8d06f393f4a93bcf9b81145a259524d66a95522a646bf8d7e05b6ffdf2e63dcc"
    ),
    "exact_service_source_present": True,
    "python_executable_path": "/usr/bin/python3.10",
    "python_executable_sha256": (
        "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86"
    ),
    "service_source_path": (
        "native/tools/engine_v2_full_pipeline_cpu_supervisor_v1.cpp"
    ),
    "service_source_sha256": (
        "a7abb3ab52fc01b65b0d6d1cd09e5d807d5f9060c7aca1e1312225040b60c741"
    ),
    "socket_path": (
        "/run/betelgeuze-engine-v2/full-pipeline-cpu-supervisor-v1.sock"
    ),
}
EXPECTED_LIFECYCLE = {
    "activation_contract_bound_to_handoff": False,
    "client_roster_configured": False,
    "exactly_once_runner_bound": False,
    "independent_namespace_attestation_present": False,
    "installation_manifest_present": False,
    "operational": False,
    "preflight_accepts_supervisor_handoff": False,
    "provider_qualified": False,
    "root_service_installed": False,
    "service_socket_bound": False,
    "systemd_provisioning_present": False,
}
EXPECTED_PROTOCOL = {
    "ancillary_descriptor_count": 3,
    "ancillary_descriptor_roles": [
        "exact_preflight_source",
        "artifact_directory",
        "runtime_directory",
    ],
    "handoff_bytes": 464,
    "handoff_descriptor_roles": [
        "sealed_handoff_receipt",
        "initial_user_namespace",
        "initial_mount_namespace",
    ],
    "handoff_magic": "BGV2CPUHANDOF1",
    "maximum_timeout_seconds": 900,
    "nonce_bytes": 32,
    "request_bytes": 192,
    "request_magic": "BGV2CPUSUPREQ1",
    "required_request_digests": [
        "activation_sha256",
        "preflight_sha256",
        "profile_sha256",
        "runtime_manifest_sha256",
    ],
    "socket_domain": "AF_UNIX",
    "socket_type": "SOCK_SEQPACKET",
    "terminal_bytes": 96,
    "terminal_magic": "BGV2CPUTERMV1",
    "version": 1,
}
EXPECTED_RESTRICTIONS = {
    "actual_service_execution_allowed_in_ci": False,
    "caller_supplied_command_allowed": False,
    "caller_supplied_environment_allowed": False,
    "failed_or_consumed_qualification_rerun_allowed": False,
    "hip_execution_allowed": False,
    "molecular_input_allowed": False,
    "performance_measurement_allowed": False,
    "production_socket_creation_allowed": False,
    "qualification_state_write_allowed": False,
    "reservation_allowed": False,
}
EXPECTED_TRUST_BOUNDARY = {
    "child_credential_drop_after_trace_stop": True,
    "close_range_before_untrusted_exec": True,
    "continuous_trace_options": [
        "PTRACE_O_TRACEEXEC",
        "PTRACE_O_EXITKILL",
        "PTRACE_O_TRACEFORK",
        "PTRACE_O_TRACEVFORK",
        "PTRACE_O_TRACECLONE",
    ],
    "exec_descriptor_primitive": "execveat_AT_EMPTY_PATH",
    "expected_initial_mount_namespace_inode": 4_026_531_841,
    "expected_initial_user_namespace_inode": 4_026_531_837,
    "handoff_peer_credential": "SO_PEERCRED_root_service_socketpair",
    "launch_environment_sha256": (
        "5cf4cf74eba4f493ae3f8a88c3459e2f8861146b6e38b5c4d7bd65e958f0da96"
    ),
    "launch_vector_sha256": (
        "3844da69d7b4a1dd61cde9ffa559c7409a6d23b43a80f63dcea612f859a932d3"
    ),
    "mount_independent_namespace_fd_attestation_implemented": True,
    "namespace_descriptor_ioctls": [
        "NS_GET_NSTYPE",
        "NS_GET_OWNER_UID",
        "NS_GET_PARENT",
        "NS_GET_USERNS",
    ],
    "namespace_fd_attestation_independently_qualified": False,
    "peer_pid_pinned_with_pidfd": True,
    "peer_pid_pinned_with_so_peerpidfd": True,
    "peer_pidfd_and_connection_liveness_required_until_terminal": True,
    "preflight_source_snapshot_mode": "0444_sealed_read_only",
    "preflight_source_snapshot_seals": [
        "F_SEAL_SEAL",
        "F_SEAL_SHRINK",
        "F_SEAL_GROW",
        "F_SEAL_WRITE",
    ],
    "procfs_path_evidence_authoritative": False,
    "request_peer_credential": "SO_PEERCRED",
    "second_exec_allowed": False,
    "stdio_rebound_to_root_opened_dev_null": True,
    "supervisor_binary_digest_in_handoff": True,
    "trace_exclusion_across_exec_implemented": True,
    "trace_exclusion_independently_qualified": False,
}


class SupervisorContractError(RuntimeError):
    """The trusted-supervisor source or its non-operational policy drifted."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise SupervisorContractError(f"duplicate JSON key: {key}")
        document[key] = value
    return document


def _reject_float(value: str) -> object:
    raise SupervisorContractError(f"JSON floating point is forbidden: {value}")


def _read_contract(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        document = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SupervisorContractError("supervisor contract is unavailable or invalid") from exc
    if type(document) is not dict:
        raise SupervisorContractError("supervisor contract must be an exact object")
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
        raise SupervisorContractError(
            "supervisor contract is not canonical pretty ASCII JSON"
        )
    return document, raw


def _require_exact(value: object, expected: object, *, label: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise SupervisorContractError(f"{label} changed")


def _require_exact_keys(
    value: object, expected: set[str], *, label: str
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise SupervisorContractError(f"{label} key schema changed")
    return value


def _require_snippets(path: Path, snippets: tuple[str, ...]) -> str:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SupervisorContractError(f"bound source is unavailable: {path}") from exc
    missing = [snippet for snippet in snippets if snippet not in source]
    if missing:
        raise SupervisorContractError(
            f"{path.name} is missing frozen supervisor snippets: {missing}"
        )
    return source


def _require_ordered(source: str, snippets: tuple[str, ...], *, label: str) -> None:
    cursor = -1
    for snippet in snippets:
        observed = source.find(snippet, cursor + 1)
        if observed < 0:
            raise SupervisorContractError(
                f"{label} lost ordered supervisor snippet: {snippet}"
            )
        cursor = observed


def _git_bytes(repository_root: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SupervisorContractError(
            f"required frozen Git object is unavailable: {' '.join(arguments)}"
        ) from exc


def _verify_foundation(repository_root: Path) -> None:
    commit_oid = EXPECTED_FOUNDATION["foundation_commit_oid"]
    observed_commit_oid = _git_bytes(
        repository_root, "rev-parse", "--verify", f"{commit_oid}^{{commit}}"
    ).decode("ascii").strip()
    if observed_commit_oid != commit_oid:
        raise SupervisorContractError("frozen foundation commit OID changed")
    commit_raw = _git_bytes(repository_root, "cat-file", "commit", commit_oid)
    if hashlib.sha256(commit_raw).hexdigest() != EXPECTED_FOUNDATION[
        "foundation_commit_sha256"
    ]:
        raise SupervisorContractError("frozen foundation commit bytes changed")
    tree_oid = _git_bytes(
        repository_root, "rev-parse", f"{commit_oid}^{{tree}}"
    ).decode("ascii").strip()
    if tree_oid != EXPECTED_FOUNDATION["foundation_tree_oid"]:
        raise SupervisorContractError("frozen foundation tree OID changed")
    tree_raw = _git_bytes(
        repository_root, "ls-tree", "-r", "--full-tree", "-z", commit_oid
    )
    if hashlib.sha256(tree_raw).hexdigest() != EXPECTED_FOUNDATION[
        "foundation_tree_sha256"
    ]:
        raise SupervisorContractError("frozen foundation tree bytes changed")


def _verify_source(source_path: Path) -> str:
    try:
        raw = source_path.read_bytes()
    except OSError as exc:
        raise SupervisorContractError("supervisor implementation source is absent") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_IMPLEMENTATION["service_source_sha256"]:
        raise SupervisorContractError("supervisor implementation source digest changed")
    source = _require_snippets(
        source_path,
        (
            "constexpr bool kInstallationAuthorized = false;",
            "constexpr bool kRuntimeLaunchAuthorized = false;",
            "constexpr bool kQualificationConsumptionAuthorized = false;",
            "constexpr uid_t kExpectedClientUid = std::numeric_limits<uid_t>::max();",
            "bool client_identity_is_configured()",
            "!client_identity_is_configured()",
            "static_assert(sizeof(RequestWireV1) == 192);",
            "static_assert(sizeof(HandoffWireV1) == 464);",
            "static_assert(sizeof(TerminalWireV1) == 96);",
            "SO_PEERCRED",
            "SO_PEERPIDFD",
            "MSG_CMSG_CLOEXEC",
            "request peer pidfd is unavailable",
            "request peer pidfd close-on-exec binding failed",
            "SYS_memfd_create",
            "F_SEAL_SEAL | F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_WRITE",
            "source.raw.size(), 0444",
            "NS_GET_NSTYPE",
            "NS_GET_OWNER_UID",
            "NS_GET_PARENT",
            "NS_GET_USERNS",
            "kExpectedInitialUserNamespaceInode = 4026531837",
            "kExpectedInitialMountNamespaceInode = 4026531841",
            "PTRACE_TRACEME",
            "PTRACE_O_TRACEEXEC | PTRACE_O_EXITKILL",
            "trace exclusion could not start before credential drop",
            "SYS_execveat",
            "AT_EMPTY_PATH",
            "kernel-attested supervisor handoff was not delivered exactly once",
            "supervisor_binary_sha256",
            "launch_vector_sha256",
            "launch_environment_sha256",
            "--self-test-primitives",
            "close_range child descriptor boundary",
            "trusted null device identity changed",
            "duplicate_inherited_fd(null_device_fd, STDIN_FILENO)",
            "duplicate_inherited_fd(null_device_fd, STDOUT_FILENO)",
            "duplicate_inherited_fd(null_device_fd, STDERR_FILENO)",
            "__attribute__((used, noinline)) int run_service()",
            "--describe-contract",
            "return 125;",
        ),
    )
    for forbidden in (
        "getenv(",
        "std::getenv",
        "system(",
        "popen(",
        "execvp(",
        "execlp(",
        "unlink(",
    ):
        if forbidden in source:
            raise SupervisorContractError(
                f"supervisor gained caller/environment/path escape: {forbidden}"
            )
    if source.count(kActivation := EXPECTED_FOUNDATION["activation_contract_sha256"]) != 1:
        raise SupervisorContractError(
            f"supervisor must bind activation digest exactly once: {kActivation}"
        )
    if source.count(EXPECTED_FOUNDATION["preflight_sha256"]) != 1:
        raise SupervisorContractError("supervisor preflight digest binding changed")
    _require_ordered(
        source,
        (
            "::ptrace(PTRACE_TRACEME",
            "::raise(SIGSTOP)",
            "::setresgid",
            "::setresuid",
            "::prctl(PR_SET_NO_NEW_PRIVS",
            "::syscall(SYS_execveat",
        ),
        label="credential/trace/exec sequence",
    )
    _require_ordered(
        source,
        (
            'std::string_view(argv[1]) == "--describe-contract"',
            "if (!kInstallationAuthorized || !kRuntimeLaunchAuthorized ||",
            "return 125;",
            "return run_service();",
        ),
        label="non-operational main gate",
    )
    return digest


def _verify_workflows(paths: tuple[Path, ...]) -> None:
    required = (
        "config/engine_v2_full_pipeline_cpu_supervisor_v1.json",
        "native/tools/engine_v2_full_pipeline_cpu_supervisor_v1.cpp",
        "tools/verify_engine_v2_full_pipeline_cpu_supervisor_v1.py",
        "tests/unit/test_verify_engine_v2_full_pipeline_cpu_supervisor_v1.py",
        "docs/engine_v2_full_pipeline_cpu_supervisor_v1.md",
        "Verify full-pipeline CPU supervisor v1",
    )
    for path in paths:
        workflow = _require_snippets(path, required)
        if any(
            forbidden in workflow
            for forbidden in (
                "--serve-supervisor",
                "sudo /tmp/engine-v2-full-pipeline-cpu-supervisor-v1",
                "systemctl start betelgeuze-engine-v2-full-pipeline-cpu-supervisor",
            )
        ):
            raise SupervisorContractError(
                f"{path.name} gained live supervisor execution authority"
            )


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    source_path: Path = DEFAULT_SOURCE,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
    test_path: Path = DEFAULT_TEST,
    ci_audit_path: Path = DEFAULT_CI_AUDIT,
    workflow_paths: tuple[Path, ...] = DEFAULT_WORKFLOWS,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, object]:
    document, raw = _read_contract(contract_path)
    _require_exact_keys(
        document,
        {
            "authority",
            "build",
            "foundation",
            "implementation",
            "lifecycle",
            "protocol",
            "restrictions",
            "schema_id",
            "status",
            "supervisor_id",
            "trust_boundary",
        },
        label="supervisor contract",
    )
    _require_exact(document["schema_id"], SCHEMA_ID, label="schema_id")
    _require_exact(document["supervisor_id"], SUPERVISOR_ID, label="supervisor_id")
    _require_exact(document["status"], STATUS, label="status")
    for key, expected in (
        ("authority", EXPECTED_AUTHORITY),
        ("build", EXPECTED_BUILD),
        ("foundation", EXPECTED_FOUNDATION),
        ("implementation", EXPECTED_IMPLEMENTATION),
        ("lifecycle", EXPECTED_LIFECYCLE),
        ("protocol", EXPECTED_PROTOCOL),
        ("restrictions", EXPECTED_RESTRICTIONS),
        ("trust_boundary", EXPECTED_TRUST_BOUNDARY),
    ):
        _require_exact(document[key], expected, label=key)

    activation_path = (
        repository_root
        / "config/engine_v2_full_pipeline_cpu_performance_v1_activation.json"
    )
    preflight_path = (
        repository_root
        / "tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py"
    )
    if hashlib.sha256(activation_path.read_bytes()).hexdigest() != EXPECTED_FOUNDATION[
        "activation_contract_sha256"
    ]:
        raise SupervisorContractError("predecessor activation contract changed")
    if hashlib.sha256(preflight_path.read_bytes()).hexdigest() != EXPECTED_FOUNDATION[
        "preflight_sha256"
    ]:
        raise SupervisorContractError("predecessor preflight source changed")
    _verify_foundation(repository_root)
    source_sha256 = _verify_source(source_path)
    _verify_workflows(workflow_paths)
    _require_snippets(
        documentation_path,
        (
            "reviewable but non-operational",
            "SO_PEERCRED",
            "SO_PEERPIDFD",
            "PTRACE_O_TRACEEXEC",
            "PTRACE_O_EXITKILL",
            "sealed memfd",
            "`0444`",
            "not an activation receipt",
            "must not be installed",
            "reservation",
            "molecular",
            "HIP",
        ),
    )
    _require_snippets(
        test_path,
        (
            "test_full_pipeline_cpu_supervisor_contract_verifies",
            "test_supervisor_static_binary_is_non_operational",
            "test_supervisor_contract_rejects_authority_drift",
            "test_supervisor_contract_rejects_source_drift",
            "test_supervisor_contract_rejects_duplicate_keys",
        ),
    )
    _require_snippets(
        ci_audit_path,
        (
            "engine_v2_full_pipeline_cpu_supervisor_v1.json",
            "full_pipeline_cpu_supervisor_authority_fail_closed",
            "full_pipeline_cpu_supervisor_in_authoritative_ci",
        ),
    )
    return {
        "schema_id": SCHEMA_ID,
        "supervisor_id": SUPERVISOR_ID,
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "source_sha256": source_sha256,
        "foundation_commit_oid": EXPECTED_FOUNDATION["foundation_commit_oid"],
        "foundation_tree_oid": EXPECTED_FOUNDATION["foundation_tree_oid"],
        "all_authority_false": True,
        "implementation_present": True,
        "installation_authorized": False,
        "runtime_launch_authorized": False,
        "qualification_consumption_authorized": False,
        "provider_qualified": False,
        "operational": False,
        "reservation_created": False,
        "performance_measurement_performed": False,
        "status": "verified_reviewable_non_operational_source",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    arguments = parser.parse_args()
    print(
        json.dumps(
            verify(contract_path=arguments.contract),
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
