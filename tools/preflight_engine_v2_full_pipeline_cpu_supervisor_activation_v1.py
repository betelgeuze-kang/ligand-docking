#!/usr/bin/env python3
"""Verify the v1 supervisor handoff, then remain fail-closed and non-consuming."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import errno
import fcntl
import hashlib
import json
import os
import select
import socket
import stat
import struct
import sys
from typing import NoReturn


SCHEMA_ID = "betelgeuze.engine_v2_full_pipeline_cpu_supervisor_handoff/1.0.0"
HANDOFF_MAGIC = b"BGV2CPUHANDOF1\0\0"
HANDOFF_VERSION = 1
HANDOFF_BYTES = 464
HANDOFF_DESCRIPTOR_COUNT = 3
HANDOFF_FLAGS = 0x01 | 0x02 | 0x04
TERMINAL_MAGIC = b"BGV2CPUTERMV1\0\0\0"
TERMINAL_BYTES = 96
TERMINAL_ALLOWED_FLAGS = 0x01 | 0x02
HANDOFF_SOCKET_FD = 193
SOURCE_SNAPSHOT_FD = 190
ARTIFACT_DIRECTORY_FD = 191
RUNTIME_DIRECTORY_FD = 192
SO_PEERPIDFD = 77
CLONE_NEWNS = 0x00020000
CLONE_NEWUSER = 0x10000000
NSIO = 0xB7
NS_GET_USERNS = (NSIO << 8) | 0x1
NS_GET_PARENT = (NSIO << 8) | 0x2
NS_GET_NSTYPE = (NSIO << 8) | 0x3
NS_GET_OWNER_UID = (NSIO << 8) | 0x4
REQUIRED_MEMFD_SEALS = (
    fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
)
MAX_SOURCE_BYTES = 4 * 1024 * 1024
EXPECTED_CLIENT_UID = 64042
EXPECTED_CLIENT_GID = 64042
EXPECTED_SERVICE_UID = 0
EXPECTED_SERVICE_GID = 0
EXPECTED_INITIAL_USER_NAMESPACE_INODE = 4026531837
EXPECTED_INITIAL_MOUNT_NAMESPACE_INODE = 4026531841
EXPECTED_ACTIVATION_SHA256 = (
    "c9f77a76c0d7687d1c4195f06d50529ce66d915dd1a79f48e9a2827570af9ea2"
)
EXPECTED_PROFILE_SHA256 = (
    "385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000"
)
EXPECTED_RUNTIME_MANIFEST_SHA256 = (
    "72b90f500af43c921ce0b8f7d6774c5e99a7e4f3fe366478b3fc33b524b4b404"
)
EXPECTED_DYNAMIC_LOADER_SHA256 = (
    "8d06f393f4a93bcf9b81145a259524d66a95522a646bf8d7e05b6ffdf2e63dcc"
)
EXPECTED_PYTHON_EXECUTABLE_SHA256 = (
    "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86"
)
EXPECTED_LAUNCH_VECTOR_SHA256 = (
    "3844da69d7b4a1dd61cde9ffa559c7409a6d23b43a80f63dcea612f859a932d3"
)
EXPECTED_LAUNCH_ENVIRONMENT_SHA256 = (
    "5cf4cf74eba4f493ae3f8a88c3459e2f8861146b6e38b5c4d7bd65e958f0da96"
)
EXPECTED_ARGUMENTS = (
    "/proc/self/fd/190",
    "--artifact-directory",
    "/proc/self/fd/191",
    "--runtime-root=/proc/self/fd/192",
)
EXPECTED_ENVIRONMENT = {
    "BETELGEUZE_SUPERVISOR_ARTIFACT_FD": "191",
    "BETELGEUZE_SUPERVISOR_HANDOFF_FD": "193",
    "BETELGEUZE_SUPERVISOR_RUNTIME_FD": "192",
    "BETELGEUZE_SUPERVISOR_SOURCE_FD": "190",
    "CUDA_VISIBLE_DEVICES": "",
    "HIP_VISIBLE_DEVICES": "",
    "LC_ALL": "C",
    "PATH": "/usr/bin:/bin",
    "ROCR_VISIBLE_DEVICES": "",
}

_HANDOFF = struct.Struct("!16sII32s" + "32s" * 11 + "IIIIQQQQII")
_TERMINAL = struct.Struct("!16sII32s32sII")
if _HANDOFF.size != HANDOFF_BYTES:
    raise RuntimeError("supervisor handoff parser size drifted")
if _TERMINAL.size != TERMINAL_BYTES:
    raise RuntimeError("supervisor terminal parser size drifted")


class SupervisorHandoffError(RuntimeError):
    """Raised when the kernel-attested handoff is incomplete or cross-wired."""


def _fail(message: str) -> NoReturn:
    raise SupervisorHandoffError(message)


def _require_sha256(value: str, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{name} SHA-256 is invalid")
    return value


@dataclass(frozen=True)
class HandoffExpectationV1:
    activation_sha256: str
    profile_sha256: str
    runtime_manifest_sha256: str
    dynamic_loader_sha256: str
    python_executable_sha256: str
    launch_vector_sha256: str
    launch_environment_sha256: str
    client_uid: int
    client_gid: int
    service_uid: int
    service_gid: int
    user_namespace_inode: int
    mount_namespace_inode: int
    supervisor_binary_sha256: str | None = None

    def validate(self) -> None:
        for name in (
            "activation_sha256",
            "profile_sha256",
            "runtime_manifest_sha256",
            "dynamic_loader_sha256",
            "python_executable_sha256",
            "launch_vector_sha256",
            "launch_environment_sha256",
        ):
            _require_sha256(str(getattr(self, name)), name=name)
        if self.supervisor_binary_sha256 is not None:
            _require_sha256(
                self.supervisor_binary_sha256,
                name="supervisor_binary_sha256",
            )
        for name in (
            "client_uid",
            "client_gid",
            "service_uid",
            "service_gid",
            "user_namespace_inode",
            "mount_namespace_inode",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                _fail(f"{name} is invalid")
        if self.client_uid == 0 or self.client_uid == self.service_uid:
            _fail("supervisor client and service identities are not separated")


@dataclass(frozen=True)
class HandoffEvidenceV1:
    packet_sha256: str
    nonce_sha256: str
    request_sha256: str
    preflight_sha256: str
    supervisor_binary_sha256: str
    service_peer_pid: int
    service_peer_uid: int
    service_peer_gid: int
    request_peer_pid: int
    request_peer_uid: int
    request_peer_gid: int
    child_pid: int
    user_namespace_device: int
    user_namespace_inode: int
    mount_namespace_device: int
    mount_namespace_inode: int

    def to_dict(self) -> dict[str, object]:
        return {
            "child_pid": self.child_pid,
            "handoff_descriptor_count": HANDOFF_DESCRIPTOR_COUNT,
            "mount_namespace_device": self.mount_namespace_device,
            "mount_namespace_inode": self.mount_namespace_inode,
            "nonce_sha256": self.nonce_sha256,
            "packet_sha256": self.packet_sha256,
            "preflight_sha256": self.preflight_sha256,
            "request_peer_gid": self.request_peer_gid,
            "request_peer_pid": self.request_peer_pid,
            "request_peer_uid": self.request_peer_uid,
            "request_sha256": self.request_sha256,
            "schema_id": SCHEMA_ID,
            "service_peer_gid": self.service_peer_gid,
            "service_peer_pid": self.service_peer_pid,
            "service_peer_uid": self.service_peer_uid,
            "status": "verified_kernel_handoff_non_consuming",
            "supervisor_binary_sha256": self.supervisor_binary_sha256,
            "user_namespace_device": self.user_namespace_device,
            "user_namespace_inode": self.user_namespace_inode,
        }


def verify_terminal_packet(
    packet: bytes,
    *,
    expected_nonce: bytes,
    expected_request_sha256: str,
) -> dict[str, object]:
    """Bind a terminal packet to the exact request without writing state."""

    if type(packet) is not bytes or len(packet) != TERMINAL_BYTES:
        _fail("supervisor terminal packet size changed")
    if type(expected_nonce) is not bytes or len(expected_nonce) != 32:
        _fail("supervisor terminal nonce expectation is invalid")
    _require_sha256(expected_request_sha256, name="expected_request")
    magic, version, size, nonce, request_digest, exit_code, flags = _TERMINAL.unpack(
        packet
    )
    if (
        magic != TERMINAL_MAGIC
        or version != HANDOFF_VERSION
        or size != TERMINAL_BYTES
        or nonce != expected_nonce
        or request_digest.hex() != expected_request_sha256
        or flags & ~TERMINAL_ALLOWED_FLAGS
    ):
        _fail("supervisor terminal receipt cross-wired or drifted")
    return {
        "containment_failure": bool(flags & 0x02),
        "exit_code": exit_code,
        "request_sha256": expected_request_sha256,
        "schema_id": (
            "betelgeuze.engine_v2_full_pipeline_cpu_supervisor_terminal/1.0.0"
        ),
        "terminal_sha256": hashlib.sha256(packet).hexdigest(),
        "timed_out": bool(flags & 0x01),
    }


@dataclass
class VerifiedHandoffV1:
    evidence: HandoffEvidenceV1
    handoff_socket_fd: int
    peer_pidfd: int
    receipt_fd: int
    user_namespace_fd: int
    mount_namespace_fd: int

    def close(self) -> None:
        for name in (
            "mount_namespace_fd",
            "user_namespace_fd",
            "receipt_fd",
            "peer_pidfd",
            "handoff_socket_fd",
        ):
            descriptor = getattr(self, name)
            if descriptor >= 0:
                os.close(descriptor)
                setattr(self, name, -1)

    def __enter__(self) -> VerifiedHandoffV1:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def production_expectation() -> HandoffExpectationV1:
    return HandoffExpectationV1(
        activation_sha256=EXPECTED_ACTIVATION_SHA256,
        profile_sha256=EXPECTED_PROFILE_SHA256,
        runtime_manifest_sha256=EXPECTED_RUNTIME_MANIFEST_SHA256,
        dynamic_loader_sha256=EXPECTED_DYNAMIC_LOADER_SHA256,
        python_executable_sha256=EXPECTED_PYTHON_EXECUTABLE_SHA256,
        launch_vector_sha256=EXPECTED_LAUNCH_VECTOR_SHA256,
        launch_environment_sha256=EXPECTED_LAUNCH_ENVIRONMENT_SHA256,
        client_uid=EXPECTED_CLIENT_UID,
        client_gid=EXPECTED_CLIENT_GID,
        service_uid=EXPECTED_SERVICE_UID,
        service_gid=EXPECTED_SERVICE_GID,
        user_namespace_inode=EXPECTED_INITIAL_USER_NAMESPACE_INODE,
        mount_namespace_inode=EXPECTED_INITIAL_MOUNT_NAMESPACE_INODE,
    )


def _set_cloexec(descriptor: int) -> None:
    flags = fcntl.fcntl(descriptor, fcntl.F_GETFD)
    fcntl.fcntl(descriptor, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)


def _stable_read(descriptor: int, size: int, *, name: str) -> bytes:
    before = os.fstat(descriptor)
    raw = os.pread(descriptor, size + 1, 0)
    after = os.fstat(descriptor)
    identity = (
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
    if any(getattr(before, field) != getattr(after, field) for field in identity):
        _fail(f"{name} identity changed while read")
    if len(raw) != size:
        _fail(f"{name} size changed")
    return raw


def _verify_receipt(
    descriptor: int,
    packet: bytes,
    *,
    expectation: HandoffExpectationV1,
) -> None:
    metadata = os.fstat(descriptor)
    seals = fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)
    raw = _stable_read(descriptor, HANDOFF_BYTES, name="sealed handoff receipt")
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != expectation.service_uid
        or metadata.st_gid != expectation.service_gid
        or stat.S_IMODE(metadata.st_mode) != 0o400
        or metadata.st_nlink != 0
        or metadata.st_size != HANDOFF_BYTES
        or seals != REQUIRED_MEMFD_SEALS
        or raw != packet
    ):
        _fail("sealed handoff receipt identity changed")


def _ioctl_owner_uid(descriptor: int) -> int:
    owner = array("I", [0])
    fcntl.ioctl(descriptor, NS_GET_OWNER_UID, owner, True)
    return int(owner[0])


def _verify_namespaces(
    user_descriptor: int,
    mount_descriptor: int,
    *,
    expectation: HandoffExpectationV1,
    packet_user_device: int,
    packet_user_inode: int,
    packet_mount_device: int,
    packet_mount_inode: int,
) -> tuple[os.stat_result, os.stat_result]:
    user = os.fstat(user_descriptor)
    mount = os.fstat(mount_descriptor)
    if (
        user.st_dev != packet_user_device
        or user.st_ino != packet_user_inode
        or mount.st_dev != packet_mount_device
        or mount.st_ino != packet_mount_inode
        or user.st_ino != expectation.user_namespace_inode
        or mount.st_ino != expectation.mount_namespace_inode
        or fcntl.ioctl(user_descriptor, NS_GET_NSTYPE) != CLONE_NEWUSER
        or fcntl.ioctl(mount_descriptor, NS_GET_NSTYPE) != CLONE_NEWNS
        or _ioctl_owner_uid(user_descriptor) != 0
    ):
        _fail("initial namespace descriptor identity changed")
    try:
        parent = fcntl.ioctl(user_descriptor, NS_GET_PARENT)
    except OSError as exc:
        if exc.errno != errno.EPERM:
            raise SupervisorHandoffError(
                "initial user namespace parent could not be attested"
            ) from exc
    else:
        os.close(parent)
        _fail("user namespace is not the initial namespace")
    owner_descriptor = fcntl.ioctl(mount_descriptor, NS_GET_USERNS)
    try:
        owner = os.fstat(owner_descriptor)
        if owner.st_dev != user.st_dev or owner.st_ino != user.st_ino:
            _fail("mount namespace owner changed")
    finally:
        os.close(owner_descriptor)
    return user, mount


def _parse_packet(packet: bytes) -> tuple[object, ...]:
    if len(packet) != HANDOFF_BYTES:
        _fail("supervisor handoff packet size changed")
    return _HANDOFF.unpack(packet)


def receive_and_verify_handoff(
    handoff_socket_fd: int,
    *,
    expectation: HandoffExpectationV1,
    expected_child_pid: int | None = None,
) -> VerifiedHandoffV1:
    """Receive exactly one handoff and retain all liveness/namespace handles."""

    if type(handoff_socket_fd) is not int or handoff_socket_fd < 3:
        _fail("handoff socket descriptor is invalid")
    expectation.validate()
    child_pid = os.getpid() if expected_child_pid is None else expected_child_pid
    if type(child_pid) is not int or child_pid <= 1:
        _fail("expected child PID is invalid")

    owned_socket = socket.socket(fileno=os.dup(handoff_socket_fd))
    peer_pidfd = -1
    received: list[int] = []
    try:
        owned_socket.setblocking(True)
        peer_pid, peer_uid, peer_gid = struct.unpack(
            "3i",
            owned_socket.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12),
        )
        if (
            peer_pid <= 1
            or peer_uid != expectation.service_uid
            or peer_gid != expectation.service_gid
        ):
            _fail("handoff socket peer is not the rostered root service")
        peer_pidfd = struct.unpack(
            "i", owned_socket.getsockopt(socket.SOL_SOCKET, SO_PEERPIDFD, 4)
        )[0]
        if peer_pidfd < 0:
            _fail("handoff socket peer pidfd is unavailable")
        _set_cloexec(peer_pidfd)
        poller = select.poll()
        poller.register(peer_pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        if poller.poll(0):
            _fail("handoff socket peer is not live")

        packet, ancillary, flags, _address = owned_socket.recvmsg(
            HANDOFF_BYTES,
            socket.CMSG_SPACE(struct.calcsize("3i")),
            socket.MSG_CMSG_CLOEXEC,
        )
        rights_messages = 0
        ancillary_type_changed = False
        ancillary_shape_changed = False
        for level, kind, raw in ancillary:
            if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                ancillary_type_changed = True
                continue
            rights_messages += 1
            integer_size = struct.calcsize("i")
            complete_size = len(raw) - (len(raw) % integer_size)
            if complete_size:
                received.extend(
                    struct.unpack(
                        f"{complete_size // integer_size}i",
                        raw[:complete_size],
                    )
                )
            if not raw or complete_size != len(raw):
                ancillary_shape_changed = True
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            _fail("supervisor handoff packet or descriptors were truncated")
        if ancillary_type_changed:
            _fail("supervisor handoff ancillary type changed")
        if (
            ancillary_shape_changed
            or rights_messages != 1
            or len(received) != HANDOFF_DESCRIPTOR_COUNT
        ):
            _fail("supervisor handoff requires exactly three descriptors")
        for descriptor in received:
            _set_cloexec(descriptor)

        values = _parse_packet(packet)
        (
            magic,
            version,
            size,
            nonce,
            request_digest,
            activation_digest,
            preflight_digest,
            profile_digest,
            runtime_digest,
            source_digest,
            loader_digest,
            python_digest,
            supervisor_digest,
            launch_vector_digest,
            launch_environment_digest,
            request_peer_pid,
            request_peer_uid,
            request_peer_gid,
            observed_child_pid,
            user_device,
            user_inode,
            mount_device,
            mount_inode,
            packet_flags,
            reserved,
        ) = values
        if (
            magic != HANDOFF_MAGIC
            or version != HANDOFF_VERSION
            or size != HANDOFF_BYTES
            or nonce == bytes(32)
            or request_digest == bytes(32)
            or preflight_digest == bytes(32)
            or source_digest == bytes(32)
            or supervisor_digest == bytes(32)
            or packet_flags != HANDOFF_FLAGS
            or reserved != 0
            or request_peer_pid <= 1
            or request_peer_uid != expectation.client_uid
            or request_peer_gid != expectation.client_gid
            or observed_child_pid != child_pid
        ):
            _fail("supervisor handoff header or roster identity changed")

        expected_digests = (
            (activation_digest, expectation.activation_sha256, "activation"),
            (profile_digest, expectation.profile_sha256, "profile"),
            (runtime_digest, expectation.runtime_manifest_sha256, "runtime manifest"),
            (loader_digest, expectation.dynamic_loader_sha256, "dynamic loader"),
            (
                python_digest,
                expectation.python_executable_sha256,
                "Python executable",
            ),
            (launch_vector_digest, expectation.launch_vector_sha256, "launch vector"),
            (
                launch_environment_digest,
                expectation.launch_environment_sha256,
                "launch environment",
            ),
        )
        for observed, expected, name in expected_digests:
            if observed.hex() != expected:
                _fail(f"supervisor handoff {name} binding changed")
        if source_digest != preflight_digest:
            _fail("supervisor source snapshot and preflight binding diverged")
        if (
            expectation.supervisor_binary_sha256 is not None
            and supervisor_digest.hex() != expectation.supervisor_binary_sha256
        ):
            _fail("supervisor binary binding changed")

        _verify_receipt(received[0], packet, expectation=expectation)
        user, mount = _verify_namespaces(
            received[1],
            received[2],
            expectation=expectation,
            packet_user_device=user_device,
            packet_user_inode=user_inode,
            packet_mount_device=mount_device,
            packet_mount_inode=mount_inode,
        )
        evidence = HandoffEvidenceV1(
            packet_sha256=hashlib.sha256(packet).hexdigest(),
            nonce_sha256=hashlib.sha256(nonce).hexdigest(),
            request_sha256=request_digest.hex(),
            preflight_sha256=preflight_digest.hex(),
            supervisor_binary_sha256=supervisor_digest.hex(),
            service_peer_pid=peer_pid,
            service_peer_uid=peer_uid,
            service_peer_gid=peer_gid,
            request_peer_pid=request_peer_pid,
            request_peer_uid=request_peer_uid,
            request_peer_gid=request_peer_gid,
            child_pid=observed_child_pid,
            user_namespace_device=user.st_dev,
            user_namespace_inode=user.st_ino,
            mount_namespace_device=mount.st_dev,
            mount_namespace_inode=mount.st_ino,
        )
        return VerifiedHandoffV1(
            evidence=evidence,
            handoff_socket_fd=owned_socket.detach(),
            peer_pidfd=peer_pidfd,
            receipt_fd=received[0],
            user_namespace_fd=received[1],
            mount_namespace_fd=received[2],
        )
    except BaseException:
        for descriptor in received:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if peer_pidfd >= 0:
            os.close(peer_pidfd)
        owned_socket.close()
        raise


def _validate_inherited_source() -> str:
    metadata = os.fstat(SOURCE_SNAPSHOT_FD)
    if not 1 <= metadata.st_size <= MAX_SOURCE_BYTES:
        _fail("preflight source snapshot size changed")
    raw = _stable_read(
        SOURCE_SNAPSHOT_FD,
        metadata.st_size,
        name="preflight source snapshot",
    )
    seals = fcntl.fcntl(SOURCE_SNAPSHOT_FD, fcntl.F_GET_SEALS)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o444
        or metadata.st_nlink != 0
        or seals != REQUIRED_MEMFD_SEALS
    ):
        _fail("preflight source snapshot identity changed")
    return hashlib.sha256(raw).hexdigest()


def _require_exact_process_state() -> str:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        _fail("GitHub Actions cannot run the supervisor activation preflight")
    if tuple(sys.argv) != EXPECTED_ARGUMENTS or dict(os.environ) != EXPECTED_ENVIRONMENT:
        _fail("supervisor activation preflight process state changed")
    if os.geteuid() != EXPECTED_CLIENT_UID or os.getegid() != EXPECTED_CLIENT_GID:
        _fail("supervisor activation preflight roster identity changed")
    for descriptor, name in (
        (ARTIFACT_DIRECTORY_FD, "artifact directory"),
        (RUNTIME_DIRECTORY_FD, "runtime directory"),
    ):
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid not in (0, EXPECTED_CLIENT_UID)
            or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            _fail(f"{name} descriptor is uncontrolled")
    return _validate_inherited_source()


def main() -> int:
    source_sha256 = _require_exact_process_state()
    expectation = production_expectation()
    with receive_and_verify_handoff(
        HANDOFF_SOCKET_FD,
        expectation=expectation,
    ) as verified:
        if verified.evidence.preflight_sha256 != source_sha256:
            _fail("supervisor handoff did not bind the exact preflight snapshot")
        # The package/roster/handoff layer is intentionally not the performance
        # preflight or exactly-once state transaction.  A later reviewed change
        # must bind this evidence and the terminal receipt before execution.
        _fail("downstream performance preflight binding is not admitted")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SupervisorHandoffError as error:
        print(
            json.dumps(
                {
                    "authority_false": True,
                    "error": str(error),
                    "schema_id": SCHEMA_ID,
                    "status": "rejected_non_consuming",
                },
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(125) from error
