from __future__ import annotations

import ctypes
import errno
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_PR_SET_CHILD_SUBREAPER = 36
_PR_GET_CHILD_SUBREAPER = 37
_PR_GET_DUMPABLE = 3
_PR_SET_DUMPABLE = 4
_PR_SET_NO_NEW_PRIVS = 38
_PR_GET_NO_NEW_PRIVS = 39
_PROTOCOL_LIMIT_BYTES = 1024 * 1024
_POLL_INTERVAL_SECONDS = 0.02
_DEFAULT_CLEANUP_SECONDS = 3.0
_SUPERVISOR_KIND = "linux_pid_namespace_v1"
_START_TOKEN = b"R"
_cancel_requested = False


class LinuxRunnerContainmentUnavailable(RuntimeError):
    """Raised before runner spawn when Linux descendant containment is unavailable."""


@dataclass(frozen=True)
class _ProcessIdentity:
    pid: int
    ppid: int
    state: str
    start_time: int


def _libc() -> ctypes.CDLL:
    libc = ctypes.CDLL(None, use_errno=True)
    if getattr(libc, "prctl", None) is None:
        raise LinuxRunnerContainmentUnavailable("Linux prctl is unavailable")
    return libc


def _read_proc_stat(pid: int) -> _ProcessIdentity:
    try:
        payload = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ProcessLookupError(pid) from exc
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ESRCH}:
            raise ProcessLookupError(pid) from exc
        raise LinuxRunnerContainmentUnavailable(
            f"/proc/{pid}/stat is unreadable"
        ) from exc
    closing_paren = payload.rfind(")")
    if closing_paren < 0:
        raise LinuxRunnerContainmentUnavailable(f"malformed /proc/{pid}/stat")
    fields = payload[closing_paren + 2 :].split()
    if len(fields) < 20:
        raise LinuxRunnerContainmentUnavailable(f"incomplete /proc/{pid}/stat")
    try:
        return _ProcessIdentity(
            pid=pid,
            state=fields[0],
            ppid=int(fields[1]),
            start_time=int(fields[19]),
        )
    except (TypeError, ValueError) as exc:
        raise LinuxRunnerContainmentUnavailable(f"invalid /proc/{pid}/stat") from exc


def require_linux_runner_supervisor_support() -> None:
    """Check required containment primitives without changing process state."""

    if sys.platform != "linux":
        raise LinuxRunnerContainmentUnavailable(
            "validated runners require Linux descendant containment"
        )
    if not Path("/proc/self/stat").is_file():
        raise LinuxRunnerContainmentUnavailable(
            "validated runners require a readable Linux /proc process table"
        )
    _read_proc_stat(os.getpid())
    _libc()
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise LinuxRunnerContainmentUnavailable(
            "validated runners require Linux pidfd signaling"
        )
    try:
        pidfd = os.pidfd_open(os.getpid(), 0)
    except OSError as exc:
        raise LinuxRunnerContainmentUnavailable(
            "validated runner pidfd signaling is unavailable"
        ) from exc
    else:
        os.close(pidfd)
    # Exercise the process-table backend before any runner is spawned. Entries
    # hidden by procfs policy are ignored, while malformed/read errors for
    # visible entries still fail closed.
    _process_table()


def linux_pid_namespace_launcher() -> str:
    """Resolve the trusted launcher used to create a private PID namespace."""

    require_linux_runner_supervisor_support()
    launcher = shutil.which("unshare", path=os.defpath)
    if launcher is None:
        raise LinuxRunnerContainmentUnavailable(
            "validated runners require the util-linux unshare launcher"
        )
    return launcher


def _require_namespace_init() -> None:
    """Fail before runner spawn unless this supervisor is namespace PID 1."""

    identity = _read_proc_stat(os.getpid())
    if os.getpid() != 1 or identity.pid != 1 or identity.ppid != 0:
        raise LinuxRunnerContainmentUnavailable(
            "validated runner supervisor must be PID 1 in a private PID namespace"
        )


def _read_proc_status(pid: int) -> dict[str, str]:
    try:
        lines = Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ProcessLookupError(pid) from exc
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ESRCH}:
            raise ProcessLookupError(pid) from exc
        raise LinuxRunnerContainmentUnavailable(
            f"/proc/{pid}/status is unreadable"
        ) from exc
    status: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition(":")
        if separator:
            status[key] = value.strip()
    return status


def _harden_namespace_supervisor() -> None:
    """Remove runner process-control authority before any runner is spawned."""

    libc = _libc()
    if libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise LinuxRunnerContainmentUnavailable(
            f"PR_SET_DUMPABLE failed: {os.strerror(error_number)}"
        )
    if libc.prctl(_PR_GET_DUMPABLE, 0, 0, 0, 0) != 0:
        raise LinuxRunnerContainmentUnavailable(
            "validated runner supervisor remained ptrace-accessible"
        )
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise LinuxRunnerContainmentUnavailable(
            f"PR_SET_NO_NEW_PRIVS failed: {os.strerror(error_number)}"
        )
    if libc.prctl(_PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) != 1:
        raise LinuxRunnerContainmentUnavailable(
            "validated runner no-new-privileges state could not be verified"
        )
    status = _read_proc_status(os.getpid())
    try:
        effective_capabilities = int(status.get("CapEff", "-1"), 16)
    except ValueError as exc:
        raise LinuxRunnerContainmentUnavailable(
            "validated runner capability state is malformed"
        ) from exc
    if effective_capabilities != 0:
        raise LinuxRunnerContainmentUnavailable(
            "validated runner supervisor must have zero effective capabilities"
        )


def open_linux_pid_namespace_init(
    launcher_pid: int,
    *,
    timeout_seconds: float = 2.0,
) -> int:
    """Pin the launcher's namespace-init child before the runner start gate opens."""

    deadline = time.monotonic() + max(timeout_seconds, 0.1)
    children_path = Path(
        f"/proc/{launcher_pid}/task/{launcher_pid}/children"
    )
    while time.monotonic() < deadline:
        try:
            child_ids = [int(item) for item in children_path.read_text().split()]
        except FileNotFoundError as exc:
            raise LinuxRunnerContainmentUnavailable(
                "validated runner namespace launcher exited before initialization"
            ) from exc
        except (OSError, ValueError) as exc:
            raise LinuxRunnerContainmentUnavailable(
                "validated runner namespace child inventory is unavailable"
            ) from exc
        if len(child_ids) > 1:
            raise LinuxRunnerContainmentUnavailable(
                "validated runner namespace launcher created unexpected children"
            )
        if child_ids:
            child_pid = child_ids[0]
            identity = _read_proc_stat(child_pid)
            status = _read_proc_status(child_pid)
            namespace_pids = status.get("NSpid", "").split()
            if identity.ppid != launcher_pid or not namespace_pids:
                raise LinuxRunnerContainmentUnavailable(
                    "validated runner namespace-init ancestry is invalid"
                )
            try:
                if int(namespace_pids[-1]) != 1:
                    raise ValueError
            except ValueError as exc:
                raise LinuxRunnerContainmentUnavailable(
                    "validated runner supervisor is not namespace PID 1"
                ) from exc
            try:
                pidfd = os.pidfd_open(child_pid, 0)
            except OSError as exc:
                raise LinuxRunnerContainmentUnavailable(
                    "validated runner namespace-init pidfd is unavailable"
                ) from exc
            try:
                observed = _read_proc_stat(child_pid)
                if (
                    observed.ppid != launcher_pid
                    or observed.start_time != identity.start_time
                ):
                    raise LinuxRunnerContainmentUnavailable(
                        "validated runner namespace-init identity changed"
                    )
            except Exception:
                os.close(pidfd)
                raise
            return pidfd
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise LinuxRunnerContainmentUnavailable(
        "validated runner namespace-init did not appear before the start deadline"
    )


def signal_linux_pidfd(pidfd: int, sig: int) -> None:
    """Signal a pinned namespace-init identity."""

    try:
        signal.pidfd_send_signal(pidfd, sig, None, 0)
    except ProcessLookupError:
        return
    except OSError as exc:
        if exc.errno != errno.ESRCH:
            raise LinuxRunnerContainmentUnavailable(
                "validated runner namespace-init signal failed"
            ) from exc


def wait_linux_pidfd_exit(pidfd: int, *, timeout_seconds: float) -> bool:
    """Return only after the pinned namespace init has exited."""

    poller = select.poll()
    poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
    timeout_ms = max(0, int(timeout_seconds * 1000))
    return bool(poller.poll(timeout_ms))


def _become_child_subreaper() -> None:
    libc = _libc()
    if libc.prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        error_number = ctypes.get_errno()
        raise LinuxRunnerContainmentUnavailable(
            f"PR_SET_CHILD_SUBREAPER failed: {os.strerror(error_number)}"
        )
    observed = ctypes.c_int(0)
    if libc.prctl(
        _PR_GET_CHILD_SUBREAPER,
        ctypes.byref(observed),
        0,
        0,
        0,
    ) != 0:
        error_number = ctypes.get_errno()
        raise LinuxRunnerContainmentUnavailable(
            f"PR_GET_CHILD_SUBREAPER failed: {os.strerror(error_number)}"
        )
    if observed.value != 1:
        raise LinuxRunnerContainmentUnavailable(
            "Linux child-subreaper state could not be verified"
        )


def _process_table() -> dict[int, _ProcessIdentity]:
    try:
        entries = list(Path("/proc").iterdir())
    except OSError as exc:
        raise LinuxRunnerContainmentUnavailable(
            "Linux /proc process table became unavailable"
        ) from exc
    table: dict[int, _ProcessIdentity] = {}
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            identity = _read_proc_stat(pid)
        except ProcessLookupError:
            continue
        except LinuxRunnerContainmentUnavailable as exc:
            cause = exc.__cause__
            if isinstance(cause, OSError) and cause.errno in {
                errno.EACCES,
                errno.EPERM,
            }:
                continue
            raise
        table[pid] = identity
    return table


def _descendants(root_pid: int) -> dict[int, _ProcessIdentity]:
    table = _process_table()
    descendants: dict[int, _ProcessIdentity] = {}
    parents = {root_pid}
    while parents:
        children = {
            pid: identity
            for pid, identity in table.items()
            if pid not in descendants and identity.ppid in parents
        }
        if not children:
            break
        descendants.update(children)
        parents = set(children)
    return descendants


def _signal_identity(identity: _ProcessIdentity, sig: int) -> None:
    try:
        pidfd = os.pidfd_open(identity.pid, 0)
    except ProcessLookupError:
        return
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return
        raise LinuxRunnerContainmentUnavailable(
            f"pidfd_open failed for supervised descendant {identity.pid}"
        ) from exc
    try:
        try:
            current = _read_proc_stat(identity.pid)
        except ProcessLookupError:
            return
        if current.start_time != identity.start_time:
            return
        try:
            signal.pidfd_send_signal(pidfd, sig, None, 0)
        except ProcessLookupError:
            return
        except OSError as exc:
            if exc.errno != errno.ESRCH:
                raise LinuxRunnerContainmentUnavailable(
                    f"pidfd signal failed for supervised descendant {identity.pid}"
                ) from exc
    finally:
        os.close(pidfd)


def _reap_available_children(root_pid: int, *, exclude_pid: int) -> None:
    direct_children = [
        identity.pid
        for identity in _process_table().values()
        if identity.ppid == root_pid and identity.pid != exclude_pid
    ]
    for pid in direct_children:
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            continue
        except InterruptedError:
            continue


def _freeze_descendants(root_pid: int, *, deadline: float) -> None:
    stable_snapshot: set[tuple[int, int]] | None = None
    stable_rounds = 0
    while time.monotonic() < deadline:
        descendants = _descendants(root_pid)
        live = {
            pid: identity
            for pid, identity in descendants.items()
            if identity.state not in {"X", "Z"}
        }
        if not live:
            return
        for identity in live.values():
            _signal_identity(identity, signal.SIGSTOP)
        time.sleep(_POLL_INTERVAL_SECONDS)
        observed = _descendants(root_pid)
        runnable = {
            (identity.pid, identity.start_time)
            for identity in observed.values()
            if identity.state not in {"T", "t", "X", "Z"}
        }
        snapshot = {
            (identity.pid, identity.start_time)
            for identity in observed.values()
            if identity.state not in {"X", "Z"}
        }
        if not runnable and snapshot == stable_snapshot:
            stable_rounds += 1
        else:
            stable_rounds = 0
        stable_snapshot = snapshot
        if stable_rounds >= 1:
            return


def _kill_and_reap_descendants(
    root_pid: int,
    runner: subprocess.Popen[bytes],
    *,
    cleanup_seconds: float,
) -> tuple[int, str]:
    deadline = time.monotonic() + max(cleanup_seconds, 0.5)
    freeze_deadline = min(deadline, time.monotonic() + max(cleanup_seconds / 2.0, 0.25))
    containment_errors: list[str] = []
    try:
        _freeze_descendants(root_pid, deadline=freeze_deadline)
    except LinuxRunnerContainmentUnavailable as exc:
        containment_errors.append(str(exc))

    runner_returncode = runner.poll()
    while time.monotonic() < deadline:
        try:
            descendants = _descendants(root_pid)
        except LinuxRunnerContainmentUnavailable as exc:
            containment_errors.append(str(exc))
            break
        for identity in descendants.values():
            if identity.state not in {"X", "Z"}:
                try:
                    _signal_identity(identity, signal.SIGKILL)
                except LinuxRunnerContainmentUnavailable as exc:
                    containment_errors.append(str(exc))
        if runner_returncode is None:
            try:
                runner_returncode = runner.wait(timeout=_POLL_INTERVAL_SECONDS)
            except subprocess.TimeoutExpired:
                pass
        _reap_available_children(root_pid, exclude_pid=runner.pid)
        remaining = _descendants(root_pid)
        if not remaining:
            if runner_returncode is None:
                runner_returncode = runner.poll()
            return (
                int(runner_returncode if runner_returncode is not None else -signal.SIGKILL),
                "; ".join(dict.fromkeys(containment_errors)),
            )
        time.sleep(_POLL_INTERVAL_SECONDS)

    try:
        remaining = _descendants(root_pid)
    except LinuxRunnerContainmentUnavailable as exc:
        containment_errors.append(str(exc))
        remaining = {}
    if remaining:
        identities = ",".join(
            f"{item.pid}:{item.start_time}" for item in remaining.values()
        )
        containment_errors.append(
            f"supervised descendants remained after bounded cleanup: {identities}"
        )
    if runner_returncode is None:
        runner_returncode = runner.poll()
    return (
        int(runner_returncode if runner_returncode is not None else -signal.SIGKILL),
        "; ".join(dict.fromkeys(containment_errors)),
    )


def _read_config(config_fd: int) -> dict[str, Any]:
    with os.fdopen(config_fd, "rb", closefd=True) as handle:
        raw = handle.read(_PROTOCOL_LIMIT_BYTES + 1)
    if len(raw) > _PROTOCOL_LIMIT_BYTES:
        raise ValueError("runner supervisor configuration exceeds protocol limit")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("runner supervisor configuration must be an object")
    command = payload.get("command")
    if not isinstance(command, list) or not command or not all(
        isinstance(item, str) and item for item in command
    ):
        raise ValueError("runner supervisor command must be a non-empty string list")
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_dir():
        raise ValueError("runner supervisor cwd must be an existing directory")
    timeout_seconds = payload.get("timeout_seconds")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise ValueError("runner supervisor timeout_seconds must be an integer")
    protocol_nonce = payload.get("protocol_nonce")
    if not isinstance(protocol_nonce, str) or len(protocol_nonce) != 64:
        raise ValueError("runner supervisor protocol nonce is invalid")
    try:
        int(protocol_nonce, 16)
    except ValueError as exc:
        raise ValueError("runner supervisor protocol nonce is invalid") from exc
    payload["timeout_seconds"] = max(timeout_seconds, 1)
    return payload


def _wait_for_start(start_fd: int) -> None:
    with os.fdopen(start_fd, "rb", closefd=True) as handle:
        token = handle.read(2)
    if token != _START_TOKEN:
        raise LinuxRunnerContainmentUnavailable(
            "validated runner start gate was not authorized"
        )


def _handle_cancel(_signum: int, _frame: Any) -> None:
    global _cancel_requested
    _cancel_requested = True


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()


def _failure_payload(
    message: str,
    *,
    cancelled: bool = False,
    protocol_nonce: str = "",
) -> dict[str, Any]:
    return {
        "returncode": 125,
        "timed_out": False,
        "cancelled": cancelled,
        "stdout": "",
        "stderr": message,
        "containment_error": message,
        "supervisor": _SUPERVISOR_KIND,
        "protocol_nonce": protocol_nonce,
    }


def supervise(config_fd: int, start_fd: int) -> tuple[dict[str, Any], bool]:
    global _cancel_requested
    _cancel_requested = False
    signal.signal(signal.SIGTERM, _handle_cancel)
    signal.signal(signal.SIGINT, _handle_cancel)
    require_linux_runner_supervisor_support()
    _require_namespace_init()
    _become_child_subreaper()
    _harden_namespace_supervisor()
    config = _read_config(config_fd)
    protocol_nonce = config["protocol_nonce"]
    _wait_for_start(start_fd)
    if _cancel_requested:
        return (
            _failure_payload(
                "runner cancelled before spawn",
                cancelled=True,
                protocol_nonce=protocol_nonce,
            ),
            False,
        )

    command = config["command"]
    cwd = config["cwd"]
    timeout_seconds = config["timeout_seconds"]
    runner: subprocess.Popen[bytes] | None = None
    with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(
        mode="w+b"
    ) as stderr_file:
        try:
            runner = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                shell=False,
                start_new_session=True,
                env=dict(os.environ),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return (
                _failure_payload(
                    f"validated runner spawn failed: {exc}",
                    protocol_nonce=protocol_nonce,
                ),
                False,
            )

        timed_out = False
        cancelled = False
        runner_returncode: int | None = None
        deadline = time.monotonic() + timeout_seconds
        while True:
            if _cancel_requested:
                cancelled = True
                break
            runner_returncode = runner.poll()
            if runner_returncode is not None:
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(_POLL_INTERVAL_SECONDS)

        contained_returncode, containment_error = _kill_and_reap_descendants(
            os.getpid(),
            runner,
            cleanup_seconds=_DEFAULT_CLEANUP_SECONDS,
        )
        if runner_returncode is None:
            runner_returncode = contained_returncode
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read().decode("utf-8", errors="replace")
        stderr = stderr_file.read().decode("utf-8", errors="replace")

    if containment_error:
        stderr = "\n".join(item for item in (stderr, containment_error) if item)
        returncode = 125
    elif timed_out or cancelled:
        returncode = int(runner_returncode) if int(runner_returncode) != 0 else 125
    else:
        returncode = int(runner_returncode)
    return (
        {
            "returncode": returncode,
            "timed_out": timed_out,
            "cancelled": cancelled,
            "stdout": stdout,
            "stderr": stderr,
            "containment_error": containment_error,
            "supervisor": _SUPERVISOR_KIND,
            "protocol_nonce": protocol_nonce,
        },
        bool(containment_error or timed_out or cancelled),
    )


def main() -> int:
    if (
        len(sys.argv) != 5
        or sys.argv[1] != "--config-fd"
        or sys.argv[3] != "--start-fd"
    ):
        _emit(
            _failure_payload(
                "usage: linux_runner_supervisor.py --config-fd FD --start-fd FD"
            )
        )
        return 125
    try:
        config_fd = int(sys.argv[2])
        start_fd = int(sys.argv[4])
        payload, failed = supervise(config_fd, start_fd)
    except (LinuxRunnerContainmentUnavailable, OSError, ValueError, json.JSONDecodeError) as exc:
        _emit(_failure_payload(f"validated runner containment unavailable: {exc}"))
        return 125
    _emit(payload)
    return 125 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
