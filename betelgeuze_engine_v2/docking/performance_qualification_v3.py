"""Sealed synthetic CPU geometric-kernel qualification for profile v3."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import secrets
import stat
import sys
import threading
import time
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence
import weakref

from betelgeuze_engine_v2.docking import performance_sidecar as v2
from betelgeuze_engine_v2.docking.performance_host_preflight_v3 import (
    HOST_PREFLIGHT_SCHEMA_ID,
    HostPreflightEvidenceV3,
    derive_host_preflight_evidence_v3,
)


PROFILE_ID: Final = "engine_v2_ryzen_5900x_geometric_kernel_synthetic_v3"
PROFILE_SHA256: Final = (
    "21facfc62956b402d4a43e5b68389083bacaa3d3afd753eb6b1da3578c8bb6b3"
)
PROFILE_SCHEMA_ID: Final = "betelgeuze.engine_v2_cpu_performance_profile/3.0.0"
ARTIFACT_SCHEMA_ID: Final = "betelgeuze.engine_v2_cpu_performance_artifact/3.0.0"
SOURCE_BINDINGS_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_cpu_performance_source_bindings/3.0.0"
)
CANONICAL_PROFILE_RELATIVE_PATH: Final = Path(
    "config/engine_v2_cpu_performance_profile_v3.json"
)
PREDECESSOR_PROFILE_RELATIVE_PATH: Final = Path(
    "config/engine_v2_cpu_performance_profile.json"
)
PREDECESSOR_TERMINAL_RELATIVE_PATH: Final = Path(
    "config/engine_v2_cpu_performance_v2_terminal_decision.json"
)
ACTIVATION_RELATIVE_PATH: Final = Path(
    "config/engine_v2_cpu_performance_v3_runner_activation.json"
)
RUNNER_TOOL_RELATIVE_PATH: Final = Path(
    "tools/run_engine_v2_cpu_performance_qualification_v3.py"
)
PROFILE_VERIFIER_RELATIVE_PATH: Final = Path(
    "tools/verify_engine_v2_cpu_performance_profile_v3.py"
)
PREDECESSOR_PROFILE_SHA256: Final = (
    "1d6d3da4dc1d3d0a2734cd2a19ee45409e105fe67c3bc6518b3df566d86b7560"
)
PREDECESSOR_TERMINAL_SHA256: Final = (
    "047f157c8d5d3228c180aca6af392eb8cf13d828659b9a83c38c74c34cc0cf0f"
)
MAX_ARTIFACT_BYTES: Final = 32 * 1024 * 1024
MAX_STATE_BYTES: Final = 64 * 1024
STATE_DIRECTORY_RELATIVE_PATH: Final = (
    Path(".betelgeuze-engine-v2") / "qualification" / PROFILE_SHA256
)
ATTEMPT_LEDGER_FILENAME: Final = "attempt.json"
TERMINAL_STATE_FILENAME: Final = "terminal.json"
ATTEMPT_LEDGER_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_cpu_performance_attempt_ledger/3.0.0"
)
TERMINAL_STATE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_cpu_performance_terminal_state/3.0.0"
)


class CPUPerformanceQualificationV3Error(ValueError):
    """A fail-closed profile-v3 qualification error."""


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_json(value: object) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _read_exact_source(path: Path, *, name: str, maximum_bytes: int) -> bytes:
    try:
        return v2._read_owner_controlled_regular_file(
            path,
            name=name,
            maximum_bytes=maximum_bytes,
        )
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc


def _account_home_directory() -> Path:
    """Return the login-account home without trusting caller environment state."""

    try:
        home = Path(pwd.getpwuid(os.geteuid()).pw_dir).absolute()
        resolved = home.resolve(strict=True)
        metadata = home.lstat()
    except (KeyError, OSError) as exc:
        raise CPUPerformanceQualificationV3Error(
            "qualification account home is unavailable"
        ) from exc
    if (
        home != resolved
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise CPUPerformanceQualificationV3Error(
            "qualification account home is not owner-controlled"
        )
    return resolved


def _open_state_directory() -> tuple[Path, int]:
    """Create/open the fixed account-scoped state directory descriptor-first."""

    home = _account_home_directory()
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(home, directory_flags)
    except OSError as exc:
        raise CPUPerformanceQualificationV3Error(
            "qualification account home cannot be opened safely"
        ) from exc
    current = home
    try:
        for component in STATE_DIRECTORY_RELATIVE_PATH.parts:
            if (
                not component
                or component in (".", "..")
                or "/" in component
                or "\x00" in component
            ):
                raise CPUPerformanceQualificationV3Error(
                    "qualification state path is invalid"
                )
            created = False
            try:
                os.mkdir(component, 0o700, dir_fd=descriptor)
                created = True
            except FileExistsError:
                pass
            except OSError as exc:
                raise CPUPerformanceQualificationV3Error(
                    "qualification state directory cannot be created safely"
                ) from exc
            if created:
                try:
                    os.fsync(descriptor)
                except OSError as exc:
                    raise CPUPerformanceQualificationV3Error(
                        "qualification state directory creation is not durable"
                    ) from exc
            try:
                child = os.open(component, directory_flags, dir_fd=descriptor)
            except OSError as exc:
                raise CPUPerformanceQualificationV3Error(
                    "qualification state directory cannot be opened safely"
                ) from exc
            metadata = os.fstat(child)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            ):
                os.close(child)
                raise CPUPerformanceQualificationV3Error(
                    "qualification state directory is not owner-controlled"
                )
            os.close(descriptor)
            descriptor = child
            current /= component
        _require_state_directory_binding(current, descriptor)
        return current, descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _require_state_directory_binding(path: Path, descriptor: int) -> None:
    try:
        path_metadata = os.stat(path, follow_symlinks=False)
        descriptor_metadata = os.fstat(descriptor)
    except OSError as exc:
        raise CPUPerformanceQualificationV3Error(
            "qualification state directory identity is unavailable"
        ) from exc
    if (
        (path_metadata.st_dev, path_metadata.st_ino)
        != (descriptor_metadata.st_dev, descriptor_metadata.st_ino)
        or not stat.S_ISDIR(descriptor_metadata.st_mode)
        or descriptor_metadata.st_uid != os.geteuid()
        or descriptor_metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise CPUPerformanceQualificationV3Error(
            "qualification state directory identity changed"
        )


def _load_profiles() -> tuple[Mapping[str, Any], v2.CPUPerformanceProfileV2]:
    root = _repository_root()
    profile_v3_raw = _read_exact_source(
        root / CANONICAL_PROFILE_RELATIVE_PATH,
        name="CPU performance profile v3",
        maximum_bytes=64 * 1024,
    )
    if _sha256_bytes(profile_v3_raw) != PROFILE_SHA256:
        raise CPUPerformanceQualificationV3Error("profile_v3_identity_changed")
    try:
        profile_v3 = json.loads(profile_v3_raw.decode("ascii"))
    except (UnicodeError, ValueError) as exc:
        raise CPUPerformanceQualificationV3Error("profile_v3_invalid") from exc
    if (
        type(profile_v3) is not dict
        or profile_v3.get("schema_id") != PROFILE_SCHEMA_ID
        or profile_v3.get("profile_id") != PROFILE_ID
        or profile_v3.get("authority") != dict(v2.AUTHORITY_FALSE)
        or profile_v3.get("restrictions") != dict(v2.RESTRICTIONS)
    ):
        raise CPUPerformanceQualificationV3Error("profile_v3_contract_changed")
    terminal_raw = _read_exact_source(
        root / PREDECESSOR_TERMINAL_RELATIVE_PATH,
        name="CPU performance v2 terminal decision",
        maximum_bytes=64 * 1024,
    )
    if _sha256_bytes(terminal_raw) != PREDECESSOR_TERMINAL_SHA256:
        raise CPUPerformanceQualificationV3Error("predecessor_terminal_changed")
    try:
        predecessor = v2.load_cpu_performance_profile(
            root / PREDECESSOR_PROFILE_RELATIVE_PATH
        )
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    if predecessor.profile_sha256 != PREDECESSOR_PROFILE_SHA256:
        raise CPUPerformanceQualificationV3Error("predecessor_profile_changed")
    return MappingProxyType(profile_v3), predecessor


def _load_canonical_indented_json(raw: bytes, *, name: str) -> Mapping[str, Any]:
    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        observed: dict[str, object] = {}
        for key, value in pairs:
            if key in observed:
                raise ValueError(f"duplicate JSON key: {key}")
            observed[key] = value
        return observed

    def reject_float(value: str) -> object:
        raise ValueError(f"JSON float is forbidden: {value}")

    try:
        if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
            raise ValueError("exactly one trailing newline is required")
        document = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except (UnicodeError, ValueError) as exc:
        raise CPUPerformanceQualificationV3Error(f"{name} is invalid") from exc
    if type(document) is not dict:
        raise CPUPerformanceQualificationV3Error(f"{name} must be an object")
    expected = (
        json.dumps(
            document,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )
    if raw != expected:
        raise CPUPerformanceQualificationV3Error(
            f"{name} must use canonical indented JSON"
        )
    return document


def verify_runner_activation_contract() -> Mapping[str, object]:
    """Verify exact-source activation without executing a measurement."""

    root = _repository_root()
    activation_raw = _read_exact_source(
        root / ACTIVATION_RELATIVE_PATH,
        name="CPU performance v3 runner activation",
        maximum_bytes=64 * 1024,
    )
    activation = _load_canonical_indented_json(
        activation_raw, name="CPU performance v3 runner activation"
    )
    activation = _require_exact_keys(
        activation,
        name="runner activation",
        keys=(
            "schema_id",
            "status",
            "profile_id",
            "profile_sha256",
            "predecessor_terminal_sha256",
            "authority",
            "restrictions",
            "runner",
            "source_bindings",
        ),
    )
    runner = _require_exact_keys(
        activation["runner"],
        name="runner activation policy",
        keys=(
            "attempt_ledger_policy",
            "caller_supplied_probe_allowed",
            "decision_return_policy",
            "exactly_once_profile_attempt",
            "execution_state_recorded_only_by_terminal_decision",
            "github_actions_live_execution_allowed",
            "isolated_live_entrypoint_required",
            "live_synthetic_local_execution_implemented",
            "molecular_execution_allowed",
            "output_policy",
            "reservation_created",
            "result_dependent_configuration_allowed",
            "terminal_state_policy",
            "test_double_execution_authority",
        ),
    )
    if (
        activation["schema_id"]
        != "betelgeuze.engine_v2_cpu_performance_runner_activation/3.0.0"
        or activation["status"]
        != "implementation_admitted_execution_not_attested"
        or activation["profile_id"] != PROFILE_ID
        or activation["profile_sha256"] != PROFILE_SHA256
        or activation["predecessor_terminal_sha256"]
        != PREDECESSOR_TERMINAL_SHA256
        or activation["authority"] != dict(v2.AUTHORITY_FALSE)
        or activation["restrictions"] != dict(v2.RESTRICTIONS)
        or runner
        != {
            "attempt_ledger_policy": (
                "fixed_account_scoped_profile_sha_o_excl_before_preflight"
            ),
            "caller_supplied_probe_allowed": False,
            "decision_return_policy": (
                "artifact_and_terminal_persisted_before_return"
            ),
            "exactly_once_profile_attempt": True,
            "execution_state_recorded_only_by_terminal_decision": True,
            "github_actions_live_execution_allowed": False,
            "isolated_live_entrypoint_required": True,
            "live_synthetic_local_execution_implemented": True,
            "molecular_execution_allowed": False,
            "output_policy": (
                "owner_only_absent_only_single_artifact_plus_terminal"
            ),
            "reservation_created": False,
            "result_dependent_configuration_allowed": False,
            "terminal_state_policy": (
                "owner_only_absent_only_attempt_and_artifact_bound"
            ),
            "test_double_execution_authority": False,
        }
    ):
        raise CPUPerformanceQualificationV3Error(
            "runner activation authority or identity changed"
        )
    source_paths = {
        "host_preflight_source_sha256": (
            root
            / "betelgeuze_engine_v2/docking/performance_host_preflight_v3.py"
        ),
        "measurement_core_source_sha256": Path(v2.__file__).resolve(),
        "profile_v3_sha256": root / CANONICAL_PROFILE_RELATIVE_PATH,
        "profile_v3_verifier_sha256": root / PROFILE_VERIFIER_RELATIVE_PATH,
        "qualification_v3_source_sha256": Path(__file__).resolve(),
        "runner_tool_sha256": root / RUNNER_TOOL_RELATIVE_PATH,
        "terminal_v2_sha256": root / PREDECESSOR_TERMINAL_RELATIVE_PATH,
    }
    expected_source_bindings = {
        name: _sha256_bytes(
            _read_exact_source(path, name=name, maximum_bytes=4 * 1024 * 1024)
        )
        for name, path in source_paths.items()
    }
    if activation["source_bindings"] != expected_source_bindings:
        raise CPUPerformanceQualificationV3Error(
            "runner activation source bindings changed"
        )
    return MappingProxyType(
        {
            "activation_sha256": _sha256_bytes(activation_raw),
            "authority": dict(v2.AUTHORITY_FALSE),
            "github_actions_live_execution_allowed": False,
            "live_run_capability": True,
            "molecular_execution": False,
            "profile_id": PROFILE_ID,
            "profile_sha256": PROFILE_SHA256,
            "runner_activation_verified": True,
        }
    )


def _host_v2_projection(host: HostPreflightEvidenceV3) -> dict[str, object]:
    return {
        "cpu_model": host.cpu_model,
        "boost_disabled": (
            host.boost_state is not None and not host.boost_state.boost_enabled
        ),
        "available_cpu_affinity": list(host.available_cpu_affinity),
        "platform_system": host.platform_system,
        "platform_machine": host.platform_machine,
        "byteorder": host.byteorder,
        "parent_pid": host.parent_pid,
        "parent_os_task_count": host.parent_os_task_count,
        "qualified": host.qualified,
        "blockers": list(host.blockers),
    }


def _derive_orchestration_source_bindings() -> Mapping[str, object]:
    root = _repository_root()
    verify_runner_activation_contract()
    paths = {
        "activation_sha256": root / ACTIVATION_RELATIVE_PATH,
        "host_preflight_source_sha256": (
            root
            / "betelgeuze_engine_v2/docking/performance_host_preflight_v3.py"
        ),
        "profile_v3_sha256": root / CANONICAL_PROFILE_RELATIVE_PATH,
        "profile_v3_verifier_sha256": root / PROFILE_VERIFIER_RELATIVE_PATH,
        "qualification_v3_source_sha256": Path(__file__).resolve(),
        "runner_tool_sha256": root / RUNNER_TOOL_RELATIVE_PATH,
        "terminal_v2_sha256": root / PREDECESSOR_TERMINAL_RELATIVE_PATH,
    }
    hashes = {
        name: _sha256_bytes(
            _read_exact_source(path, name=name, maximum_bytes=4 * 1024 * 1024)
        )
        for name, path in paths.items()
    }
    if hashes["profile_v3_sha256"] != PROFILE_SHA256:
        raise CPUPerformanceQualificationV3Error("profile_v3_source_binding_changed")
    if hashes["terminal_v2_sha256"] != PREDECESSOR_TERMINAL_SHA256:
        raise CPUPerformanceQualificationV3Error("terminal_v2_source_binding_changed")
    return MappingProxyType(
        {
            "schema_id": SOURCE_BINDINGS_SCHEMA_ID,
            **hashes,
        }
    )


def _source_bindings(*, complete: bool) -> dict[str, object]:
    if not complete:
        return {"measurement_core": {}, "orchestration": {}}
    try:
        core = v2._derive_source_bindings()
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    return {
        "measurement_core": dict(core),
        "orchestration": dict(_derive_orchestration_source_bindings()),
    }


def _artifact_projection(
    *,
    predecessor: v2.CPUPerformanceProfileV2,
    run_nonce: str,
    host: HostPreflightEvidenceV3,
    source_bindings: Mapping[str, object],
    transcript: Sequence[Mapping[str, Any]],
    fixture_results: Sequence[Mapping[str, object]],
    status: str,
    recorded_decision: str,
    recorded_numeric_gate_passed: bool | None,
    blockers: Sequence[str],
) -> dict[str, object]:
    return {
        "schema_id": ARTIFACT_SCHEMA_ID,
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "predecessor_profile_id": v2.PROFILE_ID,
        "predecessor_profile_sha256": PREDECESSOR_PROFILE_SHA256,
        "status": status,
        "run_nonce": run_nonce,
        "host": host.to_dict(),
        "source_bindings": dict(source_bindings),
        "fixture_inputs": v2._fixture_input_rows(predecessor),
        "measurement_contract": v2._measurement_contract(predecessor, transcript),
        "transcript": [dict(row) for row in transcript],
        "fixture_results": [dict(row) for row in fixture_results],
        "recorded_decision": recorded_decision,
        "recorded_numeric_gate_passed": recorded_numeric_gate_passed,
        "blockers": list(blockers),
        "numeric_contract_changed": False,
        "offline_replay_only": True,
        "offline_artifact_gate_eligible": False,
        "live_run_capability_serialized": False,
        "qualification_authority": False,
        "authority": dict(v2.AUTHORITY_FALSE),
        "restrictions": dict(v2.RESTRICTIONS),
    }


def _seal_artifact(projection: Mapping[str, object]) -> dict[str, object]:
    return {**projection, "receipt_sha256": _sha256_json(projection)}


_ARTIFACT_KEYS: Final = frozenset(
    {
        "schema_id",
        "profile_id",
        "profile_sha256",
        "predecessor_profile_id",
        "predecessor_profile_sha256",
        "status",
        "run_nonce",
        "host",
        "source_bindings",
        "fixture_inputs",
        "measurement_contract",
        "transcript",
        "fixture_results",
        "recorded_decision",
        "recorded_numeric_gate_passed",
        "blockers",
        "numeric_contract_changed",
        "offline_replay_only",
        "offline_artifact_gate_eligible",
        "live_run_capability_serialized",
        "qualification_authority",
        "authority",
        "restrictions",
        "receipt_sha256",
    }
)


def _require_exact_keys(
    value: object,
    *,
    name: str,
    keys: Sequence[str] | frozenset[str],
) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != set(keys):
        raise CPUPerformanceQualificationV3Error(f"{name} keys changed")
    return value


def _require_digest(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CPUPerformanceQualificationV3Error(f"{name} is not a SHA-256 digest")
    return value


def _validate_host_document(value: object, *, complete: bool) -> Mapping[str, Any]:
    host = _require_exact_keys(
        value,
        name="host",
        keys=(
            "schema_id",
            "cpu_model",
            "boost_state",
            "available_cpu_affinity",
            "platform_system",
            "platform_machine",
            "byteorder",
            "parent_pid",
            "parent_os_task_count",
            "qualified",
            "blockers",
            "consumes_qualification",
            "launches_measurements",
            "molecular_execution",
        ),
    )
    if host["schema_id"] != HOST_PREFLIGHT_SCHEMA_ID:
        raise CPUPerformanceQualificationV3Error("host schema changed")
    if (
        host["consumes_qualification"] is not False
        or host["launches_measurements"] is not False
        or host["molecular_execution"] is not False
    ):
        raise CPUPerformanceQualificationV3Error("host preflight authority changed")
    affinity = host["available_cpu_affinity"]
    blockers = host["blockers"]
    if (
        type(host["cpu_model"]) is not str
        or type(affinity) is not list
        or affinity != sorted(set(affinity))
        or any(type(cpu) is not int or not 0 <= cpu <= 1_048_575 for cpu in affinity)
        or type(blockers) is not list
        or len(blockers) != len(set(blockers))
        or any(type(blocker) is not str or not blocker for blocker in blockers)
        or type(host["qualified"]) is not bool
        or host["qualified"] != (not blockers)
        or type(host["parent_pid"]) is not int
        or host["parent_pid"] < 1
        or type(host["parent_os_task_count"]) is not int
        or not 1 <= host["parent_os_task_count"] <= 1024
    ):
        raise CPUPerformanceQualificationV3Error("host preflight fields are invalid")
    boost = host["boost_state"]
    if boost is not None:
        boost = _require_exact_keys(
            boost,
            name="boost_state",
            keys=(
                "path",
                "reader_id",
                "raw_byte_count",
                "raw_sha256",
                "reported_size_before",
                "reported_size_descriptor_before",
                "reported_size_descriptor_after",
                "reported_size_after",
                "stable_read_count",
                "boost_enabled",
            ),
        )
        accepted = {
            hashlib.sha256(raw).hexdigest(): (len(raw), raw.strip() == b"1")
            for raw in (b"0", b"0\n", b"1", b"1\n")
        }
        raw_sha = _require_digest(boost["raw_sha256"], name="boost raw SHA-256")
        if (
            boost["path"] != "/sys/devices/system/cpu/cpufreq/boost"
            or boost["reader_id"] != "betelgeuze.linux_sysfs_boolean_reader/1.0.0"
            or raw_sha not in accepted
            or type(boost["raw_byte_count"]) is not int
            or type(boost["boost_enabled"]) is not bool
            or (boost["raw_byte_count"], boost["boost_enabled"])
            != accepted[raw_sha]
            or boost["stable_read_count"] != 2
            or any(
                type(boost[name]) is not int or not 0 <= boost[name] <= 1 << 40
                for name in (
                    "reported_size_before",
                    "reported_size_descriptor_before",
                    "reported_size_descriptor_after",
                    "reported_size_after",
                )
            )
        ):
            raise CPUPerformanceQualificationV3Error("boost-state evidence is invalid")
    host_v2 = {
        "cpu_model": host["cpu_model"],
        "boost_disabled": boost is not None and boost["boost_enabled"] is False,
        "available_cpu_affinity": affinity,
        "platform_system": host["platform_system"],
        "platform_machine": host["platform_machine"],
        "byteorder": host["byteorder"],
        "parent_pid": host["parent_pid"],
        "parent_os_task_count": host["parent_os_task_count"],
        "qualified": host["qualified"],
        "blockers": blockers,
    }
    try:
        v2._verify_host_projection(host_v2, complete=complete)
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    return host


def _verify_orchestration_bindings(value: object, *, complete: bool) -> None:
    if not complete:
        if value != {}:
            raise CPUPerformanceQualificationV3Error(
                "blocked artifact orchestration bindings must be empty"
            )
        return
    bindings = _require_exact_keys(
        value,
        name="orchestration source bindings",
        keys=(
            "schema_id",
            "activation_sha256",
            "host_preflight_source_sha256",
            "profile_v3_sha256",
            "profile_v3_verifier_sha256",
            "qualification_v3_source_sha256",
            "runner_tool_sha256",
            "terminal_v2_sha256",
        ),
    )
    if bindings["schema_id"] != SOURCE_BINDINGS_SCHEMA_ID:
        raise CPUPerformanceQualificationV3Error(
            "orchestration source-binding schema changed"
        )
    expected = _derive_orchestration_source_bindings()
    if dict(bindings) != dict(expected):
        raise CPUPerformanceQualificationV3Error(
            "orchestration source bindings changed"
        )


@dataclass(frozen=True, slots=True)
class VerifiedOfflineCPUPerformanceArtifactV3:
    _document_bytes: bytes = field(repr=False)
    recorded_numeric_gate_passed: bool | None
    recorded_decision: str
    verification_blockers: tuple[str, ...]
    live_run_capability: bool = False
    local_numeric_gate_eligible: bool = False
    offline_replay_only: bool = True
    qualification_authority: bool = False
    structural_integrity_verified: bool = True
    execution_attested: bool = False

    @property
    def document(self) -> dict[str, Any]:
        return json.loads(self._document_bytes.decode("ascii"))


def require_cpu_performance_artifact_v3_document(
    document: Mapping[str, Any],
) -> VerifiedOfflineCPUPerformanceArtifactV3:
    """Reverify the v3 artifact without inspecting the current host."""

    _profile_v3, predecessor = _load_profiles()
    artifact = _require_exact_keys(
        document, name="CPU performance artifact v3", keys=_ARTIFACT_KEYS
    )
    if (
        artifact["schema_id"] != ARTIFACT_SCHEMA_ID
        or artifact["profile_id"] != PROFILE_ID
        or artifact["profile_sha256"] != PROFILE_SHA256
        or artifact["predecessor_profile_id"] != v2.PROFILE_ID
        or artifact["predecessor_profile_sha256"] != PREDECESSOR_PROFILE_SHA256
        or artifact["authority"] != dict(v2.AUTHORITY_FALSE)
        or artifact["restrictions"] != dict(v2.RESTRICTIONS)
        or artifact["numeric_contract_changed"] is not False
        or artifact["offline_replay_only"] is not True
        or artifact["offline_artifact_gate_eligible"] is not False
        or artifact["live_run_capability_serialized"] is not False
        or artifact["qualification_authority"] is not False
    ):
        raise CPUPerformanceQualificationV3Error("artifact v3 authority changed")
    _require_digest(artifact["run_nonce"], name="run_nonce")
    receipt = _require_digest(artifact["receipt_sha256"], name="receipt_sha256")
    projection = {
        key: value for key, value in artifact.items() if key != "receipt_sha256"
    }
    if _sha256_json(projection) != receipt:
        raise CPUPerformanceQualificationV3Error("artifact v3 receipt changed")
    status = artifact["status"]
    if status not in ("complete", "blocked_preflight"):
        raise CPUPerformanceQualificationV3Error("artifact v3 status is invalid")
    complete = status == "complete"
    host = _validate_host_document(artifact["host"], complete=complete)
    bindings = _require_exact_keys(
        artifact["source_bindings"],
        name="source_bindings",
        keys=("measurement_core", "orchestration"),
    )
    try:
        core_bindings = v2._verify_source_bindings(
            bindings["measurement_core"], complete=complete
        )
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    _verify_orchestration_bindings(bindings["orchestration"], complete=complete)
    try:
        v2._verify_fixture_input_rows(artifact["fixture_inputs"], predecessor)
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    if complete:
        try:
            transcript = v2._validate_transcript_rows(
                artifact["transcript"],
                profile=predecessor,
                run_nonce=str(artifact["run_nonce"]),
                parent_pid=int(host["parent_pid"]),
                source_bindings=core_bindings,
            )
            numeric_passed, blockers = v2._verify_fixture_results(
                artifact["fixture_results"],
                transcript=transcript,
                profile=predecessor,
            )
            v2._verify_measurement_contract(
                artifact["measurement_contract"],
                profile=predecessor,
                transcript=transcript,
            )
        except v2.CPUPerformanceError as exc:
            raise CPUPerformanceQualificationV3Error(str(exc)) from exc
        if (
            type(artifact["recorded_numeric_gate_passed"]) is not bool
            or artifact["recorded_numeric_gate_passed"] is not numeric_passed
            or artifact["recorded_decision"] != ("GO" if numeric_passed else "NO_GO")
            or artifact["blockers"] != list(blockers)
        ):
            raise CPUPerformanceQualificationV3Error(
                "artifact v3 numerical decision does not rederive"
            )
        recorded_numeric: bool | None = numeric_passed
    else:
        if (
            artifact["transcript"] != []
            or artifact["fixture_results"] != []
            or artifact["recorded_numeric_gate_passed"] is not None
            or artifact["recorded_decision"] != "BLOCKED"
            or type(artifact["blockers"]) is not list
            or not artifact["blockers"]
            or any(
                type(blocker) is not str or not blocker
                for blocker in artifact["blockers"]
            )
        ):
            raise CPUPerformanceQualificationV3Error(
                "blocked artifact v3 fields are invalid"
            )
        try:
            v2._verify_measurement_contract(
                artifact["measurement_contract"],
                profile=predecessor,
                transcript=(),
            )
        except v2.CPUPerformanceError as exc:
            raise CPUPerformanceQualificationV3Error(str(exc)) from exc
        recorded_numeric = None
    return VerifiedOfflineCPUPerformanceArtifactV3(
        _document_bytes=_canonical_json_bytes(dict(artifact)),
        recorded_numeric_gate_passed=recorded_numeric,
        recorded_decision=str(artifact["recorded_decision"]),
        verification_blockers=("offline_artifact_cannot_attest_execution",),
    )


def require_cpu_performance_artifact_v3_bytes(
    raw: bytes,
) -> VerifiedOfflineCPUPerformanceArtifactV3:
    try:
        document = v2.require_canonical_json_object_bytes(
            raw,
            name="CPU performance artifact v3",
            maximum_bytes=MAX_ARTIFACT_BYTES,
            trailing_newline_required=True,
        )
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    return require_cpu_performance_artifact_v3_document(document)


def read_cpu_performance_artifact_v3(
    path: Path,
) -> VerifiedOfflineCPUPerformanceArtifactV3:
    """Read one bounded owner-only artifact without following path symlinks."""

    target = Path(path)
    try:
        parent, _parent_metadata = v2._reject_symlink_parent(target)
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    bound_target = parent / target.name
    try:
        metadata = bound_target.lstat()
    except OSError as exc:
        raise CPUPerformanceQualificationV3Error(
            "CPU performance artifact v3 is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.geteuid()
        or metadata.st_nlink != 1
    ):
        raise CPUPerformanceQualificationV3Error(
            "CPU performance artifact v3 is not an owner-only single-link file"
        )
    raw = _read_exact_source(
        bound_target,
        name="CPU performance artifact v3",
        maximum_bytes=MAX_ARTIFACT_BYTES,
    )
    return require_cpu_performance_artifact_v3_bytes(raw)


def _validated_absent_artifact_target(path: Path) -> Path:
    target = Path(path)
    if (
        not target.name
        or target.name in (".", "..")
        or target.suffix != ".json"
        or len(os.fsencode(target.name)) > 240
        or len(os.fsencode(target)) > 4096
    ):
        raise CPUPerformanceQualificationV3Error("artifact output filename is invalid")
    try:
        parent, parent_metadata = v2._reject_symlink_parent(target)
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_fd = os.open(parent, directory_flags)
    except OSError as exc:
        raise CPUPerformanceQualificationV3Error(
            "artifact parent cannot be opened safely"
        ) from exc
    try:
        try:
            v2._require_same_trusted_parent(parent, directory_fd, parent_metadata)
        except v2.CPUPerformanceError as exc:
            raise CPUPerformanceQualificationV3Error(str(exc)) from exc
        try:
            os.stat(target.name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise CPUPerformanceQualificationV3Error(
                "artifact output state is ambiguous"
            ) from exc
        else:
            raise CPUPerformanceQualificationV3Error(
                "artifact output already exists"
            )
    finally:
        os.close(directory_fd)
    return parent / target.name


def _output_path_sha256(path: Path) -> str:
    return _sha256_bytes(os.fsencode(str(path)))


def _write_all(descriptor: int, raw: bytes, *, name: str) -> None:
    offset = 0
    while offset < len(raw):
        try:
            written = os.write(descriptor, raw[offset:])
        except OSError as exc:
            raise CPUPerformanceQualificationV3Error(
                f"{name} write failed"
            ) from exc
        if written <= 0:
            raise CPUPerformanceQualificationV3Error(
                f"{name} write made no progress"
            )
        offset += written


class _ReservedProfileAttemptV3:
    """Opaque lease backed by the durable attempt marker."""

    __slots__ = (
        "_activation_sha256",
        "_attempt_receipt_sha256",
        "_issued_pid",
        "_issued_start_ticks",
        "_output_path_sha256",
        "_raw_sha256",
        "_run_nonce",
        "__weakref__",
    )

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CPUPerformanceQualificationV3Error(
            "reserved profile attempts cannot be caller-constructed"
        )

    def __setattr__(self, _name: str, _value: object) -> None:
        raise CPUPerformanceQualificationV3Error(
            "reserved profile attempts are immutable"
        )


@dataclass(slots=True)
class _AttemptRegistryEntryV3:
    raw_sha256: str
    pid: int
    process_start_ticks: int
    state: str


def _build_attempt_registry() -> tuple[Any, Any]:
    issued: weakref.WeakKeyDictionary[
        _ReservedProfileAttemptV3, _AttemptRegistryEntryV3
    ] = weakref.WeakKeyDictionary()
    lock = threading.Lock()

    def issue(
        *,
        raw_sha256: str,
        activation_sha256: str,
        attempt_receipt_sha256: str,
        output_path_sha256: str,
        run_nonce: str,
        process_start_ticks: int,
    ) -> _ReservedProfileAttemptV3:
        attempt = object.__new__(_ReservedProfileAttemptV3)
        object.__setattr__(attempt, "_activation_sha256", activation_sha256)
        object.__setattr__(
            attempt, "_attempt_receipt_sha256", attempt_receipt_sha256
        )
        object.__setattr__(attempt, "_issued_pid", os.getpid())
        object.__setattr__(attempt, "_issued_start_ticks", process_start_ticks)
        object.__setattr__(attempt, "_output_path_sha256", output_path_sha256)
        object.__setattr__(attempt, "_raw_sha256", raw_sha256)
        object.__setattr__(attempt, "_run_nonce", run_nonce)
        with lock:
            issued[attempt] = _AttemptRegistryEntryV3(
                raw_sha256=raw_sha256,
                pid=os.getpid(),
                process_start_ticks=process_start_ticks,
                state="reserved",
            )
        return attempt

    def begin(attempt: object) -> _ReservedProfileAttemptV3:
        if not isinstance(attempt, _ReservedProfileAttemptV3):
            raise CPUPerformanceQualificationV3Error(
                "live v3 execution requires a durable attempt lease"
            )
        with lock:
            try:
                entry = issued.get(attempt)
                valid = bool(
                    entry is not None
                    and entry.state == "reserved"
                    and attempt._raw_sha256 == entry.raw_sha256
                    and attempt._issued_pid == entry.pid == os.getpid()
                    and attempt._issued_start_ticks == entry.process_start_ticks
                    and v2._process_start_ticks(os.getpid())
                    == entry.process_start_ticks
                )
            except (AttributeError, TypeError, v2.CPUPerformanceError):
                valid = False
            if not valid or entry is None:
                raise CPUPerformanceQualificationV3Error(
                    "durable attempt lease is invalid or already consumed"
                )
            entry.state = "executing"
        return attempt

    return issue, begin


_issue_reserved_attempt, _begin_reserved_attempt = _build_attempt_registry()


def _reserve_profile_attempt_v3(
    *,
    state_directory_fd: int,
    activation_sha256: str,
    output_path_sha256: str,
) -> _ReservedProfileAttemptV3:
    """Atomically burn the one profile attempt before any host measurement."""

    for name in (ATTEMPT_LEDGER_FILENAME, TERMINAL_STATE_FILENAME):
        try:
            os.stat(name, dir_fd=state_directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise CPUPerformanceQualificationV3Error(
                "qualification state is ambiguous"
            ) from exc
        if name == ATTEMPT_LEDGER_FILENAME:
            raise CPUPerformanceQualificationV3Error(
                "exactly-once profile attempt was already consumed"
            )
        raise CPUPerformanceQualificationV3Error(
            "terminal state exists without an available profile attempt"
        )

    run_nonce = secrets.token_hex(32)
    process_start_ticks = v2._process_start_ticks(os.getpid())
    projection: dict[str, object] = {
        "schema_id": ATTEMPT_LEDGER_SCHEMA_ID,
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "activation_sha256": activation_sha256,
        "run_nonce": run_nonce,
        "output_path_sha256": output_path_sha256,
        "process_id": os.getpid(),
        "process_start_ticks": process_start_ticks,
        "attempt_ordinal": 1,
        "measurement_started": False,
        "authority": dict(v2.AUTHORITY_FALSE),
        "restrictions": dict(v2.RESTRICTIONS),
    }
    document = {**projection, "receipt_sha256": _sha256_json(projection)}
    raw = _canonical_json_bytes(document) + b"\n"
    if len(raw) > MAX_STATE_BYTES:
        raise CPUPerformanceQualificationV3Error("attempt ledger exceeds byte limit")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(
            ATTEMPT_LEDGER_FILENAME,
            flags,
            0o600,
            dir_fd=state_directory_fd,
        )
    except FileExistsError as exc:
        raise CPUPerformanceQualificationV3Error(
            "exactly-once profile attempt was concurrently consumed"
        ) from exc
    except OSError as exc:
        raise CPUPerformanceQualificationV3Error(
            "attempt ledger cannot be created atomically"
        ) from exc
    try:
        os.fchmod(descriptor, 0o600)
        initial = os.fstat(descriptor)
        if (
            not stat.S_ISREG(initial.st_mode)
            or stat.S_IMODE(initial.st_mode) != 0o600
            or initial.st_uid != os.geteuid()
            or initial.st_nlink != 1
            or initial.st_size != 0
        ):
            raise CPUPerformanceQualificationV3Error(
                "attempt ledger initial identity is invalid"
            )
        _write_all(descriptor, raw, name="attempt ledger")
        os.fsync(descriptor)
        final = os.fstat(descriptor)
        if (
            (final.st_dev, final.st_ino) != (initial.st_dev, initial.st_ino)
            or final.st_nlink != 1
            or final.st_size != len(raw)
            or stat.S_IMODE(final.st_mode) != 0o600
        ):
            raise CPUPerformanceQualificationV3Error(
                "attempt ledger final identity is invalid"
            )
    finally:
        os.close(descriptor)
    os.fsync(state_directory_fd)
    return _issue_reserved_attempt(
        raw_sha256=_sha256_bytes(raw),
        activation_sha256=activation_sha256,
        attempt_receipt_sha256=str(document["receipt_sha256"]),
        output_path_sha256=output_path_sha256,
        run_nonce=run_nonce,
        process_start_ticks=process_start_ticks,
    )


class LiveCPUPerformanceRunResultV3:
    """Opaque process-local v3 result issued only by the sealed registry."""

    __slots__ = (
        "_artifact_bytes",
        "_artifact_sha256",
        "_issued_pid",
        "_issued_start_ticks",
        "__weakref__",
    )

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise CPUPerformanceQualificationV3Error(
            "live v3 results cannot be caller-constructed"
        )

    def __setattr__(self, _name: str, _value: object) -> None:
        raise CPUPerformanceQualificationV3Error("live v3 results are immutable")

    def _document(self) -> dict[str, Any]:
        if not _live_result_is_registered(self):
            raise CPUPerformanceQualificationV3Error(
                "live v3 result is not runner-issued"
            )
        return json.loads(self._artifact_bytes.decode("ascii"))

    @property
    def live_run_capability(self) -> bool:
        return _live_result_is_registered(self)

    @property
    def recorded_numeric_gate_passed(self) -> bool | None:
        value = self._document()["recorded_numeric_gate_passed"]
        return value if type(value) is bool else None

    @property
    def recorded_decision(self) -> str:
        return str(self._document()["recorded_decision"])

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self._document()["blockers"])

    def artifact_document(self) -> dict[str, object]:
        return self._document()


@dataclass(slots=True)
class _LiveResultRegistryEntryV3:
    artifact_sha256: str
    pid: int
    process_start_ticks: int
    state: str


def _build_live_result_registry() -> tuple[Any, Any, Any, Any]:
    issued: weakref.WeakKeyDictionary[
        LiveCPUPerformanceRunResultV3, _LiveResultRegistryEntryV3
    ] = weakref.WeakKeyDictionary()
    lock = threading.Lock()

    def valid_entry(
        result: object, *, required_state: str
    ) -> _LiveResultRegistryEntryV3 | None:
        if not isinstance(result, LiveCPUPerformanceRunResultV3):
            return None
        try:
            entry = issued.get(result)
            if entry is None or entry.state != required_state:
                return None
            if not (
                result._artifact_sha256 == entry.artifact_sha256
                and _sha256_bytes(result._artifact_bytes) == entry.artifact_sha256
                and result._issued_pid == entry.pid == os.getpid()
                and result._issued_start_ticks == entry.process_start_ticks
                and v2._process_start_ticks(os.getpid())
                == entry.process_start_ticks
            ):
                return None
            return entry
        except (AttributeError, TypeError, v2.CPUPerformanceError):
            return None

    def issue(projection: Mapping[str, object]) -> LiveCPUPerformanceRunResultV3:
        artifact = _seal_artifact(projection)
        require_cpu_performance_artifact_v3_document(artifact)
        artifact_bytes = _canonical_json_bytes(artifact)
        artifact_sha = _sha256_bytes(artifact_bytes)
        result = object.__new__(LiveCPUPerformanceRunResultV3)
        object.__setattr__(result, "_artifact_bytes", artifact_bytes)
        object.__setattr__(result, "_artifact_sha256", artifact_sha)
        object.__setattr__(result, "_issued_pid", os.getpid())
        object.__setattr__(result, "_issued_start_ticks", v2._process_start_ticks(os.getpid()))
        with lock:
            issued[result] = _LiveResultRegistryEntryV3(
                artifact_sha256=artifact_sha,
                pid=os.getpid(),
                process_start_ticks=v2._process_start_ticks(os.getpid()),
                state="issued",
            )
        return result

    def is_registered(result: object) -> bool:
        with lock:
            return valid_entry(result, required_state="issued") is not None

    def claim(result: object) -> bytes:
        with lock:
            entry = valid_entry(result, required_state="issued")
            if entry is None:
                raise CPUPerformanceQualificationV3Error(
                    "live v3 result was already claimed or is not runner-issued"
                )
            entry.state = "writing"
            return bytes(result._artifact_bytes)

    def consume(result: object) -> None:
        with lock:
            entry = valid_entry(result, required_state="writing")
            if entry is None:
                raise CPUPerformanceQualificationV3Error(
                    "live v3 result persistence state changed"
                )
            entry.state = "consumed"

    return issue, is_registered, claim, consume


(
    _issue_live_result,
    _live_result_is_registered,
    _claim_live_result,
    _consume_live_result,
) = _build_live_result_registry()


def _blocked_result(
    *,
    predecessor: v2.CPUPerformanceProfileV2,
    run_nonce: str,
    host: HostPreflightEvidenceV3,
    blockers: Sequence[str],
) -> LiveCPUPerformanceRunResultV3:
    projection = _artifact_projection(
        predecessor=predecessor,
        run_nonce=run_nonce,
        host=host,
        source_bindings=_source_bindings(complete=False),
        transcript=(),
        fixture_results=(),
        status="blocked_preflight",
        recorded_decision="BLOCKED",
        recorded_numeric_gate_passed=None,
        blockers=tuple(dict.fromkeys(blockers)),
    )
    return _issue_live_result(projection)


def _unevaluated_timeout_host() -> HostPreflightEvidenceV3:
    """Build truthful evidence when the total budget expires before preflight."""

    return HostPreflightEvidenceV3(
        cpu_model="",
        boost_state=None,
        available_cpu_affinity=(),
        platform_system=platform.system() or "unknown",
        platform_machine=platform.machine() or "unknown",
        byteorder=sys.byteorder,
        parent_pid=os.getpid(),
        parent_os_task_count=max(1, v2._os_task_count(os.getpid())),
        qualified=False,
        blockers=("host_not_evaluated_due_total_timeout",),
    )


def _require_live_execution_environment_v3() -> None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise CPUPerformanceQualificationV3Error(
            "GitHub Actions cannot execute the live v3 qualification"
        )


def _execute_reserved_performance_runner_v3(
    attempt: _ReservedProfileAttemptV3,
) -> LiveCPUPerformanceRunResultV3:
    """Execute only after the fixed account-scoped attempt has been burned."""

    started = time.monotonic()
    _require_live_execution_environment_v3()
    reserved = _begin_reserved_attempt(attempt)
    activation = verify_runner_activation_contract()
    if activation["activation_sha256"] != reserved._activation_sha256:
        raise CPUPerformanceQualificationV3Error(
            "runner activation changed after attempt reservation"
        )
    _profile_v3, predecessor = _load_profiles()
    deadline = started + predecessor.total_timeout_seconds
    run_nonce = reserved._run_nonce
    if time.monotonic() >= deadline:
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=_unevaluated_timeout_host(),
            blockers=("sealed_runner_total_timeout",),
        )
    host = derive_host_preflight_evidence_v3()
    blockers = list(host.blockers)
    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if blockers:
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=blockers,
        )
    bindings: Mapping[str, object] = {}
    try:
        bindings = _source_bindings(complete=True)
    except CPUPerformanceQualificationV3Error as exc:
        blockers.append(str(exc))
    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if blockers:
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    transcript: list[Mapping[str, Any]] = []
    schedule = v2._expected_launch_schedule(predecessor)
    if time.monotonic() >= deadline:
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=("sealed_runner_total_timeout",),
        )
    for expected in schedule:
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            blockers.append("sealed_runner_total_timeout")
            break
        try:
            row = v2._launch_sealed_child(
                run_nonce=run_nonce,
                global_launch_ordinal=int(expected["global_launch_ordinal"]),
                fixture_id=str(expected["fixture_id"]),
                phase=str(expected["phase"]),
                pair_index=int(expected["pair_index"]),
                role=str(expected["role"]),
                timeout_seconds=min(
                    float(predecessor.child_timeout_seconds), remaining_seconds
                ),
                absolute_deadline_monotonic=deadline,
            )
        except v2.CPUPerformanceError as exc:
            blockers.append(
                f"observation_{expected['global_launch_ordinal']}_failed:{exc}"
            )
            break
        if time.monotonic() >= deadline:
            blockers.append("sealed_runner_total_timeout")
            break
        transcript.append(row)
    if blockers or len(transcript) != len(schedule):
        blockers.append("sealed_measurement_incomplete")
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=blockers,
        )

    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if not blockers:
        try:
            final_bindings = _source_bindings(complete=True)
        except CPUPerformanceQualificationV3Error as exc:
            blockers.append(f"source_binding_postflight_failed:{exc}")
        else:
            if final_bindings != bindings:
                blockers.append("source_binding_changed_during_measurement")
    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if not blockers:
        final_host = derive_host_preflight_evidence_v3()
        if final_host != host:
            blockers.append("host_context_changed_during_measurement")
    if time.monotonic() >= deadline:
        blockers.append("sealed_runner_total_timeout")
    if blockers:
        if "sealed_runner_total_timeout" in blockers:
            discard_reason = "sealed_measurement_discarded_after_total_timeout"
        elif "host_context_changed_during_measurement" in blockers:
            discard_reason = "sealed_measurement_discarded_after_host_drift"
        else:
            discard_reason = "sealed_measurement_discarded_after_source_drift"
        blockers.append(discard_reason)
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=blockers,
        )

    try:
        core_bindings = bindings["measurement_core"]
        validated = v2._validate_transcript_rows(
            [dict(row) for row in transcript],
            profile=predecessor,
            run_nonce=run_nonce,
            parent_pid=host.parent_pid,
            source_bindings=core_bindings,
        )
        if time.monotonic() >= deadline:
            raise v2.CPUPerformanceError("sealed_runner_total_timeout")
        fixture_results, numeric_passed, numeric_blockers = (
            v2._derive_fixture_results(validated, predecessor)
        )
    except v2.CPUPerformanceError as exc:
        validation_blockers = (
            (
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            )
            if str(exc) == "sealed_runner_total_timeout"
            else (
                f"sealed_transcript_validation_failed:{exc}",
                "sealed_measurement_discarded_after_validation_failure",
            )
        )
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=validation_blockers,
        )
    if time.monotonic() >= deadline:
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=(
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            ),
        )
    projection = _artifact_projection(
        predecessor=predecessor,
        run_nonce=run_nonce,
        host=host,
        source_bindings=bindings,
        transcript=validated,
        fixture_results=fixture_results,
        status="complete",
        recorded_decision="GO" if numeric_passed else "NO_GO",
        recorded_numeric_gate_passed=numeric_passed,
        blockers=numeric_blockers,
    )
    if time.monotonic() >= deadline:
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=(
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            ),
        )
    result = _issue_live_result(projection)
    if time.monotonic() >= deadline:
        return _blocked_result(
            predecessor=predecessor,
            run_nonce=run_nonce,
            host=host,
            blockers=(
                "sealed_runner_total_timeout",
                "sealed_measurement_discarded_after_total_timeout",
            ),
        )
    return result


def _write_cpu_performance_artifact_v3(
    result: LiveCPUPerformanceRunResultV3,
    path: Path,
) -> Path:
    """Publish and irrevocably consume one process-local live result."""

    target = _validated_absent_artifact_target(path)
    parent = target.parent
    try:
        parent_stat = os.stat(parent, follow_symlinks=False)
    except OSError as exc:
        raise CPUPerformanceQualificationV3Error(
            "artifact parent directory is unavailable"
        ) from exc
    artifact_bytes = _claim_live_result(result)
    raw = artifact_bytes + b"\n"
    require_cpu_performance_artifact_v3_bytes(raw)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise CPUPerformanceQualificationV3Error("artifact exceeds byte limit")
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_fd = os.open(parent, directory_flags)
    except OSError as exc:
        raise CPUPerformanceQualificationV3Error(
            "artifact parent cannot be opened safely"
        ) from exc
    temporary_name = f".{target.name}.tmp.{secrets.token_hex(16)}"
    target_name = target.name
    temporary_created = False
    target_published = False
    descriptor: int | None = None
    staging_identity: tuple[int, int] | None = None
    try:
        descriptor_parent = os.fstat(directory_fd)
        if (descriptor_parent.st_dev, descriptor_parent.st_ino) != (
            parent_stat.st_dev,
            parent_stat.st_ino,
        ):
            raise CPUPerformanceQualificationV3Error(
                "artifact parent changed before descriptor binding"
            )
        v2._require_same_trusted_parent(parent, directory_fd, parent_stat)
        try:
            os.stat(target_name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise CPUPerformanceQualificationV3Error(
                "artifact output already exists"
            )
        file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
        file_flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(
                temporary_name,
                file_flags,
                0o600,
                dir_fd=directory_fd,
            )
        except OSError as exc:
            raise CPUPerformanceQualificationV3Error(
                "artifact staging file cannot be created"
            ) from exc
        temporary_created = True
        os.fchmod(descriptor, 0o600)
        initial_staging = os.fstat(descriptor)
        staging_identity = (initial_staging.st_dev, initial_staging.st_ino)
        if (
            not stat.S_ISREG(initial_staging.st_mode)
            or stat.S_IMODE(initial_staging.st_mode) != 0o600
            or initial_staging.st_nlink != 1
            or initial_staging.st_size != 0
        ):
            raise CPUPerformanceQualificationV3Error(
                "artifact staging identity is invalid"
            )
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise CPUPerformanceQualificationV3Error(
                    "artifact write made no progress"
                )
            offset += written
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or metadata.st_size != len(raw)
            or (metadata.st_dev, metadata.st_ino) != staging_identity
        ):
            raise CPUPerformanceQualificationV3Error(
                "artifact staging identity is invalid"
            )
        v2._require_same_trusted_parent(parent, directory_fd, parent_stat)
        try:
            os.link(
                temporary_name,
                target_name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except (FileExistsError, OSError) as exc:
            try:
                ambiguous_target = os.stat(
                    target_name, dir_fd=directory_fd, follow_symlinks=False
                )
            except OSError:
                pass
            else:
                if (ambiguous_target.st_dev, ambiguous_target.st_ino) == (
                    staging_identity
                ):
                    try:
                        os.unlink(target_name, dir_fd=directory_fd)
                        os.fsync(directory_fd)
                    except OSError:
                        pass
            if isinstance(exc, FileExistsError):
                raise CPUPerformanceQualificationV3Error(
                    "artifact output was created concurrently"
                ) from exc
            raise CPUPerformanceQualificationV3Error(
                "artifact cannot be published atomically"
            ) from exc
        target_published = True
        linked = os.stat(target_name, dir_fd=directory_fd, follow_symlinks=False)
        staged_after_link = os.fstat(descriptor)
        if (
            (linked.st_dev, linked.st_ino) != staging_identity
            or (staged_after_link.st_dev, staged_after_link.st_ino)
            != staging_identity
            or linked.st_nlink != 2
            or staged_after_link.st_nlink != 2
        ):
            raise CPUPerformanceQualificationV3Error(
                "published artifact link identity is invalid"
            )
        os.unlink(temporary_name, dir_fd=directory_fd)
        temporary_created = False
        if os.fstat(descriptor).st_nlink != 1:
            raise CPUPerformanceQualificationV3Error(
                "published artifact link count is invalid"
            )
        os.fsync(directory_fd)
        verification_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(
            os, "O_NOFOLLOW", 0
        )
        verification_fd = os.open(
            target_name, verification_flags, dir_fd=directory_fd
        )
        try:
            published = os.fstat(verification_fd)
            observed = b""
            while len(observed) <= len(raw):
                chunk = os.read(
                    verification_fd,
                    min(1 << 20, len(raw) + 1 - len(observed)),
                )
                if not chunk:
                    break
                observed += chunk
            if (
                not stat.S_ISREG(published.st_mode)
                or stat.S_IMODE(published.st_mode) != 0o600
                or published.st_nlink != 1
                or (published.st_dev, published.st_ino) != staging_identity
                or observed != raw
            ):
                raise CPUPerformanceQualificationV3Error(
                    "published artifact identity is invalid"
                )
        finally:
            os.close(verification_fd)
        v2._require_same_trusted_parent(parent, directory_fd, parent_stat)
    except Exception as exc:
        if target_published and staging_identity is not None:
            try:
                target_stat = os.stat(
                    target_name, dir_fd=directory_fd, follow_symlinks=False
                )
            except OSError:
                pass
            else:
                if (target_stat.st_dev, target_stat.st_ino) == staging_identity:
                    try:
                        os.unlink(target_name, dir_fd=directory_fd)
                        os.fsync(directory_fd)
                    except OSError:
                        pass
        if isinstance(exc, v2.CPUPerformanceError):
            raise CPUPerformanceQualificationV3Error(str(exc)) from exc
        raise
    finally:
        if temporary_created:
            try:
                temporary_stat = os.stat(
                    temporary_name, dir_fd=directory_fd, follow_symlinks=False
                )
            except OSError:
                pass
            else:
                if staging_identity is None or (
                    temporary_stat.st_dev,
                    temporary_stat.st_ino,
                ) == staging_identity:
                    try:
                        os.unlink(temporary_name, dir_fd=directory_fd)
                    except OSError:
                        pass
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_fd)
        _consume_live_result(result)
    return parent / target_name


def _read_state_file(
    directory_fd: int,
    filename: str,
    *,
    name: str,
) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(filename, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise CPUPerformanceQualificationV3Error(f"{name} is unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_uid != os.geteuid()
            or before.st_nlink != 1
            or not 1 <= before.st_size <= MAX_STATE_BYTES
        ):
            raise CPUPerformanceQualificationV3Error(
                f"{name} is not an owner-only bounded state file"
            )
        chunks: list[bytes] = []
        observed = 0
        while observed <= MAX_STATE_BYTES:
            chunk = os.read(
                descriptor,
                min(64 * 1024, MAX_STATE_BYTES + 1 - observed),
            )
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
        identity_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if observed != before.st_size or any(
            getattr(before, field) != getattr(after, field)
            for field in identity_fields
        ):
            raise CPUPerformanceQualificationV3Error(f"{name} changed while read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _require_attempt_ledger_bytes(raw: bytes) -> Mapping[str, Any]:
    try:
        parsed = v2.require_canonical_json_object_bytes(
            raw,
            name="CPU performance v3 attempt ledger",
            maximum_bytes=MAX_STATE_BYTES,
            trailing_newline_required=True,
        )
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    document = _require_exact_keys(
        parsed,
        name="CPU performance v3 attempt ledger",
        keys=(
            "schema_id",
            "profile_id",
            "profile_sha256",
            "activation_sha256",
            "run_nonce",
            "output_path_sha256",
            "process_id",
            "process_start_ticks",
            "attempt_ordinal",
            "measurement_started",
            "authority",
            "restrictions",
            "receipt_sha256",
        ),
    )
    receipt = _require_digest(document["receipt_sha256"], name="attempt receipt")
    projection = {
        key: value for key, value in document.items() if key != "receipt_sha256"
    }
    if (
        document["schema_id"] != ATTEMPT_LEDGER_SCHEMA_ID
        or document["profile_id"] != PROFILE_ID
        or document["profile_sha256"] != PROFILE_SHA256
        or document["authority"] != dict(v2.AUTHORITY_FALSE)
        or document["restrictions"] != dict(v2.RESTRICTIONS)
        or document["attempt_ordinal"] != 1
        or document["measurement_started"] is not False
        or type(document["process_id"]) is not int
        or document["process_id"] < 1
        or type(document["process_start_ticks"]) is not int
        or document["process_start_ticks"] < 1
        or _sha256_json(projection) != receipt
    ):
        raise CPUPerformanceQualificationV3Error("attempt ledger contract changed")
    _require_digest(document["activation_sha256"], name="attempt activation SHA-256")
    _require_digest(document["run_nonce"], name="attempt run nonce")
    _require_digest(document["output_path_sha256"], name="attempt output path SHA-256")
    return document


def _publish_terminal_state(
    directory_fd: int,
    raw: bytes,
) -> None:
    if not raw or len(raw) > MAX_STATE_BYTES:
        raise CPUPerformanceQualificationV3Error(
            "terminal state byte count is outside its envelope"
        )
    temporary_name = f".{TERMINAL_STATE_FILENAME}.tmp.{secrets.token_hex(16)}"
    file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    file_flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    temporary_created = False
    target_published = False
    identity: tuple[int, int] | None = None
    try:
        try:
            os.stat(
                TERMINAL_STATE_FILENAME,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise CPUPerformanceQualificationV3Error(
                "terminal state is ambiguous"
            ) from exc
        else:
            raise CPUPerformanceQualificationV3Error(
                "terminal state already exists"
            )
        try:
            descriptor = os.open(
                temporary_name,
                file_flags,
                0o600,
                dir_fd=directory_fd,
            )
        except OSError as exc:
            raise CPUPerformanceQualificationV3Error(
                "terminal staging file cannot be created"
            ) from exc
        temporary_created = True
        os.fchmod(descriptor, 0o600)
        initial = os.fstat(descriptor)
        identity = (initial.st_dev, initial.st_ino)
        if (
            not stat.S_ISREG(initial.st_mode)
            or stat.S_IMODE(initial.st_mode) != 0o600
            or initial.st_uid != os.geteuid()
            or initial.st_nlink != 1
            or initial.st_size != 0
        ):
            raise CPUPerformanceQualificationV3Error(
                "terminal staging identity is invalid"
            )
        _write_all(descriptor, raw, name="terminal state")
        os.fsync(descriptor)
        final = os.fstat(descriptor)
        if (
            (final.st_dev, final.st_ino) != identity
            or final.st_nlink != 1
            or final.st_size != len(raw)
            or stat.S_IMODE(final.st_mode) != 0o600
        ):
            raise CPUPerformanceQualificationV3Error(
                "terminal staging identity changed"
            )
        try:
            os.link(
                temporary_name,
                TERMINAL_STATE_FILENAME,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise CPUPerformanceQualificationV3Error(
                "terminal state was concurrently published"
            ) from exc
        except OSError as exc:
            raise CPUPerformanceQualificationV3Error(
                "terminal state cannot be published atomically"
            ) from exc
        target_published = True
        linked = os.stat(
            TERMINAL_STATE_FILENAME,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (linked.st_dev, linked.st_ino) != identity or linked.st_nlink != 2:
            raise CPUPerformanceQualificationV3Error(
                "terminal published identity is invalid"
            )
        os.unlink(temporary_name, dir_fd=directory_fd)
        temporary_created = False
        if os.fstat(descriptor).st_nlink != 1:
            raise CPUPerformanceQualificationV3Error(
                "terminal published link count is invalid"
            )
        os.fsync(directory_fd)
        if _read_state_file(
            directory_fd,
            TERMINAL_STATE_FILENAME,
            name="CPU performance v3 terminal state",
        ) != raw:
            raise CPUPerformanceQualificationV3Error(
                "terminal published bytes changed"
            )
    except BaseException:
        if target_published and identity is not None:
            try:
                target = os.stat(
                    TERMINAL_STATE_FILENAME,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except OSError:
                pass
            else:
                if (target.st_dev, target.st_ino) == identity:
                    try:
                        os.unlink(TERMINAL_STATE_FILENAME, dir_fd=directory_fd)
                        os.fsync(directory_fd)
                    except OSError:
                        pass
        raise
    finally:
        if temporary_created:
            try:
                temporary = os.stat(
                    temporary_name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except OSError:
                pass
            else:
                if identity is None or (temporary.st_dev, temporary.st_ino) == identity:
                    try:
                        os.unlink(temporary_name, dir_fd=directory_fd)
                    except OSError:
                        pass
        if descriptor is not None:
            os.close(descriptor)


def _terminal_state_document(
    *,
    attempt: _ReservedProfileAttemptV3,
    artifact_raw: bytes,
    artifact: VerifiedOfflineCPUPerformanceArtifactV3,
) -> dict[str, object]:
    artifact_document = artifact.document
    projection: dict[str, object] = {
        "schema_id": TERMINAL_STATE_SCHEMA_ID,
        "status": "terminal_recorded",
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "activation_sha256": attempt._activation_sha256,
        "attempt_ledger_raw_sha256": attempt._raw_sha256,
        "attempt_receipt_sha256": attempt._attempt_receipt_sha256,
        "run_nonce": attempt._run_nonce,
        "output_path_sha256": attempt._output_path_sha256,
        "artifact_raw_sha256": _sha256_bytes(artifact_raw),
        "artifact_byte_count": len(artifact_raw),
        "artifact_receipt_sha256": artifact_document["receipt_sha256"],
        "artifact_persisted": True,
        "recorded_decision": artifact.recorded_decision,
        "recorded_numeric_gate_passed": artifact.recorded_numeric_gate_passed,
        "blockers": list(artifact_document["blockers"]),
        "decision_returned_only_after_terminal_persistence": True,
        "execution_attested": False,
        "live_run_capability": False,
        "qualification_authority": False,
        "authority": dict(v2.AUTHORITY_FALSE),
        "restrictions": dict(v2.RESTRICTIONS),
    }
    return {**projection, "receipt_sha256": _sha256_json(projection)}


def _require_terminal_state_bytes(
    raw: bytes,
    *,
    attempt_raw: bytes,
    artifact_raw: bytes,
    output_path_sha256: str,
) -> Mapping[str, Any]:
    try:
        parsed = v2.require_canonical_json_object_bytes(
            raw,
            name="CPU performance v3 terminal state",
            maximum_bytes=MAX_STATE_BYTES,
            trailing_newline_required=True,
        )
    except v2.CPUPerformanceError as exc:
        raise CPUPerformanceQualificationV3Error(str(exc)) from exc
    attempt = _require_attempt_ledger_bytes(attempt_raw)
    artifact = require_cpu_performance_artifact_v3_bytes(artifact_raw)
    artifact_document = artifact.document
    document = _require_exact_keys(
        parsed,
        name="CPU performance v3 terminal state",
        keys=(
            "schema_id",
            "status",
            "profile_id",
            "profile_sha256",
            "activation_sha256",
            "attempt_ledger_raw_sha256",
            "attempt_receipt_sha256",
            "run_nonce",
            "output_path_sha256",
            "artifact_raw_sha256",
            "artifact_byte_count",
            "artifact_receipt_sha256",
            "artifact_persisted",
            "recorded_decision",
            "recorded_numeric_gate_passed",
            "blockers",
            "decision_returned_only_after_terminal_persistence",
            "execution_attested",
            "live_run_capability",
            "qualification_authority",
            "authority",
            "restrictions",
            "receipt_sha256",
        ),
    )
    receipt = _require_digest(document["receipt_sha256"], name="terminal receipt")
    projection = {
        key: value for key, value in document.items() if key != "receipt_sha256"
    }
    blockers = document["blockers"]
    if (
        document["schema_id"] != TERMINAL_STATE_SCHEMA_ID
        or document["status"] != "terminal_recorded"
        or document["profile_id"] != PROFILE_ID
        or document["profile_sha256"] != PROFILE_SHA256
        or document["activation_sha256"] != attempt["activation_sha256"]
        or document["attempt_ledger_raw_sha256"] != _sha256_bytes(attempt_raw)
        or document["attempt_receipt_sha256"] != attempt["receipt_sha256"]
        or document["run_nonce"] != attempt["run_nonce"]
        or document["output_path_sha256"] != output_path_sha256
        or document["output_path_sha256"] != attempt["output_path_sha256"]
        or document["artifact_raw_sha256"] != _sha256_bytes(artifact_raw)
        or document["artifact_byte_count"] != len(artifact_raw)
        or document["artifact_receipt_sha256"]
        != artifact_document["receipt_sha256"]
        or document["artifact_persisted"] is not True
        or document["recorded_decision"] != artifact.recorded_decision
        or document["recorded_numeric_gate_passed"]
        is not artifact.recorded_numeric_gate_passed
        or blockers != artifact_document["blockers"]
        or type(blockers) is not list
        or any(type(value) is not str or not value for value in blockers)
        or document["decision_returned_only_after_terminal_persistence"] is not True
        or document["execution_attested"] is not False
        or document["live_run_capability"] is not False
        or document["qualification_authority"] is not False
        or document["authority"] != dict(v2.AUTHORITY_FALSE)
        or document["restrictions"] != dict(v2.RESTRICTIONS)
        or _sha256_json(projection) != receipt
    ):
        raise CPUPerformanceQualificationV3Error(
            "terminal state does not rederive from attempt and artifact"
        )
    return document


@dataclass(frozen=True, slots=True)
class PersistedCPUPerformanceRunV3:
    artifact_path: Path
    attempt_ledger_path: Path
    terminal_state_path: Path
    recorded_numeric_gate_passed: bool | None
    recorded_decision: str
    blockers: tuple[str, ...]
    artifact_sha256: str
    terminal_state_sha256: str
    live_run_capability: bool = False
    qualification_authority: bool = False
    execution_attested: bool = False


def run_sealed_local_performance_runner_v3(
    output_path: Path,
) -> PersistedCPUPerformanceRunV3:
    """Run exactly once and return a decision only after terminal persistence."""

    _require_live_execution_environment_v3()
    target = _validated_absent_artifact_target(output_path)
    activation = verify_runner_activation_contract()
    state_directory, state_directory_fd = _open_state_directory()
    try:
        _require_state_directory_binding(state_directory, state_directory_fd)
        attempt = _reserve_profile_attempt_v3(
            state_directory_fd=state_directory_fd,
            activation_sha256=str(activation["activation_sha256"]),
            output_path_sha256=_output_path_sha256(target),
        )
        live_result = _execute_reserved_performance_runner_v3(attempt)
        published = _write_cpu_performance_artifact_v3(live_result, target)
        artifact = read_cpu_performance_artifact_v3(published)
        artifact_raw = _read_exact_source(
            published,
            name="CPU performance artifact v3",
            maximum_bytes=MAX_ARTIFACT_BYTES,
        )
        attempt_raw = _read_state_file(
            state_directory_fd,
            ATTEMPT_LEDGER_FILENAME,
            name="CPU performance v3 attempt ledger",
        )
        if _sha256_bytes(attempt_raw) != attempt._raw_sha256:
            raise CPUPerformanceQualificationV3Error(
                "attempt ledger changed after execution"
            )
        terminal_document = _terminal_state_document(
            attempt=attempt,
            artifact_raw=artifact_raw,
            artifact=artifact,
        )
        terminal_raw = _canonical_json_bytes(terminal_document) + b"\n"
        _publish_terminal_state(state_directory_fd, terminal_raw)
        persisted_terminal = _read_state_file(
            state_directory_fd,
            TERMINAL_STATE_FILENAME,
            name="CPU performance v3 terminal state",
        )
        terminal = _require_terminal_state_bytes(
            persisted_terminal,
            attempt_raw=attempt_raw,
            artifact_raw=artifact_raw,
            output_path_sha256=_output_path_sha256(published),
        )
        _require_state_directory_binding(state_directory, state_directory_fd)
        return PersistedCPUPerformanceRunV3(
            artifact_path=published,
            attempt_ledger_path=state_directory / ATTEMPT_LEDGER_FILENAME,
            terminal_state_path=state_directory / TERMINAL_STATE_FILENAME,
            recorded_numeric_gate_passed=artifact.recorded_numeric_gate_passed,
            recorded_decision=artifact.recorded_decision,
            blockers=tuple(str(value) for value in terminal["blockers"]),
            artifact_sha256=_sha256_bytes(artifact_raw),
            terminal_state_sha256=_sha256_bytes(persisted_terminal),
        )
    finally:
        os.close(state_directory_fd)


__all__ = [
    "ACTIVATION_RELATIVE_PATH",
    "ARTIFACT_SCHEMA_ID",
    "CPUPerformanceQualificationV3Error",
    "PersistedCPUPerformanceRunV3",
    "PROFILE_ID",
    "PROFILE_SHA256",
    "VerifiedOfflineCPUPerformanceArtifactV3",
    "read_cpu_performance_artifact_v3",
    "require_cpu_performance_artifact_v3_bytes",
    "require_cpu_performance_artifact_v3_document",
    "run_sealed_local_performance_runner_v3",
    "verify_runner_activation_contract",
]
