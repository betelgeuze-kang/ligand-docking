from __future__ import annotations

import copy
import os
from pathlib import Path
import stat
import subprocess
import time
from types import SimpleNamespace

import pytest

from betelgeuze_engine_v2.physics import validation_native_runtime_identity as module


_TRUSTED_EXECUTABLE = Path("/usr/bin/python3.11")


def _maps_line(
    *,
    path: str | None = None,
    permissions: str = "r-xp",
    device_major: int | None = None,
    device_minor: int | None = None,
    inode: int | None = None,
    offset: int = 0,
    start: int = 0x1000,
    end: int = 0x2000,
) -> bytes:
    if path is None:
        suffix = ""
        major = 0 if device_major is None else device_major
        minor = 0 if device_minor is None else device_minor
        observed_inode = 0 if inode is None else inode
    elif path.startswith("["):
        suffix = f"    {path}"
        major = 0 if device_major is None else device_major
        minor = 0 if device_minor is None else device_minor
        observed_inode = 0 if inode is None else inode
    elif device_major is not None and device_minor is not None and inode is not None:
        suffix = f"    {path}"
        major = device_major
        minor = device_minor
        observed_inode = inode
    else:
        file_stat = os.stat(path, follow_symlinks=False)
        suffix = f"    {path}"
        major = os.major(file_stat.st_dev) if device_major is None else device_major
        minor = os.minor(file_stat.st_dev) if device_minor is None else device_minor
        observed_inode = file_stat.st_ino if inode is None else inode
    return (
        f"{start:x}-{end:x} {permissions} {offset:08x} "
        f"{major:02x}:{minor:02x} {observed_inode}{suffix}\n"
    ).encode("utf-8")


def _safe_maps() -> bytes:
    return _maps_line(path=os.fspath(_TRUSTED_EXECUTABLE)) + _maps_line(
        path="[vdso]",
        start=0x3000,
        end=0x4000,
    )


def _measure_synthetic_snapshot(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    raw = _safe_maps()
    monkeypatch.setattr(module, "_read_maps_bounded", lambda *, deadline: raw)
    return module.measure_native_runtime_snapshot()


def _minimization_rows() -> list[dict[str, object]]:
    return [
        {
            "ordinal": ordinal,
            "case_id": f"min-case-{ordinal:02d}",
            "case_passed": True,
            "coordinate_traces": [],
        }
        for ordinal in range(1, 15)
    ]


def _energy_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ordinal in range(27):
        variant_count = 3 if ordinal < 5 else 2
        rows.append(
            {
                "ordinal": ordinal,
                "case_id": f"energy-case-{ordinal:02d}",
                "case_passed": True,
                "variant_results": [
                    {"ordinal": nested, "variant_id": f"v{nested}"}
                    for nested in range(variant_count)
                ],
            }
        )
    return rows


def _materialization_manifest_row() -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for case_ordinal in range(27):
        variant_count = 3 if case_ordinal < 5 else 2
        case_projection: dict[str, object] = {
            "case_id": f"manifest-case-{case_ordinal:02d}",
            "case_input_sha256": f"{case_ordinal + 1:064x}",
            "fixture_profile_id": "fixture",
            "fixture_profile_sha256": "a" * 64,
            "mutation_contract_id": "mutation",
            "mutation_contract_sha256": "b" * 64,
            "expected_outcome": "pass",
            "expected_error_code": None,
            "variant_count": variant_count,
            "variants": [
                {"variant_id": f"variant-{nested}"} for nested in range(variant_count)
            ],
            "result_fields_present": False,
        }
        cases.append(
            {
                **case_projection,
                "materialization_sha256": module._sha256(case_projection),
            }
        )
    manifest_projection: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_reference_validation_materializer/1.0.0",
        "materializer_id": "cpu_reference_validation_exact_fixture_materializer/1.0.0",
        "materializer_version": "1.0.0",
        "materializer_source_sha256": "c" * 64,
        "protocol_sha256": "d" * 64,
        "fixture_manifest_sha256": "e" * 64,
        "materialization_policy": {},
        "coverage": {
            "fixture_count": 7,
            "mutation_count": 20,
            "case_count": 27,
            "variant_count": 59,
            "expected_pass_case_count": 15,
            "expected_fail_closed_case_count": 12,
        },
        "cases": cases,
        "result_collection_performed": False,
        "energy_or_force_values_present": False,
        "metric_values_present": False,
        "validation_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return {
        "ordinal": 0,
        "case_id": "materialization_manifest",
        "materialization_manifest": {
            **manifest_projection,
            "materialization_manifest_sha256": module._sha256(manifest_projection),
        },
    }


def _rehash(document: dict[str, object], hash_field: str) -> None:
    projection = {key: value for key, value in document.items() if key != hash_field}
    document[hash_field] = module._sha256(projection)


def test_measurement_builds_canonical_ordered_snapshot_and_exact_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)

    assert snapshot["schema_id"] == module.NATIVE_RUNTIME_SNAPSHOT_SCHEMA_ID
    assert snapshot["mapping_count"] == 2
    assert snapshot["file_count"] == 1
    assert snapshot["mapping_rows"][0]["path"] == os.fspath(_TRUSTED_EXECUTABLE)
    assert snapshot["mapping_rows"][1]["path"] == "[vdso]"
    assert module.require_native_runtime_snapshot(snapshot) == snapshot
    assert module.measure_native_runtime_snapshot() == snapshot


def test_measurement_allows_nonexecutable_vma_change_but_rejects_executable_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    safe_executable = _maps_line(path=os.fspath(_TRUSTED_EXECUTABLE))
    first = safe_executable + _maps_line(
        permissions="rw-p",
        start=0x3000,
        end=0x4000,
    )
    second_nonexec_changed = safe_executable + _maps_line(
        permissions="rw-p",
        start=0x4000,
        end=0x5000,
    )
    reads = iter((first, second_nonexec_changed))
    monkeypatch.setattr(
        module,
        "_read_maps_bounded",
        lambda *, deadline: next(reads),
    )
    assert module.measure_native_runtime_snapshot()["mapping_count"] == 1

    changed_executable = _maps_line(
        path=os.fspath(_TRUSTED_EXECUTABLE),
        start=0x1001,
        end=0x2001,
    )
    reads = iter((safe_executable, changed_executable))
    monkeypatch.setattr(
        module,
        "_read_maps_bounded",
        lambda *, deadline: next(reads),
    )
    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError, match="executable.*changed"
    ):
        module.measure_native_runtime_snapshot()


@pytest.mark.parametrize(
    "unsafe_maps",
    [
        _maps_line(path=os.fspath(_TRUSTED_EXECUTABLE), permissions="rwxp"),
        _maps_line(path=None),
        _maps_line(path="[stack]"),
        _maps_line(path="[vdso]", device_major=1),
        _maps_line(path="[vdso]", inode=1),
        _maps_line(path="[vdso]", permissions="r-xs"),
        _maps_line(
            path="/memfd:jit (deleted)", device_major=0, device_minor=0, inode=1
        ),
        _maps_line(
            path=f"{_TRUSTED_EXECUTABLE} (deleted)",
            device_major=os.major(os.stat(_TRUSTED_EXECUTABLE).st_dev),
            device_minor=os.minor(os.stat(_TRUSTED_EXECUTABLE).st_dev),
            inode=os.stat(_TRUSTED_EXECUTABLE).st_ino,
        ),
    ],
    ids=[
        "write-execute",
        "anonymous-executable",
        "unapproved-special",
        "vdso-device",
        "vdso-inode",
        "vdso-shared",
        "memfd",
        "deleted",
    ],
)
def test_measurement_rejects_unsafe_executable_mapping_classes(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_maps: bytes,
) -> None:
    monkeypatch.setattr(module, "_read_maps_bounded", lambda *, deadline: unsafe_maps)

    with pytest.raises(module.ValidationNativeRuntimeIdentityError):
        module.measure_native_runtime_snapshot()


def test_measurement_rejects_nonabsolute_and_ambiguous_maps_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for raw in (
        b"1000-2000 r-xp 00000000 00:00 1 relative.so\n",
        b"not-a-maps-row\n",
        b"1000-2000 r-xp 00000000 00:00 1 /tmp/a\\012b\n",
    ):
        monkeypatch.setattr(
            module, "_read_maps_bounded", lambda *, deadline, raw=raw: raw
        )
        with pytest.raises(module.ValidationNativeRuntimeIdentityError):
            module.measure_native_runtime_snapshot()


def test_measurement_rejects_maps_vs_fd_device_or_inode_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _maps_line(
        path=os.fspath(_TRUSTED_EXECUTABLE),
        inode=os.stat(_TRUSTED_EXECUTABLE).st_ino + 1,
    )
    monkeypatch.setattr(module, "_read_maps_bounded", lambda *, deadline: raw)

    with pytest.raises(module.ValidationNativeRuntimeIdentityError, match="maps-vs-fd"):
        module.measure_native_runtime_snapshot()


def test_trusted_file_policy_rejects_nonregular_nonroot_and_writable() -> None:
    safe = {
        "st_mode": stat.S_IFREG | 0o755,
        "st_uid": 0,
        "st_nlink": 1,
    }
    for replacement in (
        {"st_mode": stat.S_IFCHR | 0o755},
        {"st_uid": 1000},
        {"st_mode": stat.S_IFREG | 0o775},
        {"st_mode": stat.S_IFREG | 0o757},
    ):
        fields = {**safe, **replacement}
        with pytest.raises(module.ValidationNativeRuntimeIdentityError):
            module._require_trusted_file_stat(SimpleNamespace(**fields))


def test_no_follow_component_open_rejects_symlink() -> None:
    assert _TRUSTED_EXECUTABLE.is_file()
    assert Path("/usr/bin/python3").is_symlink()

    with pytest.raises(module.ValidationNativeRuntimeIdentityError, match="O_NOFOLLOW"):
        module._open_trusted_absolute_file(
            "/usr/bin/python3",
            deadline=time.monotonic() + 10.0,
        )


def test_hash_detects_file_growth_and_stat_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "mutable.so"
    target.write_bytes(b"abc")
    descriptor = os.open(target, os.O_RDONLY)
    before = os.fstat(descriptor)
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
            module.ValidationNativeRuntimeIdentityError, match="grew|changed"
        ):
            module._hash_open_file(
                descriptor,
                before,
                already_hashed_bytes=0,
                deadline=time.monotonic() + 10.0,
            )
    finally:
        os.close(descriptor)


def test_maps_bytes_rows_paths_file_bytes_total_and_deadline_are_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maps_path = tmp_path / "maps"
    maps_path.write_bytes(b"x" * 65 + b"\n")
    monkeypatch.setattr(
        module,
        "_open_proc_self_maps_descriptor",
        lambda: os.open(maps_path, os.O_RDONLY),
    )
    monkeypatch.setattr(module, "NATIVE_RUNTIME_MAX_MAPS_BYTES", 64)
    with pytest.raises(module.ValidationNativeRuntimeIdentityError, match="byte bound"):
        module._read_maps_bounded(deadline=time.monotonic() + 10.0)

    monkeypatch.setattr(module, "NATIVE_RUNTIME_MAX_MAP_ROWS", 1)
    with pytest.raises(module.ValidationNativeRuntimeIdentityError, match="row count"):
        module._parse_maps(_safe_maps(), deadline=time.monotonic() + 10.0)

    monkeypatch.setattr(module, "NATIVE_RUNTIME_MAX_PATH_BYTES", 8)
    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError, match="row length|pathname"
    ):
        module._parse_maps(
            _maps_line(path=os.fspath(_TRUSTED_EXECUTABLE)),
            deadline=time.monotonic() + 10.0,
        )

    file_stat = os.stat(_TRUSTED_EXECUTABLE)
    descriptor = os.open(_TRUSTED_EXECUTABLE, os.O_RDONLY)
    monkeypatch.setattr(module, "NATIVE_RUNTIME_MAX_FILE_BYTES", file_stat.st_size - 1)
    try:
        with pytest.raises(
            module.ValidationNativeRuntimeIdentityError, match="byte bound"
        ):
            module._hash_open_file(
                descriptor,
                file_stat,
                already_hashed_bytes=0,
                deadline=time.monotonic() + 10.0,
            )
    finally:
        os.close(descriptor)

    monkeypatch.setattr(module, "NATIVE_RUNTIME_MAX_FILE_BYTES", file_stat.st_size + 1)
    monkeypatch.setattr(
        module, "NATIVE_RUNTIME_MAX_TOTAL_FILE_BYTES", file_stat.st_size - 1
    )
    descriptor = os.open(_TRUSTED_EXECUTABLE, os.O_RDONLY)
    try:
        with pytest.raises(
            module.ValidationNativeRuntimeIdentityError, match="byte bound"
        ):
            module._hash_open_file(
                descriptor,
                file_stat,
                already_hashed_bytes=0,
                deadline=time.monotonic() + 10.0,
            )
    finally:
        os.close(descriptor)

    with pytest.raises(module.ValidationNativeRuntimeIdentityError, match="expired"):
        module.measure_native_runtime_snapshot(deadline=time.monotonic() - 1.0)


def test_maps_reader_rejects_substitute_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    substitute = tmp_path / "maps"
    substitute.write_bytes(_safe_maps())
    monkeypatch.setattr(module, "NATIVE_RUNTIME_MAPS_PATH", os.fspath(substitute))

    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError,
        match="path identity",
    ):
        module._read_maps_bounded(deadline=time.monotonic() + 10.0)


def test_bounded_worker_communication_accepts_small_exact_output() -> None:
    process = subprocess.Popen(
        [
            os.fspath(_TRUSTED_EXECUTABLE),
            "-S",
            "-c",
            "import sys; data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data)",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    output, timed_out, succeeded = module.communicate_bounded_worker_process(
        process,
        b"request\n",
        deadline=time.monotonic() + 10.0,
        max_output_bytes=64,
    )

    assert (output, timed_out, succeeded) == (b"request\n", False, True)


def test_bounded_worker_communication_kills_on_first_byte_past_cap() -> None:
    process = subprocess.Popen(
        [
            os.fspath(_TRUSTED_EXECUTABLE),
            "-S",
            "-c",
            (
                "import sys; sys.stdin.buffer.read(); "
                "sys.stdout.buffer.write(b'x'*1048576); sys.stdout.buffer.flush()"
            ),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    output, timed_out, succeeded = module.communicate_bounded_worker_process(
        process,
        b"request\n",
        deadline=time.monotonic() + 10.0,
        max_output_bytes=1024,
    )

    assert output == b""
    assert timed_out is False
    assert succeeded is False
    assert process.returncode is not None


def test_bounded_worker_communication_retains_bounded_partial_on_timeout() -> None:
    process = subprocess.Popen(
        [
            os.fspath(_TRUSTED_EXECUTABLE),
            "-S",
            "-c",
            (
                "import sys,time; sys.stdin.buffer.read(); "
                "sys.stdout.buffer.write(b'pre\\n'); sys.stdout.buffer.flush(); "
                "time.sleep(60)"
            ),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    output, timed_out, succeeded = module.communicate_bounded_worker_process(
        process,
        b"request\n",
        deadline=time.monotonic() + 0.2,
        max_output_bytes=64,
    )

    assert output == b"pre\n"
    assert timed_out is True
    assert succeeded is False
    assert process.returncode is not None


def test_process_group_termination_targets_group_after_leader_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[int, int]] = []
    process = SimpleNamespace(
        pid=1234,
        kill=lambda: pytest.fail("leader-only kill fallback was used"),
    )

    def leader_is_already_reaped(_pid: int) -> int:
        raise ProcessLookupError

    monkeypatch.setattr(module.os, "getpgid", leader_is_already_reaped)
    monkeypatch.setattr(
        module.os,
        "killpg",
        lambda pid, signal_number: seen.append((pid, signal_number)),
    )

    module._terminate_worker_process_group(process)

    assert seen == [(1234, module.signal.SIGKILL)]


def test_snapshot_validator_blocks_hash_order_schema_and_backing_crosswire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)
    mutations: list[dict[str, object]] = []

    hash_tamper = copy.deepcopy(snapshot)
    hash_tamper["snapshot_sha256"] = "0" * 64
    mutations.append(hash_tamper)

    reordered = copy.deepcopy(snapshot)
    reordered["mapping_rows"].reverse()
    _rehash(reordered, "snapshot_sha256")
    mutations.append(reordered)

    extra = copy.deepcopy(snapshot)
    extra["unexpected"] = None
    _rehash(extra, "snapshot_sha256")
    mutations.append(extra)

    crosswired = copy.deepcopy(snapshot)
    crosswired["mapping_rows"][0]["backing_file_identity_sha256"] = "f" * 64
    _rehash(crosswired, "snapshot_sha256")
    mutations.append(crosswired)

    for mutation in mutations:
        with pytest.raises(module.ValidationNativeRuntimeIdentityError):
            module.require_native_runtime_snapshot(mutation)

    kernel_only = copy.deepcopy(snapshot)
    kernel_only["mapping_rows"] = [kernel_only["mapping_rows"][1]]
    kernel_only["mapping_rows"][0]["ordinal"] = 0
    kernel_only["mapping_count"] = 1
    kernel_only["file_rows"] = []
    kernel_only["file_count"] = 0
    kernel_only["hashed_file_bytes"] = 0
    _rehash(kernel_only, "snapshot_sha256")
    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError,
        match="positive integer",
    ):
        module.require_native_runtime_snapshot(kernel_only)


@pytest.mark.parametrize(
    "unsafe_path",
    ["/", "//usr/bin/python3.11", "/usr/bin/py\x00thon", "/usr/bin/py\nthon"],
)
def test_snapshot_validator_rejects_paths_measurement_cannot_emit(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_path: str,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)
    snapshot["file_rows"][0]["path"] = unsafe_path
    snapshot["mapping_rows"][0]["path"] = unsafe_path
    snapshot["file_rows"][0]["file_identity_sha256"] = module._sha256(
        module._file_identity_projection(snapshot["file_rows"][0])
    )
    snapshot["mapping_rows"][0]["backing_file_identity_sha256"] = snapshot["file_rows"][
        0
    ]["file_identity_sha256"]
    _rehash(snapshot, "snapshot_sha256")

    with pytest.raises(module.ValidationNativeRuntimeIdentityError, match="path"):
        module.require_native_runtime_snapshot(snapshot)


def test_measurement_and_validator_reject_duplicate_kernel_mapping_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _safe_maps() + _maps_line(path="[vdso]", start=0x5000, end=0x6000)
    monkeypatch.setattr(module, "_read_maps_bounded", lambda *, deadline: raw)
    with pytest.raises(module.ValidationNativeRuntimeIdentityError, match="duplicated"):
        module.measure_native_runtime_snapshot()

    snapshot = _measure_synthetic_snapshot(monkeypatch)
    duplicate = copy.deepcopy(snapshot["mapping_rows"][1])
    duplicate["ordinal"] = 2
    duplicate["address_start_hex"] = "5000"
    duplicate["address_end_hex"] = "6000"
    snapshot["mapping_rows"].append(duplicate)
    snapshot["mapping_count"] = 3
    _rehash(snapshot, "snapshot_sha256")
    with pytest.raises(module.ValidationNativeRuntimeIdentityError, match="duplicated"):
        module.require_native_runtime_snapshot(snapshot)


def test_complete_minimization_lifecycle_binds_request_phases_rows_and_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)
    request_sha256 = "1" * 64
    rows = _minimization_rows()
    pre = module.build_worker_runtime_pre_evidence(
        lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    lifecycle = module.build_complete_worker_runtime_lifecycle_evidence(
        lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        pre_evidence=pre,
        payload_rows=rows,
        post_snapshot=snapshot,
    )

    assert lifecycle["pre"]["phase"] == "pre"
    assert lifecycle["post"]["phase"] == "post"
    assert (
        lifecycle["payload_aggregate_sha256"]
        == lifecycle["payload"]["payload_aggregate_sha256"]
    )
    assert all(
        row["nested_variant_count"] is None
        for row in lifecycle["payload"]["payload_rows"]
    )
    assert (
        module.require_worker_runtime_lifecycle_evidence(
            lifecycle,
            expected_lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
            expected_worker_request_sha256=request_sha256,
            expected_payload_rows=rows,
        )
        == lifecycle
    )
    module.require_complete_worker_runtime_process_id(
        lifecycle,
        expected_process_id=snapshot["process_id"],
    )
    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError,
        match="mismatches",
    ):
        module.require_complete_worker_runtime_process_id(
            lifecycle,
            expected_process_id=snapshot["process_id"] + 1,
        )


def test_complete_energy_lifecycle_binds_59_nested_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)
    rows = _energy_rows()
    request_sha256 = "2" * 64
    pre = module.build_worker_runtime_pre_evidence(
        lane=module.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    lifecycle = module.build_complete_worker_runtime_lifecycle_evidence(
        lane=module.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=request_sha256,
        pre_evidence=pre,
        payload_rows=rows,
        post_snapshot=snapshot,
    )

    assert (
        sum(row["nested_variant_count"] for row in lifecycle["payload"]["payload_rows"])
        == 59
    )
    module.require_worker_runtime_lifecycle_evidence(
        lifecycle,
        expected_lane=module.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        expected_worker_request_sha256=request_sha256,
        expected_payload_rows=rows,
    )

    rows[0]["variant_results"].pop()
    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError, match="59 variants"
    ):
        module.require_worker_runtime_lifecycle_evidence(
            lifecycle,
            expected_lane=module.WORKER_RUNTIME_LANE_ENERGY_FORCE,
            expected_worker_request_sha256=request_sha256,
            expected_payload_rows=rows,
        )


def test_complete_energy_manifest_lifecycle_binds_wrapper_27_cases_and_59_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)
    rows = [_materialization_manifest_row()]
    request_sha256 = "7" * 64
    pre = module.build_worker_runtime_pre_evidence(
        lane=module.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    lifecycle = module.build_complete_worker_runtime_lifecycle_evidence(
        lane=module.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=request_sha256,
        pre_evidence=pre,
        payload_rows=rows,
        post_snapshot=snapshot,
    )

    metadata = lifecycle["payload"]["payload_rows"]
    assert metadata == [
        {
            "position": 0,
            "row_ordinal": 0,
            "row_id": "materialization_manifest",
            "row_sha256": module._sha256(rows[0]),
            "nested_case_count": 27,
            "nested_variant_count": 59,
        }
    ]
    module.require_worker_runtime_lifecycle_evidence(
        lifecycle,
        expected_lane=module.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        expected_worker_request_sha256=request_sha256,
        expected_payload_rows=rows,
    )

    tampered = copy.deepcopy(rows)
    manifest = tampered[0]["materialization_manifest"]
    manifest["cases"][0]["variants"].pop()
    manifest["cases"][0]["variant_count"] -= 1
    case = manifest["cases"][0]
    case["materialization_sha256"] = module._sha256(
        {key: value for key, value in case.items() if key != "materialization_sha256"}
    )
    manifest["coverage"]["variant_count"] = 58
    manifest["materialization_manifest_sha256"] = module._sha256(
        {
            key: value
            for key, value in manifest.items()
            if key != "materialization_manifest_sha256"
        }
    )
    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError, match="27 cases and 59 variants"
    ):
        module.require_worker_runtime_lifecycle_evidence(
            lifecycle,
            expected_lane=module.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
            expected_worker_request_sha256=request_sha256,
            expected_payload_rows=tampered,
        )


def test_lifecycle_validator_blocks_row_reorder_digest_identity_and_request_crosswire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)
    rows = _minimization_rows()
    request_sha256 = "3" * 64
    pre = module.build_worker_runtime_pre_evidence(
        lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    lifecycle = module.build_complete_worker_runtime_lifecycle_evidence(
        lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        pre_evidence=pre,
        payload_rows=rows,
        post_snapshot=snapshot,
    )

    reordered = copy.deepcopy(rows)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    changed = copy.deepcopy(rows)
    changed[0]["case_passed"] = False
    renamed = copy.deepcopy(rows)
    renamed[0]["case_id"] = "crosswired-case"
    for expected_rows in (reordered, changed, renamed):
        with pytest.raises(module.ValidationNativeRuntimeIdentityError):
            module.require_worker_runtime_lifecycle_evidence(
                lifecycle,
                expected_lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
                expected_worker_request_sha256=request_sha256,
                expected_payload_rows=expected_rows,
            )

    with pytest.raises(module.ValidationNativeRuntimeIdentityError):
        module.require_worker_runtime_lifecycle_evidence(
            lifecycle,
            expected_lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
            expected_worker_request_sha256="4" * 64,
            expected_payload_rows=rows,
        )


def test_phase_validator_and_pre_post_executable_set_equality_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)
    request_sha256 = "5" * 64
    pre = module.build_worker_runtime_pre_evidence(
        lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    phase_tamper = copy.deepcopy(pre)
    phase_tamper["phase"] = "post"
    _rehash(phase_tamper, "evidence_sha256")
    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError, match="phase|binding"
    ):
        module.require_worker_runtime_pre_evidence(phase_tamper)

    changed_snapshot = copy.deepcopy(snapshot)
    changed_snapshot["mapping_rows"][0]["address_start_hex"] = "1001"
    _rehash(changed_snapshot, "snapshot_sha256")
    rows = _minimization_rows()
    payload = module.build_worker_runtime_payload_evidence(
        lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        pre_evidence=pre,
        payload_rows=rows,
    )
    with pytest.raises(
        module.ValidationNativeRuntimeIdentityError, match="pre/post executable"
    ):
        module.build_worker_runtime_post_evidence(
            lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
            worker_request_sha256=request_sha256,
            pre_evidence=pre,
            payload_evidence=payload,
            payload_rows=rows,
            snapshot=changed_snapshot,
        )


def test_incomplete_lifecycle_has_optional_pre_and_null_payload_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _measure_synthetic_snapshot(monkeypatch)
    request_sha256 = "6" * 64
    pre = module.build_worker_runtime_pre_evidence(
        lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    for optional_pre in (None, pre):
        lifecycle = module.build_incomplete_worker_runtime_lifecycle_evidence(
            lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
            worker_request_sha256=request_sha256,
            failure_code="worker_timeout",
            pre_evidence=optional_pre,
        )
        assert lifecycle["payload"] is None
        assert lifecycle["post"] is None
        assert lifecycle["payload_aggregate_sha256"] is None
        module.require_worker_runtime_lifecycle_evidence(
            lifecycle,
            expected_lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
            expected_worker_request_sha256=request_sha256,
            expected_payload_rows=None,
        )

        tampered = copy.deepcopy(lifecycle)
        tampered["payload"] = {}
        _rehash(tampered, "lifecycle_sha256")
        with pytest.raises(
            module.ValidationNativeRuntimeIdentityError, match="retained payload"
        ):
            module.require_worker_runtime_lifecycle_evidence(
                tampered,
                expected_lane=module.WORKER_RUNTIME_LANE_MINIMIZATION,
                expected_worker_request_sha256=request_sha256,
                expected_payload_rows=None,
            )
