from __future__ import annotations

import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.docking import performance_host_preflight_v3 as preflight


def _replace_stat_field(
    value: os.stat_result,
    *,
    index: int,
    replacement: int,
) -> os.stat_result:
    fields = list(value)
    fields[index] = replacement
    return os.stat_result(fields)


def test_sysfs_reader_uses_actual_bytes_not_reported_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "boost"
    path.write_bytes(b"0\n")
    path.chmod(0o644)
    original_lstat = Path.lstat
    original_fstat = os.fstat

    def reported_large_lstat(candidate: Path) -> os.stat_result:
        return _replace_stat_field(
            original_lstat(candidate), index=6, replacement=4096
        )

    def reported_large_fstat(descriptor: int) -> os.stat_result:
        return _replace_stat_field(
            original_fstat(descriptor), index=6, replacement=4096
        )

    monkeypatch.setattr(Path, "lstat", reported_large_lstat)
    monkeypatch.setattr(os, "fstat", reported_large_fstat)

    evidence = preflight._read_sysfs_boolean(path, expected_uid=os.geteuid())

    assert evidence.boost_enabled is False
    assert evidence.raw_byte_count == 2
    assert evidence.reported_size_before == 4096
    assert evidence.reported_size_descriptor_before == 4096
    assert evidence.reported_size_descriptor_after == 4096
    assert evidence.reported_size_after == 4096
    assert evidence.stable_read_count == 2


@pytest.mark.parametrize(
    ("raw", "expected"),
    ((b"0", False), (b"0\n", False), (b"1", True), (b"1\n", True)),
)
def test_sysfs_reader_accepts_only_exact_boolean_payloads(
    tmp_path: Path,
    raw: bytes,
    expected: bool,
) -> None:
    path = tmp_path / "boost"
    path.write_bytes(raw)
    path.chmod(0o644)

    evidence = preflight._read_sysfs_boolean(path, expected_uid=os.geteuid())

    assert evidence.boost_enabled is expected
    assert evidence.raw_byte_count == len(raw)


@pytest.mark.parametrize("raw", (b"", b"2\n", b" 0\n", b"0\n\n"))
def test_sysfs_reader_rejects_invalid_payloads(tmp_path: Path, raw: bytes) -> None:
    path = tmp_path / "boost"
    path.write_bytes(raw)
    path.chmod(0o644)

    with pytest.raises(
        preflight.CPUPerformanceHostPreflightError,
        match="boost_state_payload_invalid",
    ):
        preflight._read_sysfs_boolean(path, expected_uid=os.geteuid())


def test_sysfs_reader_rejects_actual_oversize(tmp_path: Path) -> None:
    path = tmp_path / "boost"
    path.write_bytes(b"0" * 33)
    path.chmod(0o644)

    with pytest.raises(
        preflight.CPUPerformanceHostPreflightError,
        match="boost_state_actual_bytes_exceeded",
    ):
        preflight._read_sysfs_boolean(path, expected_uid=os.geteuid())


def test_sysfs_reader_rejects_symlink_and_writable_file(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_bytes(b"0\n")
    target.chmod(0o644)
    symlink = tmp_path / "boost-link"
    symlink.symlink_to(target)

    with pytest.raises(
        preflight.CPUPerformanceHostPreflightError,
        match="boost_state_symlink_forbidden",
    ):
        preflight._read_sysfs_boolean(symlink, expected_uid=os.geteuid())

    target.chmod(0o664)
    with pytest.raises(
        preflight.CPUPerformanceHostPreflightError,
        match="boost_state_writable_by_others",
    ):
        preflight._read_sysfs_boolean(target, expected_uid=os.geteuid())


def test_sysfs_reader_rejects_descriptor_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "boost"
    path.write_bytes(b"0\n")
    path.chmod(0o644)
    original_fstat = os.fstat
    calls = 0

    def drifting_fstat(descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        observed = original_fstat(descriptor)
        if calls == 2:
            return _replace_stat_field(
                observed, index=1, replacement=observed.st_ino + 1
            )
        return observed

    monkeypatch.setattr(os, "fstat", drifting_fstat)
    with pytest.raises(
        preflight.CPUPerformanceHostPreflightError,
        match="boost_state_identity_changed",
    ):
        preflight._read_sysfs_boolean(path, expected_uid=os.geteuid())


def test_sysfs_reader_types_descriptor_metadata_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "boost"
    path.write_bytes(b"0\n")
    path.chmod(0o644)

    def fail_fstat(_descriptor: int) -> os.stat_result:
        raise OSError("synthetic fstat failure")

    monkeypatch.setattr(os, "fstat", fail_fstat)
    with pytest.raises(
        preflight.CPUPerformanceHostPreflightError,
        match="boost_state_metadata_unavailable",
    ):
        preflight._read_sysfs_boolean(path, expected_uid=os.geteuid())


def test_sysfs_reader_rejects_value_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "boost"
    path.write_bytes(b"0\n")
    path.chmod(0o644)
    observed = iter((b"0\n", b"", b"1\n", b""))
    monkeypatch.setattr(os, "read", lambda _descriptor, _count: next(observed))

    with pytest.raises(
        preflight.CPUPerformanceHostPreflightError,
        match="boost_state_value_changed",
    ):
        preflight._read_sysfs_boolean(path, expected_uid=os.geteuid())


def test_host_preflight_is_non_consuming_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preflight.v2, "_cpu_model", lambda: preflight.v2.CPU_MODEL_EXACT)
    monkeypatch.setattr(preflight.v2, "_os_task_count", lambda _pid: 1)
    monkeypatch.setattr(
        preflight,
        "read_cpu_boost_state_v3",
        lambda: preflight.SysfsBooleanEvidenceV3(
            path=str(preflight.CPU_BOOST_SYSFS_PATH),
            reader_id=preflight.CPU_BOOST_READER_ID,
            raw_byte_count=2,
            raw_sha256="0" * 64,
            reported_size_before=4096,
            reported_size_descriptor_before=4096,
            reported_size_descriptor_after=4096,
            reported_size_after=4096,
            stable_read_count=2,
            boost_enabled=False,
        ),
    )
    monkeypatch.setattr(os, "sched_getaffinity", lambda _pid: {2})
    monkeypatch.setattr(preflight.platform, "system", lambda: "Linux")
    monkeypatch.setattr(preflight.platform, "machine", lambda: "x86_64")

    result = preflight.derive_host_preflight_evidence_v3()
    document = result.to_dict()

    assert result.qualified is True
    assert result.blockers == ()
    assert document["consumes_qualification"] is False
    assert document["launches_measurements"] is False
    assert document["molecular_execution"] is False


def test_host_preflight_preserves_typed_boost_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preflight.v2, "_cpu_model", lambda: preflight.v2.CPU_MODEL_EXACT)
    monkeypatch.setattr(preflight.v2, "_os_task_count", lambda _pid: 1)
    monkeypatch.setattr(os, "sched_getaffinity", lambda _pid: {2})
    monkeypatch.setattr(preflight.platform, "system", lambda: "Linux")
    monkeypatch.setattr(preflight.platform, "machine", lambda: "x86_64")

    def fail() -> preflight.SysfsBooleanEvidenceV3:
        raise preflight.CPUPerformanceHostPreflightError(
            "boost_state_actual_bytes_exceeded"
        )

    monkeypatch.setattr(preflight, "read_cpu_boost_state_v3", fail)

    result = preflight.derive_host_preflight_evidence_v3()

    assert result.qualified is False
    assert result.blockers == ("boost_state_actual_bytes_exceeded",)
    assert result.boost_state is None
