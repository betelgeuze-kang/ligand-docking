"""Standalone Linux subreaper for one external-oracle process tree.

The parent executes this file from a pinned ``/proc/self/fd`` descriptor.  It
stays alive while the solver runs, adopts double-forked or ``setsid``
descendants, kills every remaining child, and only then mirrors the solver's
exit status.  It deliberately imports no Betelgeuze package.
"""

from __future__ import annotations

import ctypes
import os
import resource
import signal
import sys
import time


_PR_SET_CHILD_SUBREAPER = 36
_PR_SET_NO_NEW_PRIVS = 38
_PR_SET_PDEATHSIG = 1
_SYS_LANDLOCK_CREATE_RULESET = 444
_SYS_LANDLOCK_ADD_RULE = 445
_SYS_LANDLOCK_RESTRICT_SELF = 446
_LANDLOCK_CREATE_RULESET_VERSION = 1
_LANDLOCK_RULE_PATH_BENEATH = 1
_LANDLOCK_ACCESS_FS_WRITE_FILE = 1 << 1
_LANDLOCK_ACCESS_FS_REMOVE_DIR = 1 << 4
_LANDLOCK_ACCESS_FS_REMOVE_FILE = 1 << 5
_LANDLOCK_ACCESS_FS_MAKE_CHAR = 1 << 6
_LANDLOCK_ACCESS_FS_MAKE_DIR = 1 << 7
_LANDLOCK_ACCESS_FS_MAKE_REG = 1 << 8
_LANDLOCK_ACCESS_FS_MAKE_SOCK = 1 << 9
_LANDLOCK_ACCESS_FS_MAKE_FIFO = 1 << 10
_LANDLOCK_ACCESS_FS_MAKE_BLOCK = 1 << 11
_LANDLOCK_ACCESS_FS_MAKE_SYM = 1 << 12
_LANDLOCK_ACCESS_FS_REFER = 1 << 13
_LANDLOCK_ACCESS_FS_TRUNCATE = 1 << 14
_SCMP_ACT_ALLOW = 0x7FFF_0000
_SCMP_ACT_ERRNO_EPERM = 0x0005_0001
_SCMP_CMP_EQ = 4
_FS_METADATA_IOCTL_REQUESTS = (
    0x4004_6602,  # 32-bit FS_IOC_SETFLAGS
    0x4008_6602,  # 64-bit FS_IOC_SETFLAGS
    0x4004_7602,  # 32-bit FS_IOC_SETVERSION
    0x4008_7602,  # 64-bit FS_IOC_SETVERSION
    0x401C_5820,  # FS_IOC_FSSETXATTR
)
_DENIED_SYSCALLS = (
    "accept",
    "accept4",
    "add_key",
    "bind",
    "chmod",
    "chown",
    "chroot",
    "connect",
    "fchmod",
    "fchmodat",
    "fchmodat2",
    "fchown",
    "fchownat",
    "fremovexattr",
    "fsetxattr",
    "fsmount",
    "fsconfig",
    "fsopen",
    "futimesat",
    "io_uring_enter",
    "io_uring_register",
    "io_uring_setup",
    "lchown",
    "listen",
    "lremovexattr",
    "lsetxattr",
    "mount",
    "mount_setattr",
    "move_mount",
    "open_tree",
    "pidfd_getfd",
    "pivot_root",
    "process_vm_writev",
    "ptrace",
    "keyctl",
    "recvmmsg",
    "recvfrom",
    "recvmsg",
    "removexattr",
    "request_key",
    "sendmmsg",
    "sendmsg",
    "sendto",
    "setns",
    "setxattr",
    "shutdown",
    "socket",
    "socketpair",
    "umount",
    "umount2",
    "unshare",
    "utime",
    "utimensat",
    "utimes",
)
_OPTIONAL_DENIED_SYSCALLS = frozenset(
    {
        # x86_64 exposes only umount2; libseccomp therefore cannot resolve the
        # historical umount alias.  umount2 remains mandatory below.
        "umount",
    }
)
_CLEANUP_TIMEOUT_SECONDS = 5.0
_POLL_SECONDS = 0.005
_cancelled = False


class _LandlockRulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _LandlockPathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


class _SeccompArgumentComparison(ctypes.Structure):
    _fields_ = [
        ("argument", ctypes.c_uint),
        ("operation", ctypes.c_int),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    ]


def _bounded_resource_limit(kind: int, requested: int) -> None:
    _soft, hard = resource.getrlimit(kind)
    target = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
    if target < 0:
        raise RuntimeError
    resource.setrlimit(kind, (target, target))


def _set_resource_limits(cpu_seconds: int) -> None:
    """Bound one solver tree even when the host cgroup is not delegated."""

    if not 1 <= cpu_seconds <= 86_400:
        raise RuntimeError
    _bounded_resource_limit(resource.RLIMIT_AS, 32 * 1024**3)
    _bounded_resource_limit(resource.RLIMIT_CORE, 0)
    _bounded_resource_limit(resource.RLIMIT_CPU, cpu_seconds)
    _bounded_resource_limit(resource.RLIMIT_DATA, 32 * 1024**3)
    _bounded_resource_limit(resource.RLIMIT_FSIZE, 2 * 1024**3)
    _bounded_resource_limit(resource.RLIMIT_NOFILE, 4096)
    _bounded_resource_limit(resource.RLIMIT_NPROC, 512)
    if hasattr(resource, "RLIMIT_MSGQUEUE"):
        _bounded_resource_limit(resource.RLIMIT_MSGQUEUE, 16 * 1024**2)
    if hasattr(resource, "RLIMIT_SIGPENDING"):
        _bounded_resource_limit(resource.RLIMIT_SIGPENDING, 1024)


def _enable_subreaper() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = getattr(libc, "prctl", None)
    if prctl is None:
        raise RuntimeError
    prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    prctl.restype = ctypes.c_int
    if int(prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)) != 0:
        raise RuntimeError


def _enable_write_sandbox(write_directory_fds: tuple[int, ...]) -> None:
    """Allow filesystem mutations only below explicitly inherited directories."""

    if not write_directory_fds or len(write_directory_fds) > 16:
        raise RuntimeError
    for descriptor in write_directory_fds:
        if descriptor <= 2 or not os.path.isdir(f"/proc/self/fd/{descriptor}"):
            raise RuntimeError
    libc = ctypes.CDLL(None, use_errno=True)
    syscall = libc.syscall
    syscall.restype = ctypes.c_long
    abi = int(
        syscall(
            _SYS_LANDLOCK_CREATE_RULESET,
            ctypes.c_void_p(),
            ctypes.c_size_t(0),
            ctypes.c_uint(_LANDLOCK_CREATE_RULESET_VERSION),
        )
    )
    # REFER was added in ABI 2 and TRUNCATE in ABI 3.  Older kernels cannot
    # provide the no-write-outside-workspace contract and therefore fail closed.
    if abi < 3:
        raise RuntimeError
    handled_access = (
        _LANDLOCK_ACCESS_FS_WRITE_FILE
        | _LANDLOCK_ACCESS_FS_REMOVE_DIR
        | _LANDLOCK_ACCESS_FS_REMOVE_FILE
        | _LANDLOCK_ACCESS_FS_MAKE_CHAR
        | _LANDLOCK_ACCESS_FS_MAKE_DIR
        | _LANDLOCK_ACCESS_FS_MAKE_REG
        | _LANDLOCK_ACCESS_FS_MAKE_SOCK
        | _LANDLOCK_ACCESS_FS_MAKE_FIFO
        | _LANDLOCK_ACCESS_FS_MAKE_BLOCK
        | _LANDLOCK_ACCESS_FS_MAKE_SYM
        | _LANDLOCK_ACCESS_FS_REFER
        | _LANDLOCK_ACCESS_FS_TRUNCATE
    )
    ruleset_attributes = _LandlockRulesetAttr(handled_access)
    ruleset_fd = int(
        syscall(
            _SYS_LANDLOCK_CREATE_RULESET,
            ctypes.byref(ruleset_attributes),
            ctypes.sizeof(ruleset_attributes),
            ctypes.c_uint(0),
        )
    )
    if ruleset_fd < 0:
        raise RuntimeError
    try:
        for descriptor in write_directory_fds:
            path_attributes = _LandlockPathBeneathAttr(
                handled_access,
                descriptor,
            )
            if (
                int(
                    syscall(
                        _SYS_LANDLOCK_ADD_RULE,
                        ruleset_fd,
                        _LANDLOCK_RULE_PATH_BENEATH,
                        ctypes.byref(path_attributes),
                        ctypes.c_uint(0),
                    )
                )
                != 0
            ):
                raise RuntimeError
        if int(libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)) != 0:
            raise RuntimeError
        if (
            int(
                syscall(
                    _SYS_LANDLOCK_RESTRICT_SELF,
                    ruleset_fd,
                    ctypes.c_uint(0),
                )
            )
            != 0
        ):
            raise RuntimeError
    finally:
        os.close(ruleset_fd)


def _enable_syscall_sandbox() -> None:
    """Deny metadata, namespace-escape, cross-process, and socket syscalls."""

    try:
        library = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as exc:
        raise RuntimeError from exc
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    library.seccomp_release.restype = None
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(_SeccompArgumentComparison),
    ]
    library.seccomp_rule_add_array.restype = ctypes.c_int
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    context = library.seccomp_init(_SCMP_ACT_ALLOW)
    if not context:
        raise RuntimeError
    try:
        for name in _DENIED_SYSCALLS:
            number = int(library.seccomp_syscall_resolve_name(name.encode("ascii")))
            if number < 0:
                if name in _OPTIONAL_DENIED_SYSCALLS:
                    continue
                raise RuntimeError
            if (
                int(
                    library.seccomp_rule_add(
                        context,
                        _SCMP_ACT_ERRNO_EPERM,
                        number,
                        0,
                    )
                )
                != 0
            ):
                raise RuntimeError
        ioctl_number = int(library.seccomp_syscall_resolve_name(b"ioctl"))
        if ioctl_number < 0:
            raise RuntimeError
        for request in _FS_METADATA_IOCTL_REQUESTS:
            comparison = _SeccompArgumentComparison(1, _SCMP_CMP_EQ, request, 0)
            if (
                int(
                    library.seccomp_rule_add_array(
                        context,
                        _SCMP_ACT_ERRNO_EPERM,
                        ioctl_number,
                        1,
                        ctypes.byref(comparison),
                    )
                )
                != 0
            ):
                raise RuntimeError
        if int(library.seccomp_load(context)) != 0:
            raise RuntimeError
    finally:
        library.seccomp_release(context)


def _child_pids() -> tuple[int, ...]:
    path = f"/proc/self/task/{os.getpid()}/children"
    try:
        payload = open(path, "rb", buffering=0).read(1024 * 1024)
    except OSError as exc:
        raise RuntimeError from exc
    try:
        values = tuple(int(token) for token in payload.split())
    except ValueError as exc:
        raise RuntimeError from exc
    if any(value <= 1 for value in values):
        raise RuntimeError
    return values


def _reap_nonblocking() -> None:
    while True:
        try:
            child, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        except InterruptedError:
            continue
        if child == 0:
            return


def _kill_and_reap_all_children() -> None:
    deadline = time.monotonic() + _CLEANUP_TIMEOUT_SECONDS
    while True:
        children = _child_pids()
        if not children:
            _reap_nonblocking()
            if not _child_pids():
                return
        for child in children:
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
        _reap_nonblocking()
        if time.monotonic() >= deadline:
            raise RuntimeError
        time.sleep(_POLL_SECONDS)


def _cancel(_signal_number: int, _frame: object) -> None:
    global _cancelled
    _cancelled = True


def _status_code(status: int) -> int:
    code = os.waitstatus_to_exitcode(status)
    if code < 0:
        return min(255, 128 + abs(code))
    return min(255, code)


def _parent_guard() -> None:
    """Bind the namespace launcher lifetime to the original Python caller."""

    arguments = list(sys.argv[2:])
    if len(arguments) < 3 or arguments[1] != "--":
        raise RuntimeError
    try:
        expected_parent = int(arguments[0], 10)
    except ValueError as exc:
        raise RuntimeError from exc
    command = tuple(arguments[2:])
    if (
        expected_parent <= 1
        or not command
        or any(not value or "\0" in value for value in command)
    ):
        raise RuntimeError
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = getattr(libc, "prctl", None)
    if prctl is None:
        raise RuntimeError
    prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    prctl.restype = ctypes.c_int
    if int(prctl(_PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)) != 0:
        raise RuntimeError
    # Close the fork/prctl race: if the caller died before PDEATHSIG was armed,
    # this process has already been reparented and must not launch a solver.
    if os.getppid() != expected_parent:
        os._exit(125)
    try:
        os.execve(command[0], command, dict(os.environ))
    except BaseException:
        os._exit(125)


def _main() -> int:
    arguments = list(sys.argv[1:])
    if len(arguments) < 2 or arguments[0] != "--cpu-seconds":
        raise RuntimeError
    try:
        cpu_seconds = int(arguments[1], 10)
    except ValueError as exc:
        raise RuntimeError from exc
    del arguments[:2]
    write_directory_fds: list[int] = []
    while len(arguments) >= 2 and arguments[0] == "--write-fd":
        try:
            descriptor = int(arguments[1], 10)
        except ValueError as exc:
            raise RuntimeError from exc
        write_directory_fds.append(descriptor)
        del arguments[:2]
    if not arguments or arguments.pop(0) != "--":
        raise RuntimeError
    command = tuple(arguments)
    if not command or any(not value or "\0" in value for value in command):
        raise RuntimeError
    # Verify procfs containment support before any untrusted process exists.
    _child_pids()
    _enable_subreaper()
    _set_resource_limits(cpu_seconds)
    _enable_write_sandbox(tuple(dict.fromkeys(write_directory_fds)))
    _enable_syscall_sandbox()
    child = os.fork()
    if child == 0:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGHUP, signal.SIG_DFL)
        try:
            os.execve(command[0], command, dict(os.environ))
        except BaseException:
            os._exit(127)
    signal.signal(signal.SIGTERM, _cancel)
    signal.signal(signal.SIGINT, _cancel)
    signal.signal(signal.SIGHUP, _cancel)
    status: int | None = None
    try:
        while status is None and not _cancelled:
            try:
                observed, candidate = os.waitpid(child, os.WNOHANG)
            except InterruptedError:
                continue
            if observed == child:
                status = candidate
                break
            time.sleep(_POLL_SECONDS)
        _kill_and_reap_all_children()
        if _cancelled:
            return 128 + signal.SIGTERM
        if status is None:
            raise RuntimeError
        return _status_code(status)
    finally:
        _kill_and_reap_all_children()


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--parent-guard":
            _parent_guard()
            raise RuntimeError
        raise SystemExit(_main())
    except SystemExit:
        raise
    except BaseException:
        try:
            _kill_and_reap_all_children()
        except BaseException:
            pass
        os._exit(125)
