from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from api.artifact_access import open_confined_regular_file
from api.config import settings
from api.job_artifacts import (
    atomic_write_text_file,
    read_current_attempt_file_bytes,
    resolve_job_results_dir,
    sha256_current_attempt_file,
)
from api.linux_runner_supervisor import (
    linux_pid_namespace_launcher,
    open_linux_pid_namespace_init,
    require_linux_runner_supervisor_support,
    signal_linux_pidfd,
    wait_linux_pidfd_exit,
)
from api.request_privacy import sanitize_request_for_ledger
from api.runner_profile_contract import validate_runner_profile_execution_contract
from api.validated_runner_execution_evidence import (
    EXECUTION_EVIDENCE_PROVENANCE_KEY,
    build_validated_runner_execution_evidence,
)
from api.validated_runner_runtime_qualification import (
    NamespaceRuntimeQualification,
    require_validated_runner_namespace_runtime,
)
from betelgeuze_ai_md.contracts import EvidenceBundle
from betelgeuze_ai_md.contracts.errors import ContractValidationError

ALLOWED_RUNNER_SCRIPTS = {
    "tools/run_ligand_htvs_pipeline.py",
    "tools/run_ligand_backmapping_scoring.py",
    "tools/run_ligand_topk_delivery.py",
    "tools/run_tier_beta_vertical_slice.py",
}

_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_RUNNER_ENV_ALLOWLIST = {
    "PATH",
    "HOME",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "TZ",
    "PYTHONHASHSEED",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "PYTHONDONTWRITEBYTECODE",
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
    "HSA_OVERRIDE_GFX_VERSION",
}
_SENSITIVE_ENV_NAME_PARTS = {
    "AUTH",
    "CREDENTIAL",
    "CREDENTIALS",
    "KEY",
    "KEYS",
    "PASSWORD",
    "PASSWORDS",
    "SECRET",
    "SECRETS",
    "TOKEN",
    "TOKENS",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _results_dir(job_id: str) -> Path:
    return resolve_job_results_dir(job_id, settings.results_storage_path)


def _status_path(job_id: str) -> Path:
    return _results_dir(job_id) / "status.json"


def _write_status(job_id: str, payload: dict[str, Any]) -> None:
    path = _status_path(job_id)
    atomic_write_text_file(
        path,
        json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n",
    )


def _write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text_file(
        path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )


def _safe_profile_id(profile_id: Any) -> str:
    value = str(profile_id or "").strip()
    if not _PROFILE_ID_RE.match(value):
        raise ValueError("runner_profile_id must be a simple allowlisted profile id")
    return value


def _load_profile(profile_id: str) -> dict[str, Any]:
    profiles_dir = Path(settings.api_validated_runner_profiles_path)
    profile_path = profiles_dir / f"{profile_id}.json"
    try:
        resolved = profile_path.resolve()
        profiles_root = profiles_dir.resolve()
        if profiles_root not in resolved.parents:
            raise ValueError("runner profile path escapes configured profile directory")
    except FileNotFoundError:
        raise FileNotFoundError(f"runner profile not found: {profile_id}") from None

    if not profile_path.exists():
        raise FileNotFoundError(f"runner profile not found: {profile_id}")
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("runner profile must be a JSON object")
    if str(payload.get("profile_id", profile_id)) != profile_id:
        raise ValueError("runner profile_id does not match requested profile")
    if payload.get("enabled") is not True:
        raise PermissionError("runner profile is not enabled")
    return payload


def _render_template(value: str, context: dict[str, str]) -> str:
    try:
        return str(value).format(**context)
    except KeyError as exc:
        raise ValueError(f"unsupported runner profile placeholder: {exc}") from exc


def _require_output_within_results_dir(
    path_value: str,
    *,
    results_dir: Path,
    label: str,
) -> None:
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = _repo_root() / candidate
    try:
        logical_root = Path(os.path.abspath(str(results_dir)))
        logical_parent = Path(os.path.abspath(str(candidate.parent)))
        relative_parent = logical_parent.relative_to(logical_root)
        resolved_root = results_dir.resolve(strict=True)
        resolved_parent = candidate.parent.resolve(strict=True)
    except ValueError as exc:
        raise PermissionError(f"{label} escapes the job attempt results directory") from exc
    except OSError as exc:
        raise PermissionError(f"{label} parent is unavailable") from exc
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise PermissionError(f"{label} escapes the job attempt results directory")
    cursor = logical_root
    for part in relative_parent.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PermissionError(f"{label} parent must not contain symbolic links")
    try:
        if candidate.is_symlink():
            raise PermissionError(f"{label} must not be a symbolic link")
    except OSError as exc:
        raise PermissionError(f"{label} could not be validated") from exc


def _runner_script(profile: dict[str, Any]) -> str:
    script = str(profile.get("runner_script", "") or "").strip()
    if script not in ALLOWED_RUNNER_SCRIPTS and str(Path(script).resolve()) not in ALLOWED_RUNNER_SCRIPTS:
        raise PermissionError(f"runner_script is not allowlisted: {script}")
    path = Path(script)
    if not path.is_absolute():
        path = _repo_root() / path
    if not path.exists():
        raise FileNotFoundError(f"runner_script missing: {script}")
    return str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_confined_result_file(path: Path, *, results_dir: Path) -> str:
    """Hash one regular, single-link result without trusting its pathname."""

    try:
        pinned_digest = sha256_current_attempt_file(path)
        if pinned_digest is not None:
            return pinned_digest
        _, handle = open_confined_regular_file(
            results_dir,
            path,
            label="validated runner result",
        )
        digest = hashlib.sha256()
        with handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except (OSError, HTTPException) as exc:
        raise PermissionError(
            "validated runner result_file must be a confined regular single-link file"
        ) from exc


def _read_confined_result_bytes(
    path: Path,
    *,
    results_dir: Path,
    maximum_bytes: int,
    label: str,
) -> bytes:
    """Read bounded runner output through a pinned or root-confined descriptor."""

    try:
        pinned_payload = read_current_attempt_file_bytes(
            path,
            maximum_bytes=maximum_bytes,
        )
        if pinned_payload is not None:
            return pinned_payload
        _, handle = open_confined_regular_file(results_dir, path, label=label)
        with handle:
            payload = handle.read(maximum_bytes + 1)
        if len(payload) > maximum_bytes:
            raise OSError(f"{label} exceeds the permitted size")
        return payload
    except (OSError, HTTPException) as exc:
        raise PermissionError(
            f"{label} must be a confined regular single-link file"
        ) from exc


def _runtime_qualification_record(
    qualification: NamespaceRuntimeQualification,
) -> dict[str, Any]:
    return {
        "validated_runner_namespace_runtime_qualified": qualification.qualified,
        "validated_runner_namespace_runtime_receipt_schema_version": (
            qualification.schema_version
        ),
        "validated_runner_namespace_runtime_receipt_sha256": (
            qualification.receipt_sha256
        ),
        "validated_runner_namespace_runtime_receipt_issued_at_utc": (
            qualification.issued_at_utc
        ),
        "validated_runner_namespace_runtime_receipt_expires_at_utc": (
            qualification.expires_at_utc
        ),
    }


def _require_nonempty_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key, "") or "").strip()
    if not value:
        raise PermissionError(f"runner profile production_readiness.{key} is required")
    return value


def _validate_evidence_artifact(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        path = _repo_root() / path
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"runner profile evidence artifact missing: {path_value}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PermissionError("runner profile evidence artifact must be a JSON object")
    required_true = (
        "input_contract_reviewed",
        "output_contract_reviewed",
        "claim_boundary_reviewed",
        "gate_policy_reviewed",
        "fake_result_emission_forbidden",
    )
    missing = [key for key in required_true if payload.get(key) is not True]
    if missing:
        raise PermissionError(f"runner profile evidence artifact has unmet checks: {missing}")
    gate_artifact = str(payload.get("gate_policy_artifact", "") or "").strip()
    if not gate_artifact:
        raise PermissionError("runner profile evidence artifact requires gate_policy_artifact")
    return payload


def validate_profile_readiness(profile: dict[str, Any], *, runner_script_path: str) -> dict[str, Any]:
    readiness = profile.get("production_readiness")
    if not isinstance(readiness, dict):
        raise PermissionError("enabled runner profile requires production_readiness block")

    approved_by = _require_nonempty_text(readiness, "approved_by")
    approved_at_utc = _require_nonempty_text(readiness, "approved_at_utc")
    claim_scope = _require_nonempty_text(readiness, "claim_scope")
    evidence_artifact = _require_nonempty_text(readiness, "evidence_artifact")
    expected_hash = _require_nonempty_text(readiness, "runner_script_sha256")
    observed_hash = _sha256_file(Path(runner_script_path))
    if observed_hash != expected_hash:
        raise PermissionError("runner profile runner_script_sha256 does not match allowlisted runner")

    evidence_payload = _validate_evidence_artifact(evidence_artifact)
    return {
        "approved_by": approved_by,
        "approved_at_utc": approved_at_utc,
        "claim_scope": claim_scope,
        "evidence_artifact": evidence_artifact,
        "runner_script_sha256": observed_hash,
        "gate_policy_artifact": str(evidence_payload.get("gate_policy_artifact", "") or ""),
    }


def _safe_runner_environment() -> dict[str, str]:
    """Build a minimal child environment without API credentials or signing keys."""

    child_env = {
        key: value
        for key, value in os.environ.items()
        if key in _RUNNER_ENV_ALLOWLIST or key.startswith("LC_")
        if not _SENSITIVE_ENV_NAME_PARTS.intersection(key.upper().split("_"))
    }
    child_env.setdefault("PATH", os.defpath)
    child_env["PYTHONUNBUFFERED"] = "1"
    return child_env


def _run_profile_command(
    command: list[str],
    *,
    timeout_seconds: int,
    cancellation_event: threading.Event | None = None,
) -> dict[str, Any]:
    require_linux_runner_supervisor_support()
    namespace_launcher = linux_pid_namespace_launcher()
    bounded_timeout = max(1, int(timeout_seconds))
    protocol_nonce = secrets.token_hex(32)
    config = json.dumps(
        {
            "command": command,
            "cwd": str(_repo_root()),
            "timeout_seconds": bounded_timeout,
            "protocol_nonce": protocol_nonce,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    config_read_fd, config_write_fd = os.pipe()
    start_read_fd, start_write_fd = os.pipe()
    supervisor_script = Path(__file__).with_name("linux_runner_supervisor.py")
    try:
        try:
            supervisor = subprocess.Popen(
                [
                    namespace_launcher,
                    "--user",
                    "--map-current-user",
                    "--mount",
                    "--pid",
                    "--fork",
                    "--kill-child=SIGKILL",
                    "--mount-proc",
                    "--propagation",
                    "private",
                    sys.executable,
                    str(supervisor_script),
                    "--config-fd",
                    str(config_read_fd),
                    "--start-fd",
                    str(start_read_fd),
                ],
                cwd=str(_repo_root()),
                text=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                env=_safe_runner_environment(),
                pass_fds=(config_read_fd, start_read_fd),
            )
        finally:
            os.close(config_read_fd)
            os.close(start_read_fd)
    except BaseException:
        os.close(config_write_fd)
        os.close(start_write_fd)
        raise
    try:
        view = memoryview(config)
        while view:
            written = os.write(config_write_fd, view)
            view = view[written:]
    except (BrokenPipeError, OSError) as exc:
        os.close(start_write_fd)
        supervisor.kill()
        supervisor.communicate()
        raise RuntimeError("validated runner supervisor rejected its configuration") from exc
    finally:
        os.close(config_write_fd)

    try:
        namespace_init_pidfd = open_linux_pid_namespace_init(supervisor.pid)
    except BaseException as exc:
        os.close(start_write_fd)
        try:
            supervisor.kill()
        except ProcessLookupError:
            pass
        supervisor_stdout, supervisor_stderr = supervisor.communicate()
        reason = f"validated runner namespace initialization failed: {exc}"
        return {
            "returncode": 125,
            "timed_out": False,
            "cancelled": bool(cancellation_event and cancellation_event.is_set()),
            "stdout": "",
            "stderr": "\n".join(
                item for item in (supervisor_stderr or "", reason) if item
            ),
            "containment_error": reason,
            "supervisor": "linux_pid_namespace_v1",
        }

    try:
        if cancellation_event is not None and cancellation_event.is_set():
            os.close(start_write_fd)
            signal_linux_pidfd(namespace_init_pidfd, signal.SIGKILL)
            try:
                supervisor.kill()
            except ProcessLookupError:
                pass
            supervisor_stdout, supervisor_stderr = supervisor.communicate()
            namespace_exited = wait_linux_pidfd_exit(
                namespace_init_pidfd,
                timeout_seconds=2.0,
            )
            reason = "" if namespace_exited else "namespace init survived cancellation"
            return {
                "returncode": -signal.SIGKILL if namespace_exited else 125,
                "timed_out": False,
                "cancelled": True,
                "stdout": "",
                "stderr": "\n".join(
                    item for item in (supervisor_stderr or "", reason) if item
                ),
                "containment_error": reason,
                "supervisor": "linux_pid_namespace_v1",
            }
        try:
            written = os.write(start_write_fd, b"R")
            if written != 1:
                raise OSError("short validated runner start authorization")
        finally:
            os.close(start_write_fd)

        cancellation_requested = False
        outer_timeout = False
        supervisor_stop_requested = False
        forced_namespace_teardown = False
        teardown_errors: list[str] = []
        shutdown_deadline: float | None = None
        hard_deadline = time.monotonic() + bounded_timeout + 5.0
        while True:
            now = time.monotonic()
            if (
                not supervisor_stop_requested
                and cancellation_event is not None
                and cancellation_event.is_set()
            ):
                cancellation_requested = True
                supervisor_stop_requested = True
                forced_namespace_teardown = True
                shutdown_deadline = now + 5.0
                try:
                    signal_linux_pidfd(namespace_init_pidfd, signal.SIGKILL)
                except BaseException as exc:
                    teardown_errors.append(str(exc))
                try:
                    supervisor.kill()
                except ProcessLookupError:
                    pass
            if not supervisor_stop_requested and now >= hard_deadline:
                outer_timeout = True
                supervisor_stop_requested = True
                forced_namespace_teardown = True
                shutdown_deadline = now + 5.0
                try:
                    signal_linux_pidfd(namespace_init_pidfd, signal.SIGKILL)
                except BaseException as exc:
                    teardown_errors.append(str(exc))
                try:
                    supervisor.kill()
                except ProcessLookupError:
                    pass
            if shutdown_deadline is not None and now >= shutdown_deadline:
                try:
                    signal_linux_pidfd(namespace_init_pidfd, signal.SIGKILL)
                except BaseException as exc:
                    teardown_errors.append(str(exc))
                try:
                    supervisor.kill()
                except ProcessLookupError:
                    pass
                reason = (
                    "validated runner supervisor did not complete bounded namespace teardown"
                )
                teardown_errors.append(reason)
                try:
                    supervisor_stdout, supervisor_stderr = supervisor.communicate(
                        timeout=1.0
                    )
                except subprocess.TimeoutExpired:
                    supervisor_stdout, supervisor_stderr = "", ""
                return {
                    "returncode": 125,
                    "timed_out": outer_timeout,
                    "cancelled": cancellation_requested,
                    "stdout": "",
                    "stderr": "\n".join(
                        item
                        for item in (
                            supervisor_stderr or "",
                            "; ".join(dict.fromkeys(teardown_errors)),
                        )
                        if item
                    ),
                    "containment_error": "; ".join(
                        dict.fromkeys(teardown_errors)
                    ),
                    "supervisor": "linux_pid_namespace_v1",
                }
            try:
                supervisor_stdout, supervisor_stderr = supervisor.communicate(
                    timeout=0.1
                )
                break
            except subprocess.TimeoutExpired:
                continue

        namespace_exited = wait_linux_pidfd_exit(
            namespace_init_pidfd,
            timeout_seconds=1.0,
        )
        if not namespace_exited:
            try:
                signal_linux_pidfd(namespace_init_pidfd, signal.SIGKILL)
            except BaseException as exc:
                teardown_errors.append(str(exc))
            namespace_exited = wait_linux_pidfd_exit(
                namespace_init_pidfd,
                timeout_seconds=2.0,
            )
        if not namespace_exited:
            reason = "validated runner namespace init remained alive after teardown"
            teardown_errors.append(reason)
            return {
                "returncode": 125,
                "timed_out": outer_timeout,
                "cancelled": cancellation_requested,
                "stdout": "",
                "stderr": "\n".join(
                    item
                    for item in (
                        supervisor_stderr or "",
                        "; ".join(dict.fromkeys(teardown_errors)),
                    )
                    if item
                ),
                "containment_error": "; ".join(dict.fromkeys(teardown_errors)),
                "supervisor": "linux_pid_namespace_v1",
            }

        if forced_namespace_teardown:
            containment_error = "; ".join(dict.fromkeys(teardown_errors))
            return {
                "returncode": -signal.SIGKILL if not containment_error else 125,
                "timed_out": outer_timeout,
                "cancelled": cancellation_requested,
                "stdout": "",
                "stderr": "\n".join(
                    item for item in (supervisor_stderr or "", containment_error) if item
                ),
                "containment_error": containment_error,
                "supervisor": "linux_pid_namespace_v1",
            }

        try:
            payload = json.loads(supervisor_stdout)
        except (TypeError, json.JSONDecodeError):
            reason = "validated runner supervisor returned an invalid containment record"
            return {
                "returncode": 125,
                "timed_out": outer_timeout,
                "cancelled": cancellation_requested,
                "stdout": "",
                "stderr": "\n".join(
                    item for item in (supervisor_stderr or "", reason) if item
                ),
                "containment_error": reason,
                "supervisor": "linux_pid_namespace_v1",
            }
        if not isinstance(payload, dict):
            raise RuntimeError("validated runner supervisor record must be an object")
        payload["returncode"] = int(payload.get("returncode", 125))
        payload["timed_out"] = bool(payload.get("timed_out", False) or outer_timeout)
        payload["cancelled"] = bool(
            payload.get("cancelled", False) or cancellation_requested
        )
        payload["stdout"] = str(payload.get("stdout", "") or "")
        payload["stderr"] = "\n".join(
            item
            for item in (
                str(payload.get("stderr", "") or ""),
                supervisor_stderr or "",
            )
            if item
        )
        payload["containment_error"] = str(
            payload.get("containment_error", "") or ""
        )
        protocol_errors: list[str] = []
        if payload.get("protocol_nonce") != protocol_nonce:
            protocol_errors.append("validated runner supervisor nonce mismatch")
        if payload.get("supervisor") != "linux_pid_namespace_v1":
            protocol_errors.append("validated runner supervisor kind mismatch")
        expected_supervisor_failure = bool(
            payload["timed_out"]
            or payload["cancelled"]
            or payload["containment_error"]
        )
        if supervisor.returncode != 0 and not expected_supervisor_failure:
            protocol_errors.append(
                f"validated runner supervisor exited with code {supervisor.returncode}"
            )
        if supervisor.returncode == 0 and expected_supervisor_failure:
            protocol_errors.append(
                "validated runner supervisor reported failure with a successful exit"
            )
        if payload["timed_out"] or payload["cancelled"]:
            payload["returncode"] = (
                payload["returncode"] if payload["returncode"] != 0 else 125
            )
        if protocol_errors:
            reason = "; ".join(dict.fromkeys(protocol_errors))
            payload["returncode"] = (
                payload["returncode"] if payload["returncode"] != 0 else 125
            )
            payload["containment_error"] = "; ".join(
                item
                for item in (payload["containment_error"], reason)
                if item
            )
            payload["stderr"] = "\n".join(
                item for item in (payload["stderr"], reason) if item
            )
        return payload
    finally:
        os.close(namespace_init_pidfd)


async def execute_validated_runner_profile(
    job_id: str,
    request_data: dict[str, Any],
    *,
    require_customer_submission_allowed: bool = True,
) -> dict[str, Any]:
    if not settings.api_validated_runner_enabled:
        raise NotImplementedError(
            "API validated runner execution is disabled; enabling it requires an "
            "operator-approved profile and a namespace-qualified host runtime receipt."
        )
    runtime_qualification = require_validated_runner_namespace_runtime()
    runtime_qualification_record = _runtime_qualification_record(
        runtime_qualification
    )

    profile_id = _safe_profile_id(request_data.get("runner_profile_id"))
    profile = _load_profile(profile_id)
    execution_contract = validate_runner_profile_execution_contract(
        profile,
        require_explicit=True,
    )
    if (
        require_customer_submission_allowed
        and execution_contract.get("customer_submission_allowed") is not True
    ):
        raise PermissionError(
            f"runner profile does not allow customer submissions: {profile_id}"
        )
    execution_evidence = build_validated_runner_execution_evidence(
        profile_id=profile_id,
        execution_contract=execution_contract,
        request_data=request_data,
    )
    results_dir = _results_dir(job_id)
    results_dir.mkdir(parents=True, exist_ok=True)
    request_json_path = results_dir / "request.json"
    atomic_write_text_file(
        request_json_path,
        json.dumps(
            sanitize_request_for_ledger(request_data),
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
    )

    result_file_template = str(profile.get("result_file_template", "{job_results_dir}/runner_result.json") or "")
    evidence_bundle_template = str(profile.get("evidence_bundle_template", "") or "").strip()
    has_evidence_bundle_template = bool(evidence_bundle_template)
    context = {
        "job_id": job_id,
        "job_results_dir": str(results_dir),
        "request_json_path": str(request_json_path),
        "result_file": _render_template(result_file_template, {"job_id": job_id, "job_results_dir": str(results_dir), "request_json_path": str(request_json_path)}),
    }
    context["result_file"] = _render_template(result_file_template, context)
    if has_evidence_bundle_template:
        context["evidence_bundle"] = _render_template(
            evidence_bundle_template,
            {
                "job_id": job_id,
                "job_results_dir": str(results_dir),
                "request_json_path": str(request_json_path),
                "result_file": context["result_file"],
            },
        )

    _require_output_within_results_dir(
        context["result_file"],
        results_dir=results_dir,
        label="result_file",
    )
    if has_evidence_bundle_template:
        _require_output_within_results_dir(
            context["evidence_bundle"],
            results_dir=results_dir,
            label="evidence_bundle",
        )

    args = profile.get("arguments", [])
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ValueError("runner profile arguments must be a list of strings")

    script = _runner_script(profile)
    readiness_record = validate_profile_readiness(profile, runner_script_path=script)
    command = [sys.executable, script] + [_render_template(item, context) for item in args]

    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    t0 = time.time()
    timeout_seconds = int(settings.api_validated_runner_timeout_seconds)
    cancellation_event = threading.Event()
    command_task = asyncio.create_task(
        asyncio.to_thread(
            _run_profile_command,
            command,
            timeout_seconds=timeout_seconds,
            cancellation_event=cancellation_event,
        )
    )
    try:
        completed = await asyncio.shield(command_task)
    except asyncio.CancelledError as cancellation:
        cancellation_event.set()
        # Do not return control to the lease manager until the namespace has
        # been torn down. Repeated Task.cancel() calls must not cancel the
        # to_thread Future while its OS process is still being contained.
        while not command_task.done():
            try:
                await asyncio.shield(command_task)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        if command_task.done() and not command_task.cancelled():
            try:
                command_task.result()
            except BaseException:
                pass
        raise cancellation
    duration = max(time.time() - t0, 0.0)
    ended = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    result_file = Path(context["result_file"])
    evidence_bundle_path_value = context.get("evidence_bundle", "")
    evidence_bundle_path = Path(evidence_bundle_path_value) if evidence_bundle_path_value else None
    command_ok = bool(
        completed["returncode"] == 0
        and not completed.get("timed_out")
        and not completed.get("cancelled")
        and not completed.get("containment_error")
    )
    execution_record = {
        "adapter_version": "api_validated_runner_v1",
        "job_id": job_id,
        "profile_id": profile_id,
        "runner_script": str(profile.get("runner_script", "")),
        "profile_readiness": readiness_record,
        "profile_execution_contract": execution_contract,
        EXECUTION_EVIDENCE_PROVENANCE_KEY: execution_evidence,
        "command": command,
        "returncode": int(completed["returncode"]),
        "ok": command_ok,
        "timed_out": bool(completed["timed_out"]),
        "cancelled": bool(completed.get("cancelled", False)),
        "timeout_seconds": timeout_seconds,
        "process_group_killed_on_timeout": bool(completed["timed_out"]),
        "descendant_tree_contained": not bool(completed.get("containment_error")),
        "descendant_containment_error": str(
            completed.get("containment_error", "") or ""
        ),
        "runner_supervisor": str(completed.get("supervisor", "") or ""),
        "started_at_utc": started,
        "ended_at_utc": ended,
        "duration_sec": float(duration),
        "stdout_tail": "\n".join(str(completed["stdout"] or "").splitlines()[-40:]),
        "stderr_tail": "\n".join(str(completed["stderr"] or "").splitlines()[-40:]),
        "result_file": str(result_file),
        "evidence_bundle_template": evidence_bundle_template or "",
        "native_evidence_bundle": str(evidence_bundle_path) if evidence_bundle_path else "",
        "native_evidence_bundle_sha256": "",
        **runtime_qualification_record,
        "claim_boundary": (
            "Validated runner adapter only. It executes an operator-approved local profile and records provenance; "
            "scientific claim scope remains governed by the profile and downstream gates."
        ),
    }
    execution_record_path = results_dir / "runner_execution.json"
    _write_json_artifact(execution_record_path, execution_record)

    if not command_ok:
        error = (
            f"validated_runner_timeout:{timeout_seconds}s"
            if completed["timed_out"]
            else execution_record["stderr_tail"] or "runner failed"
        )
        _write_status(
            job_id,
            {
                "job_id": job_id,
                "status": "failed",
                "error": error,
                "runner_execution": str(execution_record_path),
                **runtime_qualification_record,
            },
        )
        raise RuntimeError(f"validated runner failed for profile {profile_id}; see {execution_record_path}")
    result_file_sha256 = _sha256_confined_result_file(
        result_file,
        results_dir=results_dir,
    )

    native_bundle_record: dict[str, str] = {}
    if has_evidence_bundle_template:
        if evidence_bundle_path is None or not evidence_bundle_path.exists() or not evidence_bundle_path.is_file():
            error = (
                f"validated_runner_missing_native_evidence_bundle:{evidence_bundle_path_value}"
            )
            execution_record["native_evidence_bundle_error"] = error
            _write_json_artifact(execution_record_path, execution_record)
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error,
                    "runner_execution": str(execution_record_path),
                    **runtime_qualification_record,
                },
            )
            raise FileNotFoundError(
                f"validated runner did not produce expected native evidence bundle: {evidence_bundle_path_value}"
            )
        try:
            pinned_evidence = _read_confined_result_bytes(
                evidence_bundle_path,
                results_dir=results_dir,
                maximum_bytes=64 * 1024 * 1024,
                label="validated runner native evidence bundle",
            )
            raw_payload = json.loads(pinned_evidence)
        except (OSError, PermissionError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            error = (
                f"validated_runner_native_evidence_bundle_not_json:{evidence_bundle_path_value}"
            )
            execution_record["native_evidence_bundle_error"] = error
            _write_json_artifact(execution_record_path, execution_record)
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error,
                    "runner_execution": str(execution_record_path),
                    **runtime_qualification_record,
                },
            )
            raise PermissionError(
                f"native evidence bundle is not valid JSON: {evidence_bundle_path_value}"
            ) from exc
        if not isinstance(raw_payload, dict):
            error = (
                f"validated_runner_native_evidence_bundle_not_object:{evidence_bundle_path_value}"
            )
            execution_record["native_evidence_bundle_error"] = error
            _write_json_artifact(execution_record_path, execution_record)
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error,
                    "runner_execution": str(execution_record_path),
                    **runtime_qualification_record,
                },
            )
            raise PermissionError(
                f"native evidence bundle must be a JSON object: {evidence_bundle_path_value}"
            )
        try:
            bundle = EvidenceBundle(**raw_payload)
        except (ContractValidationError, TypeError) as exc:
            error = (
                f"validated_runner_native_evidence_bundle_invalid:{exc}"
            )
            execution_record["native_evidence_bundle_error"] = error
            _write_json_artifact(execution_record_path, execution_record)
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error,
                    "runner_execution": str(execution_record_path),
                    **runtime_qualification_record,
                },
            )
            raise PermissionError(
                f"native evidence bundle failed EvidenceBundle validation: {exc}"
            ) from exc
        bundle_fingerprint = bundle.fingerprint()
        native_bundle_record = {
            "evidence_bundle": str(evidence_bundle_path),
            "evidence_bundle_sha256": bundle_fingerprint,
            "evidence_bundle_source": "validated_runner_native",
        }
        execution_record["native_evidence_bundle"] = str(evidence_bundle_path)
        execution_record["native_evidence_bundle_sha256"] = bundle_fingerprint
        _write_json_artifact(execution_record_path, execution_record)

    status_payload = {
        "job_id": job_id,
        "status": "completed",
        "runner_profile_id": profile_id,
        "runner_profile_claim_scope": readiness_record["claim_scope"],
        "result_file": str(result_file),
        "result_file_sha256": result_file_sha256,
        "runner_execution": str(execution_record_path),
        EXECUTION_EVIDENCE_PROVENANCE_KEY: execution_evidence,
        **runtime_qualification_record,
    }
    status_payload.update(native_bundle_record)
    _write_status(job_id, status_payload)
    return status_payload
