"""Shared stdlib-only PID-namespace process controller.

The caller owns request authorization, source admission and runtime qualification.
This module preserves the validated runner's nonce/start-gate/pidfd cleanup
protocol. Explicit resource envelopes add per-process limits; they never stand
in for a hard aggregate resident-memory or stored-output quota.
"""
from __future__ import annotations

import json
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import os
import threading
import time
from typing import Any, Callable

from api.linux_runner_supervisor import (
    ResourceContainmentUnavailable as ResourceContainmentUnavailable,
    linux_pid_namespace_launcher,
    open_linux_pid_namespace_init,
    require_linux_runner_supervisor_support,
    signal_linux_pidfd,
    validate_resource_limits,
    wait_linux_pidfd_exit,
)


def resource_capabilities() -> dict[str, Any]:
    return {
        "wall_seconds": True, "cpu_seconds": True,
        "address_space_bytes": True, "file_bytes": True,
        "cpu_affinity": True, "capture_bytes": True, "tree_bytes": True,
        "memory_bytes": False, "output_bytes": False,
        "cpu_limit_scope": "hard per process including its threads; not aggregate across descendants",
        "address_space_scope": "hard virtual address space; not a resident-memory cap",
        "file_scope": "hard per-file size; not cumulative stored-output quota",
        "capture_scope": "bounded parent read per stream; size-triggered stop is sampled",
        "tree_scope": "sampled file-size total; possible overshoot; no hard filesystem quota",
        "wall_scope": "runner wall timeout with existing separately bounded cleanup",
        "availability": "requires Linux namespace/runtime qualification and actual kernel admission",
    }


def run_contained(command: list[str], *, cwd: Path, environment: dict[str, str],
                  timeout_seconds: int, cancellation_event: threading.Event | None = None,
                  limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a caller-admitted fixed child; no arbitrary-command public surface.

    limits=None preserves the legacy controller and supervisor wire behavior.
    Unsupported strict resource requests fail before any namespace is spawned.
    """
    admitted_limits = validate_resource_limits(limits)
    if not isinstance(command, list) or not command or any(type(v) is not str or not v or "\0" in v for v in command):
        raise ValueError("a nonempty fixed string command is required")
    if not isinstance(environment, dict) or any(type(k) is not str or type(v) is not str or "\0" in k or "\0" in v for k, v in environment.items()):
        raise ValueError("explicit string child environment required")
    cwd = Path(cwd)
    if not cwd.is_absolute() or not cwd.is_dir():
        raise ValueError("existing absolute execution directory required")
    if type(timeout_seconds) is not int or timeout_seconds < 1:
        raise ValueError("positive integer runner wall timeout required")
    if admitted_limits is not None and "wall_seconds" in admitted_limits:
        timeout_seconds = min(timeout_seconds, admitted_limits["wall_seconds"])
    start_admitted = False
    def record_start():
        nonlocal start_admitted
        start_admitted = True
    metadata_hook = {} if admitted_limits is None else {"_on_start_admitted": record_start}
    payload = _run_pid_namespace_command(
        command, cwd=cwd, environment=environment, timeout_seconds=timeout_seconds,
        cancellation_event=cancellation_event, limits=admitted_limits, **metadata_hook,
    )
    if admitted_limits is not None:
        payload["runner_start_admitted"] = start_admitted
        payload["resource_capabilities"] = resource_capabilities()
        unknown_usage = {"child_cpu_seconds": None, "child_peak_rss_bytes": None, "measurement_complete": False}
        if payload.get("containment_error"):
            # A nonce/teardown failure also prevents trusting claimed resource
            # counters. Never let an unauthenticated zero refund reserved work.
            payload["resource_usage"] = unknown_usage
            payload["applied_resources"] = None
        else:
            payload.setdefault("resource_usage", unknown_usage)
        payload["containment_evidence"] = {
            "mechanism": payload.get("supervisor"),
            "namespace_exit_verified": not bool(payload.get("containment_error")),
            "runtime_qualification_claimed_by_process_helper": False,
        }
    return payload


def _run_pid_namespace_command(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: int,
    cancellation_event: threading.Event | None = None,
    limits: dict[str, Any] | None = None,
    _on_start_admitted: Callable[[], None] | None = None,
) -> dict[str, Any]:
    require_linux_runner_supervisor_support()
    namespace_launcher = linux_pid_namespace_launcher()
    bounded_timeout = max(1, int(timeout_seconds))
    protocol_nonce = secrets.token_hex(32)
    config_payload = {
        "command": command,
        "cwd": str(cwd),
        "timeout_seconds": bounded_timeout,
        "protocol_nonce": protocol_nonce,
    }
    if limits is not None:
        config_payload["resource_limits"] = limits
    config = json.dumps(config_payload, separators=(",", ":")).encode("utf-8")
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
                cwd=str(cwd),
                text=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
                env=environment,
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
            if _on_start_admitted is not None:
                _on_start_admitted()
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
            or payload.get("resource_error")
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
