from __future__ import annotations

from array import array
import fcntl
import hashlib
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys

import pytest

from tools import preflight_engine_v2_full_pipeline_cpu_supervisor_activation_v1 as activation


def _expectation(*, binary_sha256: str | None = None) -> activation.HandoffExpectationV1:
    user_fd = os.open("/proc/self/ns/user", os.O_RDONLY | os.O_CLOEXEC)
    mount_fd = os.open("/proc/self/ns/mnt", os.O_RDONLY | os.O_CLOEXEC)
    try:
        return activation.HandoffExpectationV1(
            activation_sha256="01" * 32,
            profile_sha256="02" * 32,
            runtime_manifest_sha256="03" * 32,
            dynamic_loader_sha256="04" * 32,
            python_executable_sha256="05" * 32,
            launch_vector_sha256="06" * 32,
            launch_environment_sha256="07" * 32,
            client_uid=os.geteuid() + 1,
            client_gid=os.getegid() + 1,
            service_uid=os.geteuid(),
            service_gid=os.getegid(),
            user_namespace_inode=os.fstat(user_fd).st_ino,
            mount_namespace_inode=os.fstat(mount_fd).st_ino,
            supervisor_binary_sha256=binary_sha256,
        )
    finally:
        os.close(mount_fd)
        os.close(user_fd)


def _sealed_receipt(packet: bytes) -> int:
    descriptor = os.memfd_create(
        "engine-v2-full-pipeline-cpu-supervisor-handoff-v1",
        os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC,
    )
    os.write(descriptor, packet)
    os.fchmod(descriptor, 0o400)
    fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, activation.REQUIRED_MEMFD_SEALS)
    return descriptor


def _packet(
    expectation: activation.HandoffExpectationV1,
    *,
    magic: bytes = activation.HANDOFF_MAGIC,
    binary_digest: bytes = bytes.fromhex("08" * 32),
    packet_flags: int = activation.HANDOFF_FLAGS,
) -> tuple[bytes, bytes, bytes]:
    nonce = bytes.fromhex("09" * 32)
    request_digest = bytes.fromhex("0a" * 32)
    user_fd = os.open("/proc/self/ns/user", os.O_RDONLY | os.O_CLOEXEC)
    mount_fd = os.open("/proc/self/ns/mnt", os.O_RDONLY | os.O_CLOEXEC)
    try:
        user = os.fstat(user_fd)
        mount = os.fstat(mount_fd)
    finally:
        os.close(mount_fd)
        os.close(user_fd)
    preflight = bytes.fromhex("0b" * 32)
    packet = activation._HANDOFF.pack(
        magic,
        activation.HANDOFF_VERSION,
        activation.HANDOFF_BYTES,
        nonce,
        request_digest,
        bytes.fromhex(expectation.activation_sha256),
        preflight,
        bytes.fromhex(expectation.profile_sha256),
        bytes.fromhex(expectation.runtime_manifest_sha256),
        preflight,
        bytes.fromhex(expectation.dynamic_loader_sha256),
        bytes.fromhex(expectation.python_executable_sha256),
        binary_digest,
        bytes.fromhex(expectation.launch_vector_sha256),
        bytes.fromhex(expectation.launch_environment_sha256),
        4242,
        expectation.client_uid,
        expectation.client_gid,
        os.getpid(),
        user.st_dev,
        user.st_ino,
        mount.st_dev,
        mount.st_ino,
        packet_flags,
        0,
    )
    return packet, nonce, request_digest


def _send_handoff(
    sender: socket.socket,
    packet: bytes,
    *,
    descriptor_count: int = 3,
) -> tuple[int, int, int]:
    receipt = _sealed_receipt(packet)
    user = os.open("/proc/self/ns/user", os.O_RDONLY | os.O_CLOEXEC)
    mount = os.open("/proc/self/ns/mnt", os.O_RDONLY | os.O_CLOEXEC)
    descriptors = (receipt, user, mount)[:descriptor_count]
    sender.sendmsg(
        [packet],
        [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array("i", descriptors))],
    )
    return receipt, user, mount


def _close_all(descriptors: tuple[int, ...]) -> None:
    for descriptor in descriptors:
        os.close(descriptor)


def test_handoff_verifies_exact_packet_receipt_namespaces_and_peer_pidfd() -> None:
    expectation = _expectation(binary_sha256="08" * 32)
    packet, nonce, request_digest = _packet(expectation)
    receiver, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    source_descriptors = _send_handoff(sender, packet)
    try:
        with activation.receive_and_verify_handoff(
            receiver.fileno(),
            expectation=expectation,
        ) as verified:
            evidence = verified.evidence.to_dict()
            assert evidence["status"] == "verified_kernel_handoff_non_consuming"
            assert evidence["packet_sha256"] == hashlib.sha256(packet).hexdigest()
            assert evidence["nonce_sha256"] == hashlib.sha256(nonce).hexdigest()
            assert evidence["request_sha256"] == request_digest.hex()
            assert evidence["supervisor_binary_sha256"] == "08" * 32
            assert evidence["handoff_descriptor_count"] == 3
            for descriptor in (
                verified.handoff_socket_fd,
                verified.peer_pidfd,
                verified.receipt_fd,
                verified.user_namespace_fd,
                verified.mount_namespace_fd,
            ):
                assert fcntl.fcntl(descriptor, fcntl.F_GETFD) & fcntl.FD_CLOEXEC
    finally:
        _close_all(source_descriptors)
        sender.close()
        receiver.close()


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("magic", "header or roster"),
        ("binary", "binary binding"),
        ("flags", "header or roster"),
    ),
)
def test_handoff_rejects_packet_or_binary_cross_wiring(
    mutation: str,
    message: str,
) -> None:
    expectation = _expectation(binary_sha256="08" * 32)
    packet, _nonce, _request = _packet(
        expectation,
        magic=(b"DRIFT" + bytes(11)) if mutation == "magic" else activation.HANDOFF_MAGIC,
        binary_digest=(bytes.fromhex("ff" * 32) if mutation == "binary" else bytes.fromhex("08" * 32)),
        packet_flags=(0 if mutation == "flags" else activation.HANDOFF_FLAGS),
    )
    receiver, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    source_descriptors = _send_handoff(sender, packet)
    try:
        with pytest.raises(activation.SupervisorHandoffError, match=message):
            activation.receive_and_verify_handoff(
                receiver.fileno(),
                expectation=expectation,
            )
    finally:
        _close_all(source_descriptors)
        sender.close()
        receiver.close()


def test_handoff_rejects_missing_namespace_descriptor() -> None:
    expectation = _expectation()
    packet, _nonce, _request = _packet(expectation)
    receiver, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    source_descriptors = _send_handoff(sender, packet, descriptor_count=2)
    try:
        with pytest.raises(
            activation.SupervisorHandoffError,
            match="exactly three descriptors",
        ):
            activation.receive_and_verify_handoff(
                receiver.fileno(),
                expectation=expectation,
            )
    finally:
        _close_all(source_descriptors)
        sender.close()
        receiver.close()


def test_handoff_closes_delivered_descriptors_when_ancillary_overflows() -> None:
    expectation = _expectation()
    packet, _nonce, _request = _packet(expectation)
    receiver, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    receipt = _sealed_receipt(packet)
    user = os.open("/proc/self/ns/user", os.O_RDONLY | os.O_CLOEXEC)
    mount = os.open("/proc/self/ns/mnt", os.O_RDONLY | os.O_CLOEXEC)
    extra = os.dup(mount)
    source_descriptors = (receipt, user, mount, extra)
    sender.sendmsg(
        [packet],
        [
            (
                socket.SOL_SOCKET,
                socket.SCM_RIGHTS,
                array("i", source_descriptors),
            )
        ],
    )
    descriptor_count_before = len(os.listdir("/proc/self/fd"))
    try:
        with pytest.raises(
            activation.SupervisorHandoffError,
            match="truncated|exactly three descriptors",
        ):
            activation.receive_and_verify_handoff(
                receiver.fileno(),
                expectation=expectation,
            )
        assert len(os.listdir("/proc/self/fd")) == descriptor_count_before
    finally:
        _close_all(source_descriptors)
        sender.close()
        receiver.close()


def test_terminal_receipt_binds_nonce_and_request() -> None:
    nonce = bytes.fromhex("09" * 32)
    request = "0a" * 32
    packet = activation._TERMINAL.pack(
        activation.TERMINAL_MAGIC,
        activation.HANDOFF_VERSION,
        activation.TERMINAL_BYTES,
        nonce,
        bytes.fromhex(request),
        125,
        0x02,
    )
    evidence = activation.verify_terminal_packet(
        packet,
        expected_nonce=nonce,
        expected_request_sha256=request,
    )
    assert evidence == {
        "containment_failure": True,
        "exit_code": 125,
        "request_sha256": request,
        "schema_id": (
            "betelgeuze.engine_v2_full_pipeline_cpu_supervisor_terminal/1.0.0"
        ),
        "terminal_sha256": hashlib.sha256(packet).hexdigest(),
        "timed_out": False,
    }
    with pytest.raises(activation.SupervisorHandoffError, match="cross-wired"):
        activation.verify_terminal_packet(
            packet,
            expected_nonce=bytes.fromhex("ff" * 32),
            expected_request_sha256=request,
        )


def test_production_roster_is_distinct_and_unprivileged() -> None:
    expectation = activation.production_expectation()
    expectation.validate()
    assert expectation.client_uid == 64042
    assert expectation.client_gid == 64042
    assert expectation.service_uid == 0
    assert expectation.service_gid == 0
    assert expectation.supervisor_binary_sha256 is None


def test_standalone_preflight_fails_before_handoff_or_output() -> None:
    script = Path(activation.__file__).resolve()
    environment = os.environ.copy()
    environment.pop("GITHUB_ACTIONS", None)
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    assert completed.returncode == 125
    assert completed.stdout == ""
    payload = __import__("json").loads(completed.stderr)
    assert payload["authority_false"] is True
    assert payload["status"] == "rejected_non_consuming"
    assert "process state changed" in payload["error"]


def test_github_actions_preflight_is_rejected_before_process_state() -> None:
    script = Path(activation.__file__).resolve()
    environment = os.environ.copy()
    environment["GITHUB_ACTIONS"] = "true"
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    assert completed.returncode == 125
    assert completed.stdout == ""
    payload = __import__("json").loads(completed.stderr)
    assert payload["authority_false"] is True
    assert payload["status"] == "rejected_non_consuming"
    assert payload["error"] == (
        "GitHub Actions cannot run the supervisor activation preflight"
    )


def test_package_binary_is_static_rostered_but_still_non_operational() -> None:
    binary = (
        Path(__file__).resolve().parents[2]
        / "packaging/engine-v2/full-pipeline-cpu-supervisor/1.0.0"
        / "engine-v2-full-pipeline-cpu-supervisor-v1"
    )
    metadata = binary.stat()
    assert stat.S_IMODE(metadata.st_mode) == 0o555
    assert metadata.st_size == 2_069_736
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == (
        "a33a07fc8a9f55a843ead479cee5b46f8ef31cb6787141fb7e3d8a563efb1466"
    )
    described = subprocess.run(
        [str(binary), "--describe-contract"],
        check=True,
        capture_output=True,
        text=True,
    )
    description = __import__("json").loads(described.stdout)
    assert description["client_uid"] == 64042
    assert description["client_gid"] == 64042
    assert description["client_identity_configured"] is True
    assert description["preflight_sha256"] == (
        "67c2e6ace0a4585d7004508323dc9928ddf45ee24e4bc77fa0406be4331857a0"
    )
    rejected = subprocess.run(
        [str(binary)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 125
    assert "qualification consumption remain unauthorized" in rejected.stderr
    assert not Path(
        "/run/betelgeuze-engine-v2/full-pipeline-cpu-supervisor-v1.sock"
    ).exists()
