from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import stat
import sys

import pytest

from betelgeuze_engine_v2.physics import validation_process_launch_identity as module


_BOOT_ID = "12345678-1234-4abc-8def-1234567890ab"
_OTHER_BOOT_ID = "87654321-4321-4cba-8fed-ba0987654321"
_PID = 321
_PARENT_PID = 12
_START_TIME = 987_654
_NAMESPACE_INODE = 4_026_531_836


def _stat_bytes(
    *,
    pid: int = _PID,
    parent_pid: int = _PARENT_PID,
    start_time: int = _START_TIME,
    command: bytes = b"worker name with ) and ) spaces",
) -> bytes:
    fields = [b"R", str(parent_pid).encode("ascii")]
    fields.extend([b"1"] * 17)
    fields.append(str(start_time).encode("ascii"))
    fields.extend([b"0"] * 32)
    return (
        str(pid).encode("ascii") + b" (" + command + b") " + b" ".join(fields) + b"\n"
    )


def _fake_proc_root(
    tmp_path: Path,
    *,
    boot_id: str = _BOOT_ID,
    stat_bytes: bytes | None = None,
    namespace_target: str | None = None,
) -> Path:
    proc_root = tmp_path / "proc-fixture"
    boot_parent = proc_root / "sys" / "kernel" / "random"
    boot_parent.mkdir(parents=True)
    (boot_parent / "boot_id").write_bytes(f"{boot_id}\n".encode("ascii"))
    pid_root = proc_root / str(_PID)
    (pid_root / "ns").mkdir(parents=True)
    (pid_root / "stat").write_bytes(_stat_bytes() if stat_bytes is None else stat_bytes)
    (pid_root / "ns" / "pid").symlink_to(
        namespace_target or f"pid:[{_NAMESPACE_INODE}]"
    )
    return proc_root


def _synthetic_public_document() -> dict[str, object]:
    return module._build_identity_document(
        proc_root="/proc",
        boot_id=_BOOT_ID,
        process_row={
            "pid": _PID,
            "parent_pid": _PARENT_PID,
            "start_time_clock_ticks": _START_TIME,
        },
        pid_namespace_inode=_NAMESPACE_INODE,
    )


def _rehash_identity(document: dict[str, object]) -> None:
    projection = {
        key: document[key]
        for key in sorted(document)
        if key != "process_launch_identity_sha256"
    }
    document["process_launch_identity_sha256"] = module._sha256(projection)


def test_real_self_measurement_and_exact_expected_verification() -> None:
    if not sys.platform.startswith("linux") or not Path("/proc/self/stat").exists():
        pytest.skip("Linux procfs is unavailable")

    document = module.measure_process_launch_identity()

    assert document["pid"] == os.getpid()
    assert document["parent_pid"] == os.getppid()
    assert document["proc_root"] == "/proc"
    assert (
        document["boot_id_sha256"]
        == hashlib.sha256(str(document["boot_id"]).encode("ascii")).hexdigest()
    )
    assert module.require_process_launch_identity_document(document) == document
    assert (
        module.verify_process_launch_identity(
            document,
            expected_pid=int(document["pid"]),
            expected_parent_pid=int(document["parent_pid"]),
            expected_start_time_clock_ticks=int(document["start_time_clock_ticks"]),
            expected_pid_namespace_inode=int(document["pid_namespace_inode"]),
            expected_boot_id_sha256=str(document["boot_id_sha256"]),
        )
        == document
    )


def test_private_fixture_measurement_parses_spaces_and_parentheses_but_is_not_public(
    tmp_path: Path,
) -> None:
    proc_root = _fake_proc_root(tmp_path)

    document = module._measure_process_launch_identity_at_proc_root(
        _PID,
        proc_root=os.fspath(proc_root),
    )

    assert document["pid"] == _PID
    assert document["parent_pid"] == _PARENT_PID
    assert document["start_time_clock_ticks"] == _START_TIME
    assert document["pid_namespace_inode"] == _NAMESPACE_INODE
    assert document["proc_root"] == os.fspath(proc_root)
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="fixed /proc",
    ):
        module.require_process_launch_identity_document(document)


def test_stat_parser_uses_last_closing_parenthesis_and_field_22() -> None:
    parsed = module._parse_process_stat(
        _stat_bytes(command=b"alpha ) beta) gamma ) delta"),
        expected_pid=_PID,
    )

    assert parsed == {
        "pid": _PID,
        "parent_pid": _PARENT_PID,
        "start_time_clock_ticks": _START_TIME,
    }


@pytest.mark.parametrize(
    "raw, match",
    [
        (b"", "framing"),
        (_stat_bytes()[:-1], "framing"),
        (_stat_bytes() + b"extra\n", "framing"),
        (b"321 worker R 12 " + b"1 " * 40 + b"\n", "command boundary"),
        (b"321 () R 12 " + b"1 " * 40 + b"\n", "command field"),
        (b"321 (worker) R 12 1 2\n", "field count"),
        (_stat_bytes(start_time=0), "positive"),
        (b"0321 (worker) R 12 " + b"1 " * 50 + b"\n", "canonical"),
    ],
    ids=[
        "empty",
        "truncated-newline",
        "multiple-lines",
        "missing-parentheses",
        "empty-command",
        "truncated-fields",
        "zero-start-time",
        "noncanonical-pid",
    ],
)
def test_stat_parser_rejects_malformed_or_truncated_rows(
    raw: bytes,
    match: str,
) -> None:
    with pytest.raises(module.ValidationProcessLaunchIdentityError, match=match):
        module._parse_process_stat(raw, expected_pid=_PID)


def test_stat_parser_rejects_pid_mismatch_and_oversize() -> None:
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="does not match",
    ):
        module._parse_process_stat(_stat_bytes(pid=_PID + 1), expected_pid=_PID)

    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="framing",
    ):
        module._parse_process_stat(
            b"1 (" + b"x" * module.PROCESS_LAUNCH_MAX_STAT_BYTES + b") R 1\n",
            expected_pid=1,
        )


def test_parser_document_and_fixture_measurement_allow_namespace_init_parent_zero(
    tmp_path: Path,
) -> None:
    parsed = module._parse_process_stat(
        _stat_bytes(parent_pid=0),
        expected_pid=_PID,
    )
    assert parsed["parent_pid"] == 0

    proc_root = _fake_proc_root(tmp_path, stat_bytes=_stat_bytes(parent_pid=0))
    measured = module._measure_process_launch_identity_at_proc_root(
        _PID,
        proc_root=os.fspath(proc_root),
    )
    assert measured["parent_pid"] == 0

    public_document = module._build_identity_document(
        proc_root="/proc",
        boot_id=_BOOT_ID,
        process_row={
            "pid": _PID,
            "parent_pid": 0,
            "start_time_clock_ticks": _START_TIME,
        },
        pid_namespace_inode=_NAMESPACE_INODE,
    )
    assert (
        module.verify_process_launch_identity(
            public_document,
            expected_pid=_PID,
            expected_parent_pid=0,
            expected_start_time_clock_ticks=_START_TIME,
            expected_pid_namespace_inode=_NAMESPACE_INODE,
            expected_boot_id_sha256=str(public_document["boot_id_sha256"]),
        )
        == public_document
    )


def test_measurement_rejects_observed_parent_and_starttime_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc_root = _fake_proc_root(tmp_path)
    rows = iter(
        (
            {
                "pid": _PID,
                "parent_pid": _PARENT_PID,
                "start_time_clock_ticks": _START_TIME,
            },
            {
                "pid": _PID,
                "parent_pid": _PARENT_PID + 1,
                "start_time_clock_ticks": _START_TIME + 1,
            },
        )
    )
    monkeypatch.setattr(
        module, "_read_process_stat", lambda *args, **kwargs: next(rows)
    )

    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="tuple changed",
    ):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )


def test_measurement_rejects_boot_transplant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc_root = _fake_proc_root(tmp_path)
    boot_ids = iter((_BOOT_ID, _OTHER_BOOT_ID))
    monkeypatch.setattr(module, "_read_boot_id", lambda _fd: next(boot_ids))

    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="boot id changed",
    ):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )


def test_measurement_rejects_namespace_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc_root = _fake_proc_root(tmp_path)
    namespace_inodes = iter((_NAMESPACE_INODE, _NAMESPACE_INODE + 1))
    monkeypatch.setattr(
        module,
        "_read_pid_namespace_inode",
        lambda _fd: next(namespace_inodes),
    )

    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="namespace identity changed",
    ):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )


@pytest.mark.parametrize(
    "field, replacement, expected_key, match",
    [
        ("pid", _PID + 1, "expected_pid", "pid does not match"),
        (
            "parent_pid",
            _PARENT_PID + 1,
            "expected_parent_pid",
            "parent_pid does not match",
        ),
        (
            "start_time_clock_ticks",
            _START_TIME + 1,
            "expected_start_time_clock_ticks",
            "start_time_clock_ticks does not match",
        ),
        (
            "pid_namespace_inode",
            _NAMESPACE_INODE + 1,
            "expected_pid_namespace_inode",
            "pid_namespace_inode does not match",
        ),
    ],
)
def test_verifier_rejects_pid_parent_starttime_and_namespace_crosswire(
    field: str,
    replacement: int,
    expected_key: str,
    match: str,
) -> None:
    document = _synthetic_public_document()
    expected: dict[str, object] = {
        "expected_pid": _PID,
        "expected_parent_pid": _PARENT_PID,
        "expected_start_time_clock_ticks": _START_TIME,
        "expected_pid_namespace_inode": _NAMESPACE_INODE,
        "expected_boot_id_sha256": document["boot_id_sha256"],
    }
    expected[expected_key] = replacement

    with pytest.raises(module.ValidationProcessLaunchIdentityError, match=match):
        module.verify_process_launch_identity(document, **expected)  # type: ignore[arg-type]

    transplanted = copy.deepcopy(document)
    transplanted[field] = replacement
    _rehash_identity(transplanted)
    with pytest.raises(module.ValidationProcessLaunchIdentityError, match=match):
        module.verify_process_launch_identity(
            transplanted,
            expected_pid=_PID,
            expected_parent_pid=_PARENT_PID,
            expected_start_time_clock_ticks=_START_TIME,
            expected_pid_namespace_inode=_NAMESPACE_INODE,
            expected_boot_id_sha256=str(document["boot_id_sha256"]),
        )


def test_verifier_rejects_boot_transplant_even_when_document_is_rehashed() -> None:
    document = _synthetic_public_document()
    original_boot_sha = str(document["boot_id_sha256"])
    document["boot_id"] = _OTHER_BOOT_ID
    document["boot_id_sha256"] = hashlib.sha256(
        _OTHER_BOOT_ID.encode("ascii")
    ).hexdigest()
    _rehash_identity(document)

    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="boot_id_sha256 does not match",
    ):
        module.verify_process_launch_identity(
            document,
            expected_pid=_PID,
            expected_parent_pid=_PARENT_PID,
            expected_start_time_clock_ticks=_START_TIME,
            expected_pid_namespace_inode=_NAMESPACE_INODE,
            expected_boot_id_sha256=original_boot_sha,
        )


def test_same_tick_pid_reuse_collision_is_explicitly_indistinguishable() -> None:
    first = _synthetic_public_document()
    hypothetical_reused_pid_in_same_tick = module._build_identity_document(
        proc_root="/proc",
        boot_id=_BOOT_ID,
        process_row={
            "pid": _PID,
            "parent_pid": _PARENT_PID,
            "start_time_clock_ticks": _START_TIME,
        },
        pid_namespace_inode=_NAMESPACE_INODE,
    )

    assert hypothetical_reused_pid_in_same_tick == first
    contract = module.process_launch_identity_contract_document()
    decision = module.process_launch_identity_decision()
    assert contract["purpose"]["same_tick_pid_reuse_collision_excluded"] is False
    assert (
        contract["authenticity_limits"]["durable_process_uniqueness_established"]
        is False
    )
    assert decision["same_tick_pid_reuse_collision_excluded"] is False
    assert decision["durable_process_uniqueness_established"] is False
    assert decision["external_launch_nonce_bound"] is False
    assert "pid_reuse_detection_primitive_implemented" not in decision
    assert "same_tick_pid_reuse_collision_not_excluded" in decision["blockers"]


def test_secure_reader_rejects_stat_and_boot_symlinks(tmp_path: Path) -> None:
    proc_root = _fake_proc_root(tmp_path)
    stat_path = proc_root / str(_PID) / "stat"
    external = tmp_path / "external"
    external.write_bytes(_stat_bytes())
    stat_path.unlink()
    stat_path.symlink_to(external)

    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="O_NOFOLLOW",
    ):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )

    proc_root = _fake_proc_root(tmp_path / "second")
    boot_path = proc_root / "sys" / "kernel" / "random" / "boot_id"
    boot_path.unlink()
    boot_path.symlink_to(external)
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="O_NOFOLLOW",
    ):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )


def test_secure_reader_rejects_oversized_boot_and_stat_files(tmp_path: Path) -> None:
    proc_root = _fake_proc_root(tmp_path)
    (proc_root / "sys" / "kernel" / "random" / "boot_id").write_bytes(
        b"x" * (module.PROCESS_LAUNCH_MAX_BOOT_ID_BYTES + 1)
    )
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="boot id exceeds",
    ):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )

    proc_root = _fake_proc_root(tmp_path / "second")
    (proc_root / str(_PID) / "stat").write_bytes(
        b"x" * (module.PROCESS_LAUNCH_MAX_STAT_BYTES + 1)
    )
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="process stat exceeds",
    ):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )


@pytest.mark.parametrize(
    "boot_bytes",
    [
        b"12345678-1234-4ABC-8def-1234567890ab\n",
        b"12345678-1234-4abc-8def-1234567890ab",
        b"12345678-1234-4abc-8def-1234567890ab\nextra\n",
        b"not-a-uuid\n",
    ],
)
def test_boot_reader_rejects_noncanonical_or_truncated_values(
    tmp_path: Path,
    boot_bytes: bytes,
) -> None:
    proc_root = _fake_proc_root(tmp_path)
    (proc_root / "sys" / "kernel" / "random" / "boot_id").write_bytes(boot_bytes)

    with pytest.raises(module.ValidationProcessLaunchIdentityError):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )


@pytest.mark.parametrize(
    "target",
    [
        "pid:[0]",
        "pid:[01]",
        "mnt:[4026531836]",
        "pid:4026531836",
        "pid:[18446744073709551616]",
    ],
)
def test_namespace_reader_rejects_malformed_or_out_of_range_targets(
    tmp_path: Path,
    target: str,
) -> None:
    proc_root = _fake_proc_root(tmp_path, namespace_target=target)

    with pytest.raises(module.ValidationProcessLaunchIdentityError):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )


def test_bounded_reader_detects_file_change_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    target = parent / "value"
    target.write_bytes(b"abc")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    real_read = os.read
    changed = False

    def mutate_after_first_read(fd: int, count: int) -> bytes:
        nonlocal changed
        chunk = real_read(fd, count)
        if chunk and not changed:
            changed = True
            with target.open("ab") as stream:
                stream.write(b"d")
        return chunk

    monkeypatch.setattr(module.os, "read", mutate_after_first_read)
    try:
        with pytest.raises(
            module.ValidationProcessLaunchIdentityError,
            match="identity changed while read",
        ):
            module._read_bounded_regular_file_at(
                parent_fd,
                "value",
                maximum_bytes=16,
                label="race fixture",
            )
    finally:
        os.close(parent_fd)


def test_namespace_reader_detects_link_change_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc_root = _fake_proc_root(tmp_path)
    namespace_link = proc_root / str(_PID) / "ns" / "pid"
    real_readlink = os.readlink
    changed = False

    def mutate_after_readlink(path: str, *, dir_fd: int | None = None) -> str:
        nonlocal changed
        target = real_readlink(path, dir_fd=dir_fd)
        if not changed:
            changed = True
            namespace_link.unlink()
            namespace_link.symlink_to(f"pid:[{_NAMESPACE_INODE + 1}]")
        return target

    monkeypatch.setattr(module.os, "readlink", mutate_after_readlink)
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="changed while",
    ):
        module._measure_process_launch_identity_at_proc_root(
            _PID,
            proc_root=os.fspath(proc_root),
        )


def test_identity_rejects_tamper_invalid_ranges_and_nonfixed_proc_root() -> None:
    original = _synthetic_public_document()
    for field, replacement in (
        ("pid", 0),
        ("parent_pid", -1),
        ("start_time_clock_ticks", module.PROCESS_LAUNCH_MAX_CLOCK_TICKS + 1),
        ("pid_namespace_inode", True),
        ("boot_id", _BOOT_ID.upper()),
        ("boot_id_sha256", "A" * 64),
        ("proc_root", "/tmp/proc"),
    ):
        tampered = copy.deepcopy(original)
        tampered[field] = replacement
        _rehash_identity(tampered)
        with pytest.raises(module.ValidationProcessLaunchIdentityError):
            module.require_process_launch_identity_document(tampered)

    tampered = copy.deepcopy(original)
    tampered["pid"] = _PID + 1
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="self hash",
    ):
        module.require_process_launch_identity_document(tampered)


def test_public_api_rejects_proc_root_constant_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "PROCESS_LAUNCH_PROC_ROOT", "/tmp/fake-proc")
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="not fixed",
    ):
        module.measure_process_launch_identity()


def test_frozen_contract_and_decision_remain_claim_closed() -> None:
    contract = module.process_launch_identity_contract_document()
    decision = module.process_launch_identity_decision()

    assert contract["contract_sha256"] == (
        "934b62f063e1e2133b80794df528a4227033e11679d266df8c6feee2b306f43a"
    )
    assert contract["contract_sha256"] == (
        module.FROZEN_PROCESS_LAUNCH_IDENTITY_CONTRACT_SHA256
    )
    assert contract["authenticity_limits"] == {
        "procfs_superblock_identity_authenticated": False,
        "boot_id_is_external_host_identity": False,
        "namespace_inode_is_external_launch_custody": False,
        "same_host_process_tuple_is_external_authentication": False,
        "same_tick_pid_reuse_collision_excluded": False,
        "durable_process_uniqueness_established": False,
        "external_launch_nonce_bound": False,
        "external_signed_runtime_manifest_bound": False,
    }
    assert all(value is False for value in contract["claim_policy"].values())
    for field in (
        "procfs_superblock_identity_authenticated",
        "external_host_authenticity_established",
        "external_worker_launch_custody_established",
        "same_tick_pid_reuse_collision_excluded",
        "durable_process_uniqueness_established",
        "external_launch_nonce_bound",
        "production_process_authenticity_established",
        "production_validation_results_collected",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "parameter_fitting_authorized",
        "claim_safe",
    ):
        assert decision[field] is False
    assert "procfs_superblock_identity_not_authenticated" in decision["blockers"]
    assert "external_host_identity_not_authenticated" in decision["blockers"]
    assert (
        module.require_process_launch_identity_contract_document(contract) == contract
    )


def test_contract_rejects_tamper_even_with_self_consistent_nested_value() -> None:
    contract = module.process_launch_identity_contract_document()
    tampered = copy.deepcopy(contract)
    tampered["authenticity_limits"]["procfs_superblock_identity_authenticated"] = True

    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="does not match",
    ):
        module.require_process_launch_identity_contract_document(tampered)


def test_required_linux_secure_open_flags_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(module.os, "O_NOFOLLOW")
    with pytest.raises(
        module.ValidationProcessLaunchIdentityError,
        match="O_NOFOLLOW/O_CLOEXEC",
    ):
        module._secure_file_flags()


def test_namespace_fixture_is_a_symlink_and_not_a_regular_file(tmp_path: Path) -> None:
    proc_root = _fake_proc_root(tmp_path)
    link_stat = os.stat(
        proc_root / str(_PID) / "ns" / "pid",
        follow_symlinks=False,
    )
    assert stat.S_ISLNK(link_stat.st_mode)
