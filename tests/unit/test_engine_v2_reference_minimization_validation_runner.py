from __future__ import annotations

import ast
from copy import copy, deepcopy
from datetime import datetime, timezone
import hashlib
import io
import inspect
import json
import os
from pathlib import Path
import stat
import subprocess
import time
from types import SimpleNamespace
from typing import Mapping

import numpy as np
import pytest
import torch

import betelgeuze_engine_v2.physics.reference_minimization_validation_bootstrap as bootstrap
import betelgeuze_engine_v2.physics.reference_minimization_validation_dependency_identity as dependency_identity
import betelgeuze_engine_v2.physics.reference_minimization_validation_result_writer as result_writer_module
import betelgeuze_engine_v2.physics.reference_minimization_validation_run_start as run_start_module
import betelgeuze_engine_v2.physics.reference_minimization_validation_runner as module
import betelgeuze_engine_v2.physics.validation_native_runtime_identity as native_identity
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    cpu_minimization_validation_protocol_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_runner import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES,
    ReferenceMinimizationValidationRunnerAlreadyStartedError,
    ReferenceMinimizationValidationRunnerError,
    reference_minimization_validation_runner_contract_decision,
    reference_minimization_validation_runner_contract_document,
    reference_minimization_validation_runner_source_sha256,
    require_reference_minimization_validation_runner_contract_document,
    run_bounded_cpu_reference_minimization_validation,
)


NOW = datetime(2026, 7, 18, 5, 0, 0, tzinfo=timezone.utc)
NONCE = "a" * 64
RECEIPT_SHA256 = "b" * 64
FINGERPRINT_SHA256 = "c" * 64
COMMIT_SHA = "d" * 40
SOURCE_MANIFEST_SHA256 = "7" * 64
DEPENDENCIES = (
    ("cryptography-distribution", "a" * 64),
    ("numpy-distribution", "b" * 64),
    ("openssl-executable", "c" * 64),
    ("python-runtime-executable", "d" * 64),
    ("python-standard-library", "e" * 64),
    ("torch-distribution", "f" * 64),
)


def _environment_rows(
    *,
    python_hash_seed: int = 123,
    application_seed: int = 456,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            {
                module.REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV: str(
                    application_seed
                ),
                "CUDA_VISIBLE_DEVICES": "",
                "HIP_VISIBLE_DEVICES": "",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "MKL_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": str(python_hash_seed),
                "PYTHONPYCACHEPREFIX": "/dev/null",
                "ROCR_VISIBLE_DEVICES": "",
                "TZ": "UTC",
            }.items()
        )
    )


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def _receipt() -> SimpleNamespace:
    return SimpleNamespace(
        started_at_utc="2026-07-18T05:00:00Z",
        receipt_sha256=RECEIPT_SHA256,
        environment_fingerprint_sha256=FINGERPRINT_SHA256,
        code_commit_sha=COMMIT_SHA,
        runner_source_sha256=reference_minimization_validation_runner_source_sha256(),
        source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        dependency_artifact_sha256_rows=DEPENDENCIES,
        environment_variable_rows=_environment_rows(),
        command_argv=module.REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV,
        python_hash_seed=123,
        application_seed=456,
    )


def _install_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = _receipt()
    _install_fake_native_runtime(monkeypatch)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(
        module,
        "require_reference_minimization_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: receipt,
    )
    monkeypatch.setattr(
        module, "_require_clean_checked_out_code_commit", lambda expected: None
    )
    monkeypatch.setattr(
        module,
        "_require_isolated_python_bootstrap_runtime",
        lambda: (Path("/trusted"),),
    )
    monkeypatch.setattr(module, "_require_source_only_python_runtime", lambda: None)
    monkeypatch.setattr(
        module,
        "_observe_dependency_artifact_sha256_rows",
        lambda roots, **kwargs: dict(DEPENDENCIES),
    )

    def supervise(**kwargs: object) -> object:
        assert isinstance(kwargs["deadline"], float)
        request = _worker_request(source_sha256=receipt.runner_source_sha256)
        assert kwargs["worker_preflight_request"] == request
        return _complete_supervised_result(
            monkeypatch,
            request=request,
            rows=module._run_case_matrix_in_process(),
        )

    monkeypatch.setattr(module, "_run_supervised_case_matrix", supervise)


def _runner_request() -> dict[str, object]:
    return {
        "schema_id": module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID,
        "reservation_root": "/private/reservations",
        "artifact_output_root": "/private/results",
        "authorization_nonce_sha256": NONCE,
        "authorization_receipt": {"signed": "authorization"},
        "review_attestation": {"signed": "review"},
        "expected_implementation_author_identity_sha256": "9" * 64,
        "network_isolation_attestation": {"signed": "network"},
        "expected_code_commit_sha": COMMIT_SHA,
        "expected_runner_source_sha256": "8" * 64,
        "expected_dependency_artifact_sha256_rows": dict(DEPENDENCIES),
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [],
        "externally_conflicting_nonce_sha256s": [],
        "revoked_network_attestation_sha256s": [],
    }


def _worker_request(
    *,
    source_sha256: str = "8" * 64,
    dependency_roots: list[str] | None = None,
    python_hash_seed: int = 123,
    application_seed: int = 456,
) -> dict[str, object]:
    roots = ["/trusted"] if dependency_roots is None else dependency_roots
    environment = module._matrix_worker_environment(
        _environment_rows(
            python_hash_seed=python_hash_seed,
            application_seed=application_seed,
        ),
        roots,
    )
    return {
        "schema_id": (
            module.REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_REQUEST_SCHEMA_ID
        ),
        "expected_code_commit_sha": COMMIT_SHA,
        "expected_runner_source_sha256": source_sha256,
        "expected_dependency_artifact_sha256_rows": dict(DEPENDENCIES),
        "dependency_roots": roots,
        "expected_environment_receipt_sha256": RECEIPT_SHA256,
        "expected_environment_fingerprint_sha256": FINGERPRINT_SHA256,
        "expected_python_hash_seed": python_hash_seed,
        "expected_application_seed": application_seed,
        "expected_worker_environment": environment,
        "expected_worker_environment_sha256": module._sha256(environment),
        "expected_python_hash_probe_sha256": module._python_hash_probe_sha256(),
    }


def _native_snapshot() -> dict[str, object]:
    file_projection: dict[str, object] = {
        "ordinal": 0,
        "path": "/usr/bin/python3.11",
        "device_major_hex": "1",
        "device_minor_hex": "2",
        "inode": 3,
        "mode_octal": "0755",
        "uid": 0,
        "gid": 0,
        "link_count": 1,
        "size_bytes": 1,
        "mtime_ns": 0,
        "ctime_ns": 0,
        "sha256": "a" * 64,
    }
    file_row = {
        **file_projection,
        "file_identity_sha256": native_identity._sha256(
            native_identity._file_identity_projection(file_projection)
        ),
    }
    projection: dict[str, object] = {
        "schema_id": native_identity.NATIVE_RUNTIME_SNAPSHOT_SCHEMA_ID,
        "process_id": 1,
        "mapping_count": 1,
        "file_count": 1,
        "hashed_file_bytes": 1,
        "mapping_rows": [
            {
                "ordinal": 0,
                "address_start_hex": "1",
                "address_end_hex": "2",
                "permissions": "r-xp",
                "file_offset_hex": "0",
                "device_major_hex": "1",
                "device_minor_hex": "2",
                "inode": 3,
                "path": "/usr/bin/python3.11",
                "backing_kind": "file",
                "backing_file_identity_sha256": file_row["file_identity_sha256"],
            }
        ],
        "file_rows": [file_row],
    }
    return {**projection, "snapshot_sha256": module._sha256(projection)}


def _install_fake_native_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = _native_snapshot()
    real_pre = native_identity.build_worker_runtime_pre_evidence
    real_complete = native_identity.build_complete_worker_runtime_lifecycle_evidence
    monkeypatch.setattr(
        module,
        "build_worker_runtime_pre_evidence",
        lambda **kwargs: real_pre(**kwargs, snapshot=snapshot),
    )
    monkeypatch.setattr(
        module,
        "build_complete_worker_runtime_lifecycle_evidence",
        lambda **kwargs: real_complete(**kwargs, post_snapshot=snapshot),
    )


def _complete_worker_transcript(
    monkeypatch: pytest.MonkeyPatch,
    *,
    request: Mapping[str, object],
    rows: object,
) -> bytes:
    output = io.BytesIO()
    with monkeypatch.context() as context:
        context.setattr(
            module.sys,
            "stdin",
            SimpleNamespace(
                buffer=io.BytesIO(module._canonical_bytes(dict(request)) + b"\n")
            ),
        )
        context.setattr(module.sys, "stdout", SimpleNamespace(buffer=output))
        context.setattr(
            module, "_require_matrix_worker_preflight", lambda _request: None
        )
        context.setattr(module, "_run_case_matrix_in_process", lambda: rows)
        assert module._matrix_worker_main_from_standard_streams() == 0
    return output.getvalue()


def _complete_supervised_result(
    monkeypatch: pytest.MonkeyPatch,
    *,
    request: Mapping[str, object],
    rows: object,
):
    raw = _complete_worker_transcript(
        monkeypatch,
        request=request,
        rows=rows,
    )
    return module._decode_complete_matrix_worker_transcript(
        raw,
        worker_preflight_request=request,
    )


def _supervise_raw_transcript(
    monkeypatch: pytest.MonkeyPatch,
    *,
    request: Mapping[str, object],
    raw: bytes,
    timed_out: bool = False,
    succeeded: bool = True,
):
    monkeypatch.setattr(
        module,
        "_start_fixed_matrix_worker",
        lambda _request: SimpleNamespace(pid=1),
    )
    monkeypatch.setattr(
        module,
        "_communicate_fixed_matrix_worker",
        lambda *_args, **_kwargs: (raw, timed_out, succeeded),
    )
    return module._run_supervised_case_matrix(
        deadline=time.monotonic() + 10.0,
        worker_preflight_request=request,
    )


def _canonical_frame_line(frame: Mapping[str, object]) -> bytes:
    projection = dict(frame)
    projection.pop("frame_sha256", None)
    projection["frame_sha256"] = module._sha256(projection)
    return module._canonical_bytes(projection) + b"\n"


def _run(root: Path):
    return run_bounded_cpu_reference_minimization_validation(
        root,
        NONCE,
        expected_environment_receipt_sha256=RECEIPT_SHA256,
        expected_code_commit_sha=COMMIT_SHA,
        expected_dependency_artifact_sha256_rows=dict(DEPENDENCIES),
    )


def test_contract_is_frozen_and_all_claims_remain_closed() -> None:
    document = reference_minimization_validation_runner_contract_document()
    decision = reference_minimization_validation_runner_contract_decision()
    assert document["contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
    )
    assert document["bounds"]["case_count"] == 14
    assert REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES == 14
    assert document["observation"]["failure_inclusive"] is True
    assert document["observation"]["result_receipt_written"] is False
    assert document["entrypoint"]["result_receipt_finalized_in_same_verified_process"]
    assert document["worker"]["fresh_fixed_subprocess"] is True
    assert document["worker"]["multiprocessing_spawn_used"] is False
    assert document["worker"]["failure_complete_start_error_observation"] is True
    assert (
        document["worker"]["failure_complete_communication_error_observation"] is True
    )
    assert document["worker"]["child_dependency_roots_and_bytes_reverified"]
    assert document["worker"]["child_preflight_failure_emits_case_rows"] is False
    assert document["worker"]["exact_frame_count"] == 16
    assert document["worker"]["ordered_case_payload_frame_count"] == 14
    assert document["worker"]["native_mapping_lifetime_closure_claimed"] is False
    assert document["worker"][
        "timeout_nonzero_or_incomplete_transcript_discards_all_child_payloads"
    ]
    assert all(value is False for value in document["claim_policy"].values())
    assert (
        require_reference_minimization_validation_runner_contract_document(document)
        == document
    )
    assert decision["bounded_validation_runner_implemented"] is True
    assert decision["production_process_entrypoint_wired"] is True
    assert decision["preconfigured_trust_store_present"] is False
    assert decision["result_receipt_writer_implemented"] is True
    assert decision["claim_safe"] is False
    assert {
        "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES",
        "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID",
        "REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID",
        "REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_MAX_BYTES",
        "REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_PATH",
        "REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID",
    } <= set(module.__all__)


def test_contract_rejects_tamper_and_source_binds_bootstrap_and_runner() -> None:
    tampered = copy(reference_minimization_validation_runner_contract_document())
    tampered["claim_policy"] = dict(tampered["claim_policy"])
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="frozen"):
        require_reference_minimization_validation_runner_contract_document(tampered)

    runner_path = Path(inspect.getsourcefile(module) or "")
    bootstrap_path = Path(bootstrap.reference_minimization_validation_bootstrap_path())
    source_identity = {
        "schema_id": (
            "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/4.0.0"
        ),
        "sources": [
            {
                "path": "betelgeuze_engine_v2/physics/reference_minimization_validation_bootstrap.py",
                "sha256": hashlib.sha256(bootstrap_path.read_bytes()).hexdigest(),
            },
            {
                "path": "betelgeuze_engine_v2/physics/reference_minimization_validation_dependency_identity.py",
                "sha256": hashlib.sha256(
                    Path(module.__file__)
                    .with_name(
                        "reference_minimization_validation_dependency_identity.py"
                    )
                    .read_bytes()
                ).hexdigest(),
            },
            {
                "path": "betelgeuze_engine_v2/physics/validation_source_identity.py",
                "sha256": hashlib.sha256(
                    Path(module.__file__)
                    .with_name("validation_source_identity.py")
                    .read_bytes()
                ).hexdigest(),
            },
            {
                "path": "betelgeuze_engine_v2/physics/validation_native_runtime_identity.py",
                "sha256": hashlib.sha256(
                    Path(module.__file__)
                    .with_name("validation_native_runtime_identity.py")
                    .read_bytes()
                ).hexdigest(),
            },
            {
                "path": "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py",
                "sha256": hashlib.sha256(runner_path.read_bytes()).hexdigest(),
            },
        ],
    }
    assert (
        reference_minimization_validation_runner_source_sha256()
        == hashlib.sha256(module._canonical_bytes(source_identity)).hexdigest()
    )


def test_stdlib_bootstrap_has_no_package_or_third_party_imports() -> None:
    tree = ast.parse(Path(bootstrap.__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    assert imports == {
        "__future__",
        "hashlib",
        "importlib.util",
        "json",
        "os",
        "betelgeuze_engine_v2.physics",
        "select",
        "stat",
        "subprocess",
        "sys",
        "sysconfig",
        "time",
    }
    assert "torch" not in imports
    assert "numpy" not in imports
    assert bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH == (
        "/etc/betelgeuze/engine-v2/reference-minimization-validation-trust-anchors.json"
    )
    assert (
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RUNNER_REQUEST_SCHEMA_ID
        == module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_REQUEST_SCHEMA_ID
    )
    assert (
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_SCHEMA_ID
        == module.REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID
    )


def test_dependency_byte_identity_helper_is_stdlib_only_and_exactly_scoped() -> None:
    tree = ast.parse(Path(dependency_identity.__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    assert imports == {
        "__future__",
        "base64",
        "binascii",
        "csv",
        "hashlib",
        "importlib",
        "json",
        "os",
        "pathlib",
        "stat",
        "sys",
        "sysconfig",
        "time",
        "typing",
    }
    assert (
        dependency_identity.REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
        == (
            "cryptography-distribution",
            "numpy-distribution",
            "openssl-executable",
            "python-runtime-executable",
            "python-standard-library",
            "torch-distribution",
        )
    )


def test_stdlib_bootstrap_verifies_ed25519_without_importing_package_crypto() -> None:
    private_key = bytes.fromhex("31" * 32)
    public_key = ed25519_public_key_bytes(private_key)
    message = b"canonical-bootstrap-authorization"
    signature = sign_ed25519(message, private_key)

    assert bootstrap._verify_ed25519_with_trusted_openssl(
        message, signature, public_key
    )
    assert not bootstrap._verify_ed25519_with_trusted_openssl(
        message + b"-tampered", signature, public_key
    )


def test_runner_defers_numpy_and_torch_imports_until_bootstrap_verification() -> None:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    top_level_imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_level_imports.add(node.module or "")
    assert "numpy" not in top_level_imports
    assert "torch" not in top_level_imports


def test_exact_matrix_retains_all_success_and_fail_closed_rows() -> None:
    rows = module._run_case_matrix_in_process()
    protocol = cpu_minimization_validation_protocol_document()
    expected_ids = [row["case_id"] for row in protocol["case_manifest"]["cases"]]
    assert [row.case_id for row in rows] == expected_ids
    assert [row.ordinal for row in rows] == list(range(1, 15))
    assert len(rows) == 14
    assert all(row.case_passed for row in rows)
    assert len(module._canonical_bytes([row.to_dict() for row in rows])) < (
        module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_WORKER_OUTPUT_BYTES
    )
    assert sum(row.expected_outcome == "pass" for row in rows) == 8
    assert sum(row.expected_outcome == "fail_closed" for row in rows) == 6
    assert all(row.observed_error_code == row.expected_error_code for row in rows[8:])
    assert all(
        tuple(trace.trace_source for trace in row.coordinate_traces)
        == module.REFERENCE_MINIMIZATION_VALIDATION_TRACE_SOURCES
        for row in rows
    )
    assert all(
        len(trace.trace_sha256) == 64
        and len(trace.steps) == trace.energy_force_evaluation_count
        and [step.evaluation_index for step in trace.steps]
        == list(range(1, len(trace.steps) + 1))
        and all(len(step.step_identity_sha256) == 64 for step in trace.steps)
        for row in rows
        for trace in row.coordinate_traces
    )
    assert all(
        all(trace.trace_state == "evaluated" for trace in row.coordinate_traces)
        for row in rows[:8]
    )
    assert all(
        row.coordinate_traces[0].trace_state == "not_evaluated_expected_fail_closed"
        for row in rows[8:]
    )
    assert rows[12].coordinate_traces[1].trace_state == "evaluated"
    assert rows[12].coordinate_traces[1].rejected_step_count > 0
    assert all(
        row.coordinate_traces[1].trace_state == "not_evaluated_expected_fail_closed"
        for row in (*rows[8:12], rows[13])
    )
    checkpoint_rows = {row.case_id: dict(row.metric_values) for row in rows}
    for case_id in (
        "v1_checkpoint_restart_exact",
        "v2_constrained_checkpoint_restart_exact",
        "v2_fixed_born_checkpoint_restart_exact",
    ):
        assert checkpoint_rows[case_id]["checkpoint_resume_bitwise_equal"] == 1.0


@pytest.fixture(scope="module")
def complete_case_rows():
    return module._run_case_matrix_in_process()


def test_worker_emits_exact_pre_fourteen_payload_completion_frames(
    monkeypatch: pytest.MonkeyPatch,
    complete_case_rows: object,
) -> None:
    _install_fake_native_runtime(monkeypatch)
    request = _worker_request()
    raw = _complete_worker_transcript(
        monkeypatch,
        request=request,
        rows=complete_case_rows,
    )
    frames = [json.loads(line) for line in raw.splitlines()]
    assert (
        len(frames)
        == module.REFERENCE_MINIMIZATION_VALIDATION_MATRIX_WORKER_FRAME_COUNT
        == 16
    )
    assert [frame["frame_type"] for frame in frames] == [
        "preflight_complete",
        *(["case_payload"] * 14),
        "completion",
    ]
    assert [frame["frame_ordinal"] for frame in frames] == list(range(16))
    request_sha256 = module._sha256(request)
    assert all(frame["worker_request_sha256"] == request_sha256 for frame in frames)
    assert frames[0]["previous_frame_sha256"] is None
    assert all(
        frame["previous_frame_sha256"] == previous["frame_sha256"]
        for previous, frame in zip(frames, frames[1:])
    )
    result = module._decode_complete_matrix_worker_transcript(
        raw,
        worker_preflight_request=request,
    )
    evidence = result.worker_execution_evidence
    assert evidence.completion_state == "complete"
    assert evidence.failure_code is None
    assert evidence.native_pre_post_snapshot_equality_verified is True
    assert evidence.native_mapping_lifetime_closure_claimed is False
    assert len(evidence.case_frame_sha256_rows) == 14
    assert evidence.retained_case_aggregate_sha256 == module._sha256(
        [row.to_dict() for row in result.case_results]
    )
    assert tuple(row[2] for row in evidence.case_frame_sha256_rows) == tuple(
        module._sha256(row.to_dict()) for row in result.case_results
    )
    assert all(
        row["coordinate_traces"]
        for row in (frame["case_observation"] for frame in frames[1:15])
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "omitted_payload",
        "reordered_payload",
        "duplicated_payload",
        "missing_completion",
        "extra_completion",
        "request_crosswire",
        "aggregate_tamper",
        "post_tamper",
        "malformed_frame",
    ),
)
def test_supervisor_discards_every_payload_for_incomplete_or_tampered_transcript(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
    complete_case_rows: object,
) -> None:
    _install_fake_native_runtime(monkeypatch)
    request = _worker_request()
    raw = _complete_worker_transcript(
        monkeypatch,
        request=request,
        rows=complete_case_rows,
    )
    lines = raw.splitlines(keepends=True)
    if mutation == "omitted_payload":
        lines.pop(4)
    elif mutation == "reordered_payload":
        lines[2], lines[3] = lines[3], lines[2]
    elif mutation == "duplicated_payload":
        lines[3] = lines[2]
    elif mutation == "missing_completion":
        lines.pop()
    elif mutation == "extra_completion":
        lines.append(lines[-1])
    elif mutation == "request_crosswire":
        completion = json.loads(lines[-1])
        completion["worker_request_sha256"] = "0" * 64
        lines[-1] = _canonical_frame_line(completion)
    elif mutation == "aggregate_tamper":
        completion = json.loads(lines[-1])
        completion["retained_case_aggregate_sha256"] = "0" * 64
        lines[-1] = _canonical_frame_line(completion)
    elif mutation == "post_tamper":
        completion = json.loads(lines[-1])
        completion["runtime_post_evidence"]["evidence_sha256"] = "0" * 64
        lines[-1] = _canonical_frame_line(completion)
    else:
        lines[5] = b"{}\n"
    result = _supervise_raw_transcript(
        monkeypatch,
        request=request,
        raw=b"".join(lines),
    )
    assert len(result) == 14
    assert all(row.case_passed is False for row in result)
    assert all(
        row.observed_error_code == "runner_worker_output_invalid" for row in result
    )
    evidence = result.worker_execution_evidence
    assert evidence.completion_state == "incomplete"
    assert evidence.case_frame_sha256_rows == ()
    assert evidence.pre_frame_sha256 is None
    assert evidence.completion_frame_sha256 is None
    assert evidence.transcript_sha256 is None
    assert evidence.native_pre_post_snapshot_equality_verified is False


def test_timeout_after_partial_payload_discards_all_child_successes(
    monkeypatch: pytest.MonkeyPatch,
    complete_case_rows: object,
) -> None:
    _install_fake_native_runtime(monkeypatch)
    request = _worker_request()
    raw = _complete_worker_transcript(
        monkeypatch,
        request=request,
        rows=complete_case_rows,
    )
    partial = b"".join(raw.splitlines(keepends=True)[:7])
    result = _supervise_raw_transcript(
        monkeypatch,
        request=request,
        raw=partial,
        timed_out=True,
        succeeded=False,
    )
    assert len(result) == 14
    assert all(
        row.observed_error_code == "runner_wall_time_exhausted" for row in result
    )
    assert all(row.operational_result_sha256 is None for row in result)
    assert result.worker_execution_evidence.completion_state == "incomplete"
    assert result.worker_execution_evidence.case_frame_sha256_rows == ()


def test_nonzero_exit_discards_even_a_complete_valid_transcript(
    monkeypatch: pytest.MonkeyPatch,
    complete_case_rows: object,
) -> None:
    _install_fake_native_runtime(monkeypatch)
    request = _worker_request()
    raw = _complete_worker_transcript(
        monkeypatch,
        request=request,
        rows=complete_case_rows,
    )
    result = _supervise_raw_transcript(
        monkeypatch,
        request=request,
        raw=raw,
        succeeded=False,
    )
    assert len(result) == 14
    assert all(
        row.observed_error_code == "runner_worker_output_invalid" for row in result
    )
    assert result.worker_execution_evidence.completion_state == "incomplete"


def test_worker_execution_parser_enforces_complete_and_incomplete_cross_invariants(
    monkeypatch: pytest.MonkeyPatch,
    complete_case_rows: object,
) -> None:
    _install_fake_native_runtime(monkeypatch)
    request = _worker_request()
    complete = _complete_supervised_result(
        monkeypatch,
        request=request,
        rows=complete_case_rows,
    )
    payload = complete.worker_execution_evidence.to_dict()
    assert (
        module._worker_execution_evidence_from_payload(
            payload,
            case_results=complete.case_results,
        ).to_dict()
        == payload
    )
    mutations = []
    omitted_frame = deepcopy(payload)
    omitted_frame["case_frame_sha256_rows"].pop()
    mutations.append(omitted_frame)
    aggregate_tamper = deepcopy(payload)
    aggregate_tamper["retained_case_aggregate_sha256"] = "0" * 64
    mutations.append(aggregate_tamper)
    false_incomplete = deepcopy(payload)
    false_incomplete["completion_state"] = "incomplete"
    false_incomplete["failure_code"] = "runner_worker_output_invalid"
    mutations.append(false_incomplete)
    for mutation in mutations:
        with pytest.raises(ReferenceMinimizationValidationRunnerError):
            module._worker_execution_evidence_from_payload(
                mutation,
                case_results=complete.case_results,
            )

    incomplete = module._supervisor_failure_complete_matrix(
        "runner_worker_output_invalid",
        worker_preflight_request=request,
    )
    incomplete_payload = incomplete.worker_execution_evidence.to_dict()
    assert (
        module._worker_execution_evidence_from_payload(
            incomplete_payload,
            case_results=incomplete.case_results,
        ).completion_state
        == "incomplete"
    )
    with pytest.raises(ReferenceMinimizationValidationRunnerError):
        module._worker_execution_evidence_from_payload(
            incomplete_payload,
            case_results=complete.case_results,
        )


def test_case_observation_rejects_missing_reordered_or_crosswired_trace_data() -> None:
    source = module._run_case_matrix_in_process()[0].to_dict()
    mutations: list[dict[str, object]] = []

    missing_step = deepcopy(source)
    missing_step["coordinate_traces"][0]["steps"].pop()
    mutations.append(missing_step)

    reordered_steps = deepcopy(source)
    steps = reordered_steps["coordinate_traces"][0]["steps"]
    steps[0], steps[1] = steps[1], steps[0]
    mutations.append(reordered_steps)

    crosswired_source = deepcopy(source)
    crosswired_source["coordinate_traces"][0]["trace_source"] = "independent_oracle"
    mutations.append(crosswired_source)

    drifted_count = deepcopy(source)
    drifted_count["coordinate_traces"][0]["energy_force_evaluation_count"] += 1
    mutations.append(drifted_count)

    drifted_ledger = deepcopy(source)
    drifted_ledger["coordinate_traces"][0]["accepted_energy_ledger"] = []
    mutations.append(drifted_ledger)

    for payload in mutations:
        with pytest.raises(ReferenceMinimizationValidationRunnerError):
            module._case_observation_from_payload(payload)


def test_deadline_retains_every_pending_case_as_failure() -> None:
    rows = module._run_case_matrix_in_process(deadline=0.0)
    assert len(rows) == 14
    assert all(row.observed_error_code == "runner_wall_time_exhausted" for row in rows)
    assert all(row.case_passed is False for row in rows)


def test_supervisor_hard_stops_a_stalled_child_and_retains_all_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StalledProcess:
        args = ("python",)
        returncode: int | None = None

        def __init__(self) -> None:
            self.calls = 0
            self.killed = False

        def communicate(
            self, *, input: bytes | None = None, timeout: float
        ) -> tuple[bytes, bytes]:
            self.calls += 1
            if self.calls == 1:
                assert input == module._canonical_bytes(_worker_request()) + b"\n"
                raise subprocess.TimeoutExpired(self.args, timeout)
            assert input is None
            self.returncode = -9
            return b"", b""

        def kill(self) -> None:
            self.killed = True

    process = StalledProcess()
    monkeypatch.setattr(
        module,
        "_start_fixed_matrix_worker",
        lambda _roots: process,
    )
    monkeypatch.setattr(
        module,
        "_communicate_fixed_matrix_worker",
        lambda *_args, **_kwargs: (process.kill() or b"", True, False),
    )
    rows = module._run_supervised_case_matrix(
        deadline=time.monotonic() + 0.05,
        worker_preflight_request=_worker_request(),
    )
    assert len(rows) == 14
    assert all(row.observed_error_code == "runner_wall_time_exhausted" for row in rows)
    assert all(row.case_passed is False for row in rows)
    assert process.killed is True


def test_supervisor_retains_start_failure_as_fourteen_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_start(_roots: object) -> object:
        raise ReferenceMinimizationValidationRunnerError("secret")

    monkeypatch.setattr(module, "_start_fixed_matrix_worker", fail_start)
    rows = module._run_supervised_case_matrix(
        deadline=time.monotonic() + 1.0,
        worker_preflight_request=_worker_request(),
    )
    assert len(rows) == 14
    assert all(row.observed_error_code == "runner_worker_start_failed" for row in rows)
    assert all(row.case_passed is False for row in rows)


def test_supervisor_reaps_communication_failure_and_retains_fourteen_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenProcess:
        args = ("python",)
        returncode: int | None = None

        def __init__(self) -> None:
            self.calls = 0
            self.killed = False

        def communicate(
            self, *, input: bytes | None = None, timeout: float
        ) -> tuple[bytes, bytes]:
            self.calls += 1
            if self.calls == 1:
                raise BrokenPipeError("secret")
            self.returncode = -9
            return b"", b""

        def kill(self) -> None:
            self.killed = True

    process = BrokenProcess()
    monkeypatch.setattr(
        module,
        "_start_fixed_matrix_worker",
        lambda _roots: process,
    )
    monkeypatch.setattr(
        module,
        "_communicate_fixed_matrix_worker",
        lambda *_args, **_kwargs: (process.kill() or b"", False, False),
    )
    rows = module._run_supervised_case_matrix(
        deadline=time.monotonic() + 1.0,
        worker_preflight_request=_worker_request(),
    )
    assert len(rows) == 14
    assert all(
        row.observed_error_code == "runner_worker_output_invalid" for row in rows
    )
    assert process.killed is True


def test_fixed_worker_launch_uses_exact_flags_and_controlled_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    seen: dict[str, object] = {}

    def popen(args: list[str], **kwargs: object) -> object:
        seen["args"] = args
        seen["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(module.subprocess, "Popen", popen)
    request = _worker_request()
    monkeypatch.setenv("PYTHONHASHSEED", "999")
    monkeypatch.setenv(
        module.REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV,
        "999",
    )

    assert module._start_fixed_matrix_worker(request) is sentinel
    assert seen["args"] == [
        os.path.realpath(module.sys.executable),
        "-S",
        "-B",
        "-X",
        "pycache_prefix=/dev/null",
        "-c",
        module._REFERENCE_MINIMIZATION_VALIDATION_FIXED_WORKER_BOOTSTRAP,
    ]
    assert seen["kwargs"] == {
        "cwd": Path(module.__file__).resolve().parents[2],
        "env": request["expected_worker_environment"],
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL,
        "start_new_session": True,
    }
    assert seen["kwargs"]["env"]["PYTHONHASHSEED"] == "123"


def test_matrix_worker_request_rejects_python_hash_seed_above_uint32() -> None:
    request = _worker_request()
    environment = dict(request["expected_worker_environment"])
    environment["PYTHONHASHSEED"] = str(2**32)
    request["expected_python_hash_seed"] = 2**32
    request["expected_worker_environment"] = environment
    request["expected_worker_environment_sha256"] = module._sha256(environment)
    with pytest.raises(
        ReferenceMinimizationValidationRunnerError,
        match="hash seed",
    ):
        module._require_matrix_worker_preflight(request)


def test_real_fixed_worker_reaches_preflight_and_returns_failure_complete_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    required_environment = {
        module.REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV: "0",
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MKL_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONPYCACHEPREFIX": "/dev/null",
        "ROCR_VISIBLE_DEVICES": "",
        "TZ": "UTC",
    }
    for name, value in required_environment.items():
        monkeypatch.setenv(name, value)
    dependency_roots = sorted(
        {
            os.fspath(Path(np.__file__).resolve().parents[1]),
            os.fspath(Path(torch.__file__).resolve().parents[1]),
        }
    )
    request = _worker_request(
        dependency_roots=dependency_roots,
        python_hash_seed=0,
        application_seed=0,
    )

    process = module._start_fixed_matrix_worker(request)
    raw, timed_out, succeeded = module._communicate_fixed_matrix_worker(
        process,
        request,
        deadline=time.monotonic() + 30.0,
    )

    assert timed_out is False
    assert succeeded is False
    assert raw == b""


def test_run_persists_one_canonical_mode_0600_marker_and_no_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_preflight(monkeypatch)
    root = _root(tmp_path)
    observation = _run(root)
    marker = (
        root
        / f"{module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_PREFIX}{NONCE}.json"
    )
    payload = marker.read_bytes()
    assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    assert marker.stat().st_nlink == 1
    assert payload == module._canonical_bytes(json.loads(payload))
    assert observation.all_cases_observed is True
    assert observation.all_cases_passed is True
    assert observation.to_dict()["result_receipt_written"] is False
    assert observation.source_manifest_sha256 == SOURCE_MANIFEST_SHA256
    assert json.loads(payload)["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256
    assert list(root.iterdir()) == [marker]
    with pytest.raises(ReferenceMinimizationValidationRunnerAlreadyStartedError):
        _run(root)
    assert marker.exists()


def test_manifest_failure_does_not_consume_start_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_preflight(monkeypatch)
    root = _root(tmp_path)
    monkeypatch.setattr(
        module,
        "_validate_manifest_before_start",
        lambda: (_ for _ in ()).throw(
            ReferenceMinimizationValidationRunnerError("manifest tamper")
        ),
    )
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="tamper"):
        _run(root)
    assert list(root.iterdir()) == []


def test_marker_reader_rejects_hardlink_and_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_preflight(monkeypatch)
    root = _root(tmp_path)
    observation = _run(root)
    marker = (
        root
        / f"{module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_PREFIX}{NONCE}.json"
    )
    document = module.read_reference_minimization_validation_runner_start_record(
        root,
        NONCE,
        expected_record_sha256=observation.runner_start_record_sha256,
        expected_environment_receipt_sha256=RECEIPT_SHA256,
        expected_runner_source_sha256=observation.runner_source_sha256,
        expected_source_manifest_sha256=observation.source_manifest_sha256,
    )
    assert document["runner_start_record_sha256"] == (
        observation.runner_start_record_sha256
    )
    alias = tmp_path / "marker-alias"
    os.link(marker, alias)
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="securely"):
        module.read_reference_minimization_validation_runner_start_record(
            root,
            NONCE,
            expected_record_sha256=observation.runner_start_record_sha256,
            expected_environment_receipt_sha256=RECEIPT_SHA256,
            expected_runner_source_sha256=observation.runner_source_sha256,
            expected_source_manifest_sha256=observation.source_manifest_sha256,
        )
    alias.unlink()
    payload = json.loads(marker.read_text(encoding="ascii"))
    payload["claim_safe"] = True
    marker.write_bytes(module._canonical_bytes(payload))
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="identity"):
        module.read_reference_minimization_validation_runner_start_record(
            root,
            NONCE,
            expected_record_sha256=observation.runner_start_record_sha256,
            expected_environment_receipt_sha256=RECEIPT_SHA256,
            expected_runner_source_sha256=observation.runner_source_sha256,
            expected_source_manifest_sha256=observation.source_manifest_sha256,
        )


def test_preflight_rejects_receipt_crosswire_before_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_preflight(monkeypatch)
    root = _root(tmp_path)
    receipt = _receipt()
    receipt.runner_source_sha256 = "0" * 64
    monkeypatch.setattr(
        module,
        "require_reference_minimization_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: receipt,
    )
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="source"):
        _run(root)
    assert list(root.iterdir()) == []


def test_exact_module_entrypoint_dispatches_canonical_stdin_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _runner_request()
    response = {
        "schema_id": module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "claim_safe": False,
    }
    output = io.BytesIO()
    monkeypatch.setattr(
        module.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(module._canonical_bytes(request) + b"\n")),
    )
    monkeypatch.setattr(
        module.sys,
        "stdout",
        SimpleNamespace(buffer=output),
    )
    seen: dict[str, object] = {}

    def execute(parsed: Mapping[str, object]) -> dict[str, object]:
        seen["request"] = parsed
        return response

    monkeypatch.setattr(module, "_execute_runner_request", execute)

    assert module.main() == 0
    assert seen["request"] == request
    assert output.getvalue() == module._canonical_bytes(response) + b"\n"


def test_runner_request_rejects_noncanonical_or_self_authorizing_input_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _runner_request()
    canonical = module._canonical_bytes(request) + b"\n"
    self_authorizing = deepcopy(request)
    self_authorizing["trusted_reviewer_keys"] = {"self": "key"}
    duplicate_nested = canonical.replace(
        b'{"signed":"authorization"}',
        b'{"signed":"authorization","signed":"duplicate"}',
    )
    invalid_requests = (
        b"",
        b"{}",
        canonical[:-1],
        json.dumps(request).encode("ascii") + b"\n",
        module._canonical_bytes(self_authorizing) + b"\n",
        duplicate_nested,
        b"x" * module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_REQUEST_BYTES
        + b"\n",
    )
    calls = 0

    def execute(_request: Mapping[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"claim_safe": False}

    monkeypatch.setattr(module, "_execute_runner_request", execute)
    for raw in invalid_requests:
        output = io.BytesIO()
        monkeypatch.setattr(
            module.sys,
            "stdout",
            SimpleNamespace(buffer=output),
        )
        assert module._main_from_canonical_request(raw) == 2
        assert output.getvalue() == b""
    assert calls == 0


def test_standard_stream_entrypoint_rejects_read_error_or_nonbytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenInput:
        def read(self, _size: int) -> bytes:
            raise OSError("unavailable")

    monkeypatch.setattr(
        module.sys,
        "stdin",
        SimpleNamespace(buffer=BrokenInput()),
    )
    assert module._main_from_standard_streams() == 2
    monkeypatch.setattr(
        module.sys,
        "stdin",
        SimpleNamespace(buffer=SimpleNamespace(read=lambda _size: "not-bytes")),
    )
    assert module._main_from_standard_streams() == 2


def test_execute_runner_request_orders_environment_run_and_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _runner_request()
    request["revoked_authorization_receipt_sha256s"] = ["4" * 64]
    request["revoked_review_attestation_sha256s"] = ["5" * 64]
    request["externally_conflicting_nonce_sha256s"] = ["6" * 64]
    request["revoked_network_attestation_sha256s"] = ["7" * 64]
    events: list[str] = []
    reviewer_keys = {"reviewer": object()}
    operator_keys = {"operator": object()}
    environment = SimpleNamespace(receipt_sha256="1" * 64)
    observation = SimpleNamespace(observation_sha256="2" * 64)
    receipt = SimpleNamespace(receipt_sha256="3" * 64)

    monkeypatch.setattr(
        module,
        "_require_runner_root_outside_checkout",
        lambda _root, *, name: events.append(f"root:{name}"),
    )
    monkeypatch.setattr(
        module,
        "reference_minimization_validation_checked_out_code_commit_sha",
        lambda: events.append("head") or COMMIT_SHA,
    )
    monkeypatch.setattr(
        module,
        "_require_isolated_python_bootstrap_runtime",
        lambda: events.append("isolated") or (Path("/trusted"),),
    )
    monkeypatch.setattr(
        module,
        "_require_source_only_python_runtime",
        lambda: events.append("source-only"),
    )
    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        lambda _commit: events.append("clean"),
    )
    monkeypatch.setattr(
        module,
        "reference_minimization_validation_runner_source_sha256",
        lambda: events.append("source") or "8" * 64,
    )
    monkeypatch.setattr(
        module,
        "_observe_dependency_artifact_sha256_rows",
        lambda _roots, **kwargs: events.append("dependencies") or dict(DEPENDENCIES),
    )
    monkeypatch.setattr(
        module,
        "_load_preconfigured_trust_anchors",
        lambda: events.append("trust") or (reviewer_keys, operator_keys),
    )
    monkeypatch.setattr(
        module,
        "_configure_deterministic_torch_runtime",
        lambda: events.append("deterministic"),
    )

    def create_environment(*args: object, **kwargs: object) -> object:
        events.append("environment")
        assert args == (
            request["reservation_root"],
            request["artifact_output_root"],
        )
        assert kwargs["authorization_nonce_sha256"] == NONCE
        assert kwargs["authorization_receipt"] is request["authorization_receipt"]
        assert kwargs["review_attestation"] is request["review_attestation"]
        assert kwargs["trusted_reviewer_keys"] is reviewer_keys
        assert kwargs["expected_implementation_author_identity_sha256"] == "9" * 64
        assert kwargs["trusted_operator_keys"] is operator_keys
        assert (
            kwargs["network_isolation_attestation"]
            is request["network_isolation_attestation"]
        )
        assert kwargs["expected_code_commit_sha"] == COMMIT_SHA
        assert kwargs["expected_runner_source_sha256"] == "8" * 64
        assert kwargs["expected_dependency_artifact_sha256_rows"] == dict(DEPENDENCIES)
        assert kwargs["revoked_receipt_sha256s"] == ("4" * 64,)
        assert kwargs["revoked_review_attestation_sha256s"] == ("5" * 64,)
        assert kwargs["externally_conflicting_nonce_sha256s"] == ("6" * 64,)
        assert kwargs["revoked_network_attestation_sha256s"] == ("7" * 64,)
        return environment

    def run(*args: object, **kwargs: object) -> object:
        events.append("run")
        assert args == (request["artifact_output_root"], NONCE)
        assert kwargs["expected_environment_receipt_sha256"] == (
            environment.receipt_sha256
        )
        assert kwargs["expected_code_commit_sha"] == COMMIT_SHA
        assert kwargs["expected_dependency_artifact_sha256_rows"] == dict(DEPENDENCIES)
        return observation

    def write(*args: object, **kwargs: object) -> object:
        events.append("writer")
        assert args[:2] == (request["artifact_output_root"], NONCE)
        assert args[2] is observation
        assert kwargs["review_attestation"] is request["review_attestation"]
        assert kwargs["authorization_receipt"] is request["authorization_receipt"]
        assert kwargs["trusted_reviewer_keys"] is reviewer_keys
        assert kwargs["expected_implementation_author_identity_sha256"] == "9" * 64
        assert kwargs["trusted_operator_keys"] is operator_keys
        assert kwargs["revoked_authorization_receipt_sha256s"] == ("4" * 64,)
        assert kwargs["revoked_review_attestation_sha256s"] == ("5" * 64,)
        assert kwargs["externally_conflicting_nonce_sha256s"] == ("6" * 64,)
        return receipt

    monkeypatch.setattr(
        run_start_module,
        "create_reference_minimization_validation_execution_environment_receipt",
        create_environment,
    )
    monkeypatch.setattr(
        module,
        "run_bounded_cpu_reference_minimization_validation",
        run,
    )
    monkeypatch.setattr(
        result_writer_module,
        "write_reference_minimization_validation_result_receipt",
        write,
    )

    response = module._execute_runner_request(request)

    assert events == [
        "root:reservation root",
        "root:artifact output root",
        "head",
        "isolated",
        "source-only",
        "clean",
        "source",
        "dependencies",
        "trust",
        "deterministic",
        "environment",
        "run",
        "writer",
    ]
    assert response == {
        "schema_id": module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "environment_receipt_sha256": "1" * 64,
        "observation_sha256": "2" * 64,
        "result_receipt_sha256": "3" * 64,
        "production_validation_results_collected": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def test_entrypoint_emits_nothing_when_finalization_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = io.BytesIO()
    monkeypatch.setattr(
        module.sys,
        "stdout",
        SimpleNamespace(buffer=output),
    )
    monkeypatch.setattr(
        module,
        "_execute_runner_request",
        lambda _request: (_ for _ in ()).throw(RuntimeError("secret")),
    )
    assert (
        module._main_from_canonical_request(
            module._canonical_bytes(_runner_request()) + b"\n"
        )
        == 2
    )
    assert output.getvalue() == b""


def test_preconfigured_trust_store_parses_exact_ed25519_keys_and_stats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schema_id": module.REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID,
        "reviewer_keys": [
            {
                "key_id": "reviewer",
                "reviewer_identity_sha256": "8" * 64,
                "verification_key_hex": "aa" * 32,
            }
        ],
        "operator_keys": [
            {
                "key_id": "operator",
                "operator_identity_sha256": "9" * 64,
                "verification_key_hex": "bb" * 32,
            }
        ],
    }
    store_path = tmp_path / "trust-store.json"
    store_path.write_bytes(module._canonical_bytes(payload) + b"\n")
    store_path.chmod(0o600)
    validate_file = module._validate_preconfigured_trust_file
    monkeypatch.setattr(
        module,
        "_open_preconfigured_trust_store",
        lambda: os.open(store_path, os.O_RDONLY | os.O_CLOEXEC),
    )
    monkeypatch.setattr(
        module,
        "_validate_preconfigured_trust_file",
        lambda _file_stat: None,
    )

    reviewer_keys, operator_keys = module._load_preconfigured_trust_anchors()

    assert reviewer_keys["reviewer"].verification_key == b"\xaa" * 32
    assert operator_keys["operator"].verification_key == b"\xbb" * 32
    module._validate_preconfigured_trust_directory(
        SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    )
    with pytest.raises(ReferenceMinimizationValidationRunnerError):
        module._validate_preconfigured_trust_directory(
            SimpleNamespace(st_mode=stat.S_IFDIR | 0o777, st_uid=0)
        )
    validate_file(
        SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600,
            st_uid=0,
            st_nlink=1,
            st_size=store_path.stat().st_size,
        )
    )
    with pytest.raises(ReferenceMinimizationValidationRunnerError):
        module._trusted_reviewer_keys_from_store(
            [
                {
                    "key_id": "reviewer",
                    "reviewer_identity_sha256": "8" * 64,
                    "verification_key_hex": "aa" * 31,
                }
            ]
        )
    invalid_payloads = (
        module._canonical_bytes({**payload, "schema_id": "wrong"}) + b"\n",
        module._canonical_bytes({**payload, "operator_keys": []}) + b"\n",
        (
            b'{"operator_keys":[],"operator_keys":[],"reviewer_keys":[],'
            b'"schema_id":"'
            + module.REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_SCHEMA_ID.encode(
                "ascii"
            )
            + b'"}\n'
        ),
        module._canonical_bytes(payload),
    )
    for raw in invalid_payloads:
        store_path.write_bytes(raw)
        with pytest.raises(ReferenceMinimizationValidationRunnerError):
            module._load_preconfigured_trust_anchors()


def test_preconfigured_trust_store_uses_dirfd_nofollow_and_nonblocking_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_PATH",
        "/etc/betelgeuze/engine-v2/trust-store.json",
    )
    calls: list[tuple[object, int, int | None]] = []
    closed: list[int] = []
    descriptors = iter((10, 11, 12, 13, 14))

    def open_file(path: object, flags: int, *, dir_fd: int | None = None) -> int:
        calls.append((path, flags, dir_fd))
        return next(descriptors)

    def file_stat(descriptor: int) -> SimpleNamespace:
        if descriptor == 14:
            return SimpleNamespace(
                st_mode=stat.S_IFREG | 0o600,
                st_uid=0,
                st_nlink=1,
                st_size=1,
            )
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)

    monkeypatch.setattr(module.os, "open", open_file)
    monkeypatch.setattr(module.os, "supports_dir_fd", {open_file})
    monkeypatch.setattr(module.os, "fstat", file_stat)
    monkeypatch.setattr(module.os, "close", closed.append)

    assert module._open_preconfigured_trust_store() == 14
    directory_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
    file_flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
    assert calls == [
        ("/", directory_flags, None),
        ("etc", directory_flags, 10),
        ("betelgeuze", directory_flags, 11),
        ("engine-v2", directory_flags, 12),
        ("trust-store.json", file_flags, 13),
    ]
    assert closed == [10, 11, 12, 13]


def test_preconfigured_trust_store_rejects_special_or_mutable_files() -> None:
    valid = {
        "st_mode": stat.S_IFREG | 0o600,
        "st_uid": 0,
        "st_nlink": 1,
        "st_size": 1,
    }
    mutations = (
        {"st_mode": stat.S_IFLNK | 0o600},
        {"st_mode": stat.S_IFIFO | 0o600},
        {"st_mode": stat.S_IFSOCK | 0o600},
        {"st_mode": stat.S_IFCHR | 0o600},
        {"st_mode": stat.S_IFBLK | 0o600},
        {"st_uid": 1},
        {"st_mode": stat.S_IFREG | 0o640},
        {"st_nlink": 2},
        {"st_size": 0},
        {
            "st_size": (
                module.REFERENCE_MINIMIZATION_VALIDATION_TRUST_STORE_MAX_BYTES + 1
            )
        },
    )
    for mutation in mutations:
        with pytest.raises(ReferenceMinimizationValidationRunnerError):
            module._validate_preconfigured_trust_file(
                SimpleNamespace(**{**valid, **mutation})
            )


def test_bootstrap_trust_store_open_is_nofollow_and_nonblocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = (
        bootstrap._canonical_bytes(
            {
                "schema_id": (
                    bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_SCHEMA_ID
                ),
                "reviewer_keys": [],
                "operator_keys": [
                    {
                        "key_id": "operator",
                        "operator_identity_sha256": "7" * 64,
                        "verification_key_hex": "aa" * 32,
                    }
                ],
            }
        )
        + b"\n"
    )
    reads = iter((payload, b""))
    seen: dict[str, object] = {}
    file_stat = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o600,
        st_uid=0,
        st_nlink=1,
        st_size=len(payload),
        st_dev=1,
        st_ino=2,
    )

    def open_file(path: object, flags: int) -> int:
        seen["open"] = (path, flags)
        return 20

    monkeypatch.setattr(
        bootstrap,
        "_require_root_owned_read_only_directory",
        lambda path: path,
    )
    monkeypatch.setattr(bootstrap.os, "open", open_file)
    monkeypatch.setattr(bootstrap.os, "fstat", lambda descriptor: file_stat)
    monkeypatch.setattr(bootstrap.os, "read", lambda descriptor, size: next(reads))
    monkeypatch.setattr(
        bootstrap.os, "close", lambda descriptor: seen.setdefault("closed", descriptor)
    )

    keys = bootstrap._load_bootstrap_operator_keys()
    assert keys == {"operator": ("7" * 64, b"\xaa" * 32)}
    assert seen["open"] == (
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH,
        os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    assert seen["closed"] == 20


def test_bootstrap_authorization_binds_nonce_author_and_dependencies_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _runner_request()
    projection = {
        "authorization_key_id": "operator",
        "authorization_operator_identity_sha256": "7" * 64,
        "authorization_nonce_sha256": request["authorization_nonce_sha256"],
        "implementation_author_identity_sha256": request[
            "expected_implementation_author_identity_sha256"
        ],
        "code_commit_sha": request["expected_code_commit_sha"],
        "runner_source_sha256": request["expected_runner_source_sha256"],
        "dependency_artifact_sha256_rows": [
            {"artifact_id": key, "sha256": value} for key, value in sorted(DEPENDENCIES)
        ],
    }
    signed = dict(projection)
    signed["receipt_sha256"] = hashlib.sha256(
        bootstrap._canonical_bytes(projection)
    ).hexdigest()
    signed["signature"] = {
        "algorithm": "ed25519",
        "key_id": "operator",
        "value": "ab" * 64,
    }
    request["authorization_receipt"] = signed
    monkeypatch.setattr(
        bootstrap,
        "_load_bootstrap_operator_keys",
        lambda: {"operator": ("7" * 64, b"k" * 32)},
    )
    monkeypatch.setattr(
        bootstrap,
        "_verify_ed25519_with_trusted_openssl",
        lambda *_args: True,
    )

    bootstrap._require_bootstrap_authorization_signature(
        request,
        expected_commit=COMMIT_SHA,
        expected_source="8" * 64,
    )
    for field, replacement in (
        ("authorization_nonce_sha256", "0" * 64),
        ("expected_implementation_author_identity_sha256", "1" * 64),
        (
            "expected_dependency_artifact_sha256_rows",
            {**dict(DEPENDENCIES), DEPENDENCIES[0][0]: "2" * 64},
        ),
    ):
        tampered = deepcopy(request)
        tampered[field] = replacement
        with pytest.raises(
            bootstrap._ReferenceMinimizationValidationBootstrapError,
            match="binding",
        ):
            bootstrap._require_bootstrap_authorization_signature(
                tampered,
                expected_commit=COMMIT_SHA,
                expected_source="8" * 64,
            )


def test_minimization_bootstrap_outer_reexecs_before_reading_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_bootstrap = bootstrap.reference_minimization_validation_bootstrap_path()
    executable = os.path.realpath(os.sys.executable)
    seen: dict[str, object] = {}
    monkeypatch.delenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        raising=False,
    )
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv(
        module.REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV,
        str(2**63 - 1),
    )
    monkeypatch.setenv("PYTHONHOME", "/hostile")
    monkeypatch.setattr(
        bootstrap,
        "_prepare_isolated_outer_launcher",
        lambda **kwargs: (executable, expected_bootstrap),
    )
    monkeypatch.setattr(
        bootstrap,
        "_read_bootstrap_request",
        lambda: (_ for _ in ()).throw(AssertionError("stdin read before exec")),
    )
    monkeypatch.setattr(
        bootstrap.os,
        "chdir",
        lambda path: seen.setdefault("cwd", path),
    )

    def reject_execve(
        path: str,
        argv: tuple[str, ...],
        environment: dict[str, str],
    ) -> None:
        seen.update(path=path, argv=argv, environment=environment)
        raise OSError("stop after capture")

    monkeypatch.setattr(bootstrap.os, "execve", reject_execve)

    assert bootstrap.main() == 2
    assert seen["cwd"] == "/"
    assert seen["path"] == executable
    assert seen["argv"] == (
        executable,
        *bootstrap.REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    environment = seen["environment"]
    assert isinstance(environment, dict)
    assert environment["PYTHONHASHSEED"] == "0"
    assert environment[
        module.REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV
    ] == str(2**63 - 1)
    assert "PYTHONHOME" not in environment


@pytest.mark.parametrize("seed", ["-1", "01", "random", "4294967296"])
def test_minimization_bootstrap_rejects_invalid_python_hash_seed(
    monkeypatch: pytest.MonkeyPatch,
    seed: str,
) -> None:
    monkeypatch.setenv("PYTHONHASHSEED", seed)
    monkeypatch.setenv(
        module.REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV,
        "456",
    )
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="PYTHONHASHSEED",
    ):
        bootstrap.reference_minimization_validation_controlled_inner_environment()


def test_bootstrap_main_checks_source_and_dependencies_before_runner_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    state = (
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
        "bootstrap",
        "/checkout",
        ("/trusted",),
        ("/checkout", "/trusted"),
    )
    source_manifest = {"verified": True}
    expected_state = (*state, bootstrap._canonical_bytes(source_manifest))
    raw = module._canonical_bytes(_runner_request()) + b"\n"
    attribute = bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE
    monkeypatch.delattr(bootstrap.sys, attribute, raising=False)
    monkeypatch.setattr(
        bootstrap,
        "_prepare_seeded_controlled_import_boundary",
        lambda **kwargs: state,
    )
    monkeypatch.setenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
    )
    monkeypatch.setenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        (time.monotonic() + 10.0).hex(),
    )
    monkeypatch.setattr(
        bootstrap,
        "_read_bootstrap_request",
        lambda: (raw, _runner_request()),
    )
    monkeypatch.setattr(
        bootstrap,
        "_require_signed_clean_checkout_before_import",
        lambda repository_root, request, **kwargs: (
            events.append("signed-clean") or source_manifest
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "_require_observed_dependency_artifact_rows_before_import",
        lambda repository_root, roots, request, **kwargs: events.append("dependencies"),
    )

    def run_runner(received: bytes) -> int:
        assert getattr(bootstrap.sys, attribute) == expected_state
        assert received == raw
        events.append("runner")
        return 0

    monkeypatch.setattr(module, "_main_from_canonical_request", run_runner)

    assert bootstrap.main() == 0
    assert events == ["signed-clean", "dependencies", "runner"]


def test_bootstrap_main_blocks_runner_when_dependency_observation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = (
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
        "bootstrap",
        "/checkout",
        ("/trusted",),
        ("/checkout", "/trusted"),
    )
    attribute = bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE
    monkeypatch.delattr(bootstrap.sys, attribute, raising=False)
    monkeypatch.setattr(
        bootstrap,
        "_prepare_seeded_controlled_import_boundary",
        lambda **kwargs: state,
    )
    monkeypatch.setenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_STATE,
    )
    monkeypatch.setenv(
        bootstrap.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        (time.monotonic() + 10.0).hex(),
    )
    monkeypatch.setattr(
        bootstrap,
        "_read_bootstrap_request",
        lambda: (b"request\n", _runner_request()),
    )
    monkeypatch.setattr(
        bootstrap,
        "_require_signed_clean_checkout_before_import",
        lambda repository_root, request, **kwargs: None,
    )
    monkeypatch.setattr(
        bootstrap,
        "_require_observed_dependency_artifact_rows_before_import",
        lambda repository_root, roots, request, **kwargs: (_ for _ in ()).throw(
            RuntimeError("secret")
        ),
    )
    monkeypatch.setattr(
        module,
        "_main_from_canonical_request",
        lambda raw: (_ for _ in ()).throw(AssertionError("runner imported")),
    )

    assert bootstrap.main() == 2
    assert not hasattr(bootstrap.sys, attribute)


def test_matrix_worker_preflight_rechecks_runtime_before_deterministic_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    repository_root = Path(module.__file__).resolve().parents[2]
    monkeypatch.chdir(repository_root)
    request = _worker_request()
    expected_environment = request["expected_worker_environment"]
    assert isinstance(expected_environment, dict)
    monkeypatch.setattr(module.os, "environ", dict(expected_environment))
    executable = os.path.realpath(os.fspath(Path(os.sys.executable)))
    expected_argv = (
        executable,
        "-S",
        "-B",
        "-X",
        "pycache_prefix=/dev/null",
        "-c",
        module._REFERENCE_MINIMIZATION_VALIDATION_FIXED_WORKER_BOOTSTRAP,
    )
    monkeypatch.setattr(
        module,
        "sys",
        SimpleNamespace(
            executable=executable,
            flags=SimpleNamespace(
                isolated=0,
                ignore_environment=0,
                no_site=1,
                no_user_site=1,
                dont_write_bytecode=1,
                hash_randomization=1,
            ),
            orig_argv=expected_argv,
            argv=["-c"],
        ),
    )
    monkeypatch.setattr(
        module,
        "_read_matrix_worker_process_argv",
        lambda: expected_argv,
    )
    monkeypatch.setattr(
        module,
        "_require_source_only_python_runtime",
        lambda: events.append("source-only"),
    )
    monkeypatch.setattr(
        module,
        "_require_trusted_dependency_roots",
        lambda _roots: events.append("roots") or (Path("/trusted"),),
    )
    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        lambda _commit: events.append("clean"),
    )
    monkeypatch.setattr(
        module,
        "reference_minimization_validation_runner_source_sha256",
        lambda: events.append("source") or "8" * 64,
    )
    monkeypatch.setattr(
        module,
        "_observe_dependency_artifact_sha256_rows",
        lambda _roots, **kwargs: events.append("dependencies") or dict(DEPENDENCIES),
    )
    monkeypatch.setattr(
        module,
        "_configure_deterministic_torch_runtime",
        lambda seed: events.append(f"deterministic:{seed}"),
    )
    module._require_matrix_worker_preflight(request)
    assert events == [
        "source-only",
        "roots",
        "clean",
        "source",
        "dependencies",
        "deterministic:456",
    ]


def test_matrix_worker_preflight_failure_emits_no_case_rows_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = io.BytesIO()
    monkeypatch.setattr(
        module.sys,
        "stdin",
        SimpleNamespace(
            buffer=io.BytesIO(module._canonical_bytes(_worker_request()) + b"\n")
        ),
    )
    monkeypatch.setattr(module.sys, "stdout", SimpleNamespace(buffer=output))
    monkeypatch.setattr(
        module,
        "_require_matrix_worker_preflight",
        lambda _request: (_ for _ in ()).throw(RuntimeError("secret")),
    )
    monkeypatch.setattr(
        module,
        "_run_case_matrix_in_process",
        lambda: (_ for _ in ()).throw(AssertionError("evaluator called")),
    )

    assert module._matrix_worker_main_from_standard_streams() == 2
    assert output.getvalue() == b""


def test_matrix_worker_request_rejects_noncanonical_and_duplicate_input() -> None:
    canonical = module._canonical_bytes(_worker_request()) + b"\n"
    duplicate = canonical.replace(
        b'"dependency_roots":["/trusted"]',
        b'"dependency_roots":["/trusted"],"dependency_roots":["/other"]',
    )
    for raw in (
        b"",
        canonical[:-1],
        json.dumps(_worker_request()).encode("ascii") + b"\n",
        duplicate,
    ):
        with pytest.raises(ReferenceMinimizationValidationRunnerError):
            module._load_matrix_worker_request(raw)


def test_direct_library_run_requires_external_trust_bootstrap(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ReferenceMinimizationValidationRunnerError,
        match="seeded controlled trust bootstrap",
    ):
        _run(_root(tmp_path))


def test_real_isolated_bootstrap_fails_closed_without_production_request() -> None:
    bootstrap_path = Path(bootstrap.__file__).resolve()
    result = subprocess.run(
        [
            os.fspath(Path(os.sys.executable).resolve()),
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            os.fspath(bootstrap_path),
        ],
        input=b"{}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == b""
