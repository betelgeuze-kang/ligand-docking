from __future__ import annotations

import ast
from copy import copy, deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import io
import inspect
import json
import os
from pathlib import Path
import py_compile
import stat
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import pytest

from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    AuthorizationOperatorTrustAnchor,
    build_signed_reference_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_validation_nonce_reservation import (
    reserve_reference_validation_authorization_nonce,
)
from betelgeuze_engine_v2.physics.reference_validation_protocol import (
    frozen_cpu_reference_validation_protocol,
)
from betelgeuze_engine_v2.physics.reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    ScientificReviewerTrustAnchor,
    build_signed_reference_validation_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_validation_run_start import (
    build_signed_reference_validation_network_isolation_attestation,
    reference_validation_artifact_output_root_identity_sha256,
)
import betelgeuze_engine_v2.physics.reference_validation_bootstrap as bootstrap_module
import betelgeuze_engine_v2.physics.reference_validation_dependency_identity as dependency_identity
import betelgeuze_engine_v2.physics.reference_minimization_validation_bootstrap as minimization_bootstrap_module
import betelgeuze_engine_v2.physics.reference_minimization_validation_dependency_identity as minimization_dependency_identity
import betelgeuze_engine_v2.physics.reference_validation_run_start as run_start_module
import betelgeuze_engine_v2.physics.validation_native_runtime_identity as native_identity
import betelgeuze_engine_v2.physics.validation_source_identity as source_identity
from betelgeuze_engine_v2.physics.reference_validation_runner import (
    FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256,
    REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID,
    REFERENCE_VALIDATION_RUNNER_MAX_CASES,
    REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
    REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID,
    ReferenceValidationRunnerAlreadyStartedError,
    ReferenceValidationRunnerError,
    reference_validation_runner_contract_decision,
    reference_validation_runner_contract_document,
    reference_validation_runner_source_sha256,
    reference_validation_checked_out_code_commit_sha,
    require_reference_validation_runner_contract_document,
    run_bounded_cpu_reference_validation,
)
import betelgeuze_engine_v2.physics.reference_validation_runner as module


NOW = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
AUTHORIZATION_NONCE = "e" * 64
ENVIRONMENT_RECEIPT_SHA256 = "1" * 64
ENVIRONMENT_FINGERPRINT_SHA256 = "2" * 64
AUTHORIZATION_RECEIPT_SHA256 = "3" * 64
CODE_COMMIT_SHA = "4" * 40
SOURCE_MANIFEST_SHA256 = "b" * 64
BOOTSTRAP_SOURCE_MANIFEST = source_identity._manifest_document(
    CODE_COMMIT_SHA,
    [
        {
            "path": "betelgeuze_engine_v2/__init__.py",
            "git_mode": "100644",
            "git_blob_oid": "c" * 40,
            "sha256": "d" * 64,
            "size": 1,
        }
    ],
)
DEPENDENCY_ROWS = {
    "cryptography-distribution": "5" * 64,
    "numpy-distribution": "6" * 64,
    "openssl-executable": "7" * 64,
    "python-runtime-executable": "8" * 64,
    "python-standard-library": "9" * 64,
    "torch-distribution": "a" * 64,
}
MANIFEST_WORKER_REQUEST_SHA256 = "c" * 64
CASE_WORKER_REQUEST_SHA256 = "d" * 64


def _environment_rows(
    *,
    python_hash_seed: int = 123,
    application_seed: int = 456,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            {
                module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV: str(application_seed),
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


def _private_root(tmp_path: Path, name: str = "outputs") -> Path:
    root = tmp_path / name
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def _receipt(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "started_at_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "receipt_sha256": ENVIRONMENT_RECEIPT_SHA256,
        "environment_fingerprint_sha256": ENVIRONMENT_FINGERPRINT_SHA256,
        "authorization_receipt_sha256": AUTHORIZATION_RECEIPT_SHA256,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "code_commit_sha": CODE_COMMIT_SHA,
        "runner_source_sha256": reference_validation_runner_source_sha256(),
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "dependency_artifact_sha256_rows": tuple(sorted(DEPENDENCY_ROWS.items())),
        "environment_variable_rows": _environment_rows(),
        "python_hash_seed": 123,
        "application_seed": 456,
        "command_argv": module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _test_native_snapshot() -> dict[str, Any]:
    file_projection = {
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
    projection = {
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
    return {
        **projection,
        "snapshot_sha256": native_identity._sha256(projection),
    }


def _complete_worker_lifecycle(
    *,
    lane: str,
    worker_request_sha256: str,
    payload_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    snapshot = _test_native_snapshot()
    pre_evidence = native_identity.build_worker_runtime_pre_evidence(
        lane=lane,
        worker_request_sha256=worker_request_sha256,
        snapshot=snapshot,
    )
    return native_identity.build_complete_worker_runtime_lifecycle_evidence(
        lane=lane,
        worker_request_sha256=worker_request_sha256,
        pre_evidence=pre_evidence,
        payload_rows=payload_rows,
        post_snapshot=snapshot,
    )


def _fixture_worker_request(
    *,
    worker_kind: str,
    materialization_manifest_sha256: str | None,
    runner_start_record_sha256: str | None,
    receipt: SimpleNamespace | None = None,
    code_commit_sha: str = CODE_COMMIT_SHA,
    runner_source_sha256: str | None = None,
    source_manifest_sha256: str = SOURCE_MANIFEST_SHA256,
    authorization_nonce_sha256: str = AUTHORIZATION_NONCE,
    dependency_rows: Mapping[str, str] = DEPENDENCY_ROWS,
) -> dict[str, Any]:
    selected = receipt or _receipt(
        code_commit_sha=code_commit_sha,
        runner_source_sha256=runner_source_sha256
        or reference_validation_runner_source_sha256(),
        source_manifest_sha256=source_manifest_sha256,
        authorization_nonce_sha256=authorization_nonce_sha256,
    )
    worker_environment = module._case_worker_environment(
        selected.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    return module._fixed_worker_request(
        worker_kind=worker_kind,
        expected_materialization_manifest_sha256=materialization_manifest_sha256,
        expected_code_commit_sha=code_commit_sha,
        expected_runner_source_sha256=(
            runner_source_sha256 or selected.runner_source_sha256
        ),
        expected_source_manifest_sha256=source_manifest_sha256,
        expected_authorization_nonce_sha256=authorization_nonce_sha256,
        expected_runner_start_record_sha256=runner_start_record_sha256,
        expected_dependency_artifact_sha256_rows=dependency_rows,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=selected,
        worker_environment=worker_environment,
    )


def _frozen_manifest_worker_result(
    receipt: SimpleNamespace | None = None,
) -> tuple[
    Any,
    list[Mapping[str, Any]],
    str,
    dict[str, Any],
    dict[str, Any],
]:
    protocol, manifest = module._load_frozen_case_manifest_document()
    selected = receipt or _receipt()
    request = _fixture_worker_request(
        worker_kind="manifest",
        materialization_manifest_sha256=None,
        runner_start_record_sha256=None,
        receipt=selected,
        code_commit_sha=selected.code_commit_sha,
        runner_source_sha256=selected.runner_source_sha256,
        source_manifest_sha256=selected.source_manifest_sha256,
        authorization_nonce_sha256=selected.authorization_nonce_sha256,
    )
    request_sha256 = module._worker_request_sha256(request)
    lifecycle = _complete_worker_lifecycle(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=request_sha256,
        payload_rows=[module._manifest_worker_payload(manifest)],
    )
    transcript = _worker_frames_bytes(_valid_manifest_worker_frames(request, manifest))
    provenance = module._build_worker_execution_provenance(
        worker_kind="manifest",
        request=request,
        supervisor_launched_child_process_id=1,
        transcript=transcript,
        lifecycle=lifecycle,
        accepted_payload_rows=[module._manifest_worker_payload(manifest)],
        failure_stage=None,
        child_exit_code=0,
        timed_out=False,
        output_overflow=False,
        communication_failed=False,
        request_fully_written=True,
    )
    return (
        protocol,
        manifest["cases"],
        manifest["materialization_manifest_sha256"],
        lifecycle,
        provenance,
    )


def _case_worker_lifecycle(
    cases: Sequence[module.ReferenceValidationCaseObservation],
) -> dict[str, Any]:
    return _complete_worker_lifecycle(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=CASE_WORKER_REQUEST_SHA256,
        payload_rows=[row.to_dict() for row in cases],
    )


def _observation_lifecycle_fields(
    cases: Sequence[module.ReferenceValidationCaseObservation],
    *,
    runner_start_record_sha256: str = "1" * 64,
    execution_environment_receipt_sha256: str = "2" * 64,
    environment_fingerprint_sha256: str = "3" * 64,
    authorization_nonce_sha256: str = "5" * 64,
    code_commit_sha: str = "6" * 40,
    runner_source_sha256: str = "7" * 64,
    source_manifest_sha256: str = "8" * 64,
    seed: int = 123,
) -> dict[str, object]:
    _, manifest = module._load_frozen_case_manifest_document()
    receipt = _receipt(
        receipt_sha256=execution_environment_receipt_sha256,
        environment_fingerprint_sha256=environment_fingerprint_sha256,
        authorization_nonce_sha256=authorization_nonce_sha256,
        code_commit_sha=code_commit_sha,
        runner_source_sha256=runner_source_sha256,
        source_manifest_sha256=source_manifest_sha256,
        application_seed=seed,
        environment_variable_rows=_environment_rows(application_seed=seed),
    )
    manifest_request = _fixture_worker_request(
        worker_kind="manifest",
        materialization_manifest_sha256=None,
        runner_start_record_sha256=None,
        receipt=receipt,
        code_commit_sha=code_commit_sha,
        runner_source_sha256=runner_source_sha256,
        source_manifest_sha256=source_manifest_sha256,
        authorization_nonce_sha256=authorization_nonce_sha256,
    )
    manifest_request_sha256 = module._worker_request_sha256(manifest_request)
    manifest_payload = module._manifest_worker_payload(manifest)
    manifest_lifecycle = _complete_worker_lifecycle(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=manifest_request_sha256,
        payload_rows=[manifest_payload],
    )
    manifest_transcript = _worker_frames_bytes(
        _valid_manifest_worker_frames(manifest_request, manifest)
    )
    manifest_provenance = module._build_worker_execution_provenance(
        worker_kind="manifest",
        request=manifest_request,
        supervisor_launched_child_process_id=1,
        transcript=manifest_transcript,
        lifecycle=manifest_lifecycle,
        accepted_payload_rows=[manifest_payload],
        failure_stage=None,
        child_exit_code=0,
        timed_out=False,
        output_overflow=False,
        communication_failed=False,
        request_fully_written=True,
    )
    case_request = _fixture_worker_request(
        worker_kind="case",
        materialization_manifest_sha256=manifest["materialization_manifest_sha256"],
        runner_start_record_sha256=runner_start_record_sha256,
        receipt=receipt,
        code_commit_sha=code_commit_sha,
        runner_source_sha256=runner_source_sha256,
        source_manifest_sha256=source_manifest_sha256,
        authorization_nonce_sha256=authorization_nonce_sha256,
    )
    case_request_sha256 = module._worker_request_sha256(case_request)
    case_lifecycle = _complete_worker_lifecycle(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=case_request_sha256,
        payload_rows=[row.to_dict() for row in cases],
    )
    case_transcript = _worker_frames_bytes(
        _valid_case_worker_frames(case_request, cases)
    )
    case_provenance = module._build_worker_execution_provenance(
        worker_kind="case",
        request=case_request,
        supervisor_launched_child_process_id=1,
        transcript=case_transcript,
        lifecycle=case_lifecycle,
        accepted_payload_rows=[row.to_dict() for row in cases],
        failure_stage=None,
        child_exit_code=0,
        timed_out=False,
        output_overflow=False,
        communication_failed=False,
        request_fully_written=True,
    )
    payload_rows = [row.to_dict() for row in cases]
    return {
        "manifest_worker_lifecycle_evidence_bytes": module._lifecycle_evidence_bytes(
            manifest_lifecycle,
            name="manifest-worker lifecycle evidence",
        ),
        "case_worker_lifecycle_evidence_bytes": module._lifecycle_evidence_bytes(
            case_lifecycle,
            name="case-worker lifecycle evidence",
        ),
        "manifest_worker_execution_provenance_bytes": (
            module._worker_execution_provenance_bytes(
                manifest_provenance,
                name="manifest-worker execution provenance",
            )
        ),
        "case_worker_execution_provenance_bytes": (
            module._worker_execution_provenance_bytes(
                case_provenance,
                name="case-worker execution provenance",
            )
        ),
        "retained_case_payload_aggregate_sha256": module._sha256(payload_rows),
    }


def _worker_frames_bytes(frames: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(module._canonical_bytes(dict(frame)) + b"\n" for frame in frames)


def _valid_case_worker_frames(
    request: Mapping[str, Any],
    cases: Sequence[module.ReferenceValidationCaseObservation],
) -> list[dict[str, Any]]:
    worker_request_sha256 = module._worker_request_sha256(request)
    lifecycle = _complete_worker_lifecycle(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=worker_request_sha256,
        payload_rows=[row.to_dict() for row in cases],
    )
    return [
        module._worker_frame(
            frame_type="pre",
            worker_kind="case",
            worker_request_sha256=worker_request_sha256,
            payload=lifecycle["pre"],
        ),
        *[
            module._worker_frame(
                frame_type="payload",
                worker_kind="case",
                worker_request_sha256=worker_request_sha256,
                payload=row.to_dict(),
                ordinal=row.ordinal,
            )
            for row in cases
        ],
        module._worker_frame(
            frame_type="completion",
            worker_kind="case",
            worker_request_sha256=worker_request_sha256,
            payload=lifecycle,
        ),
    ]


def _valid_manifest_worker_frames(
    request: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> list[dict[str, Any]]:
    worker_request_sha256 = module._worker_request_sha256(request)
    payload = module._manifest_worker_payload(manifest)
    lifecycle = _complete_worker_lifecycle(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=worker_request_sha256,
        payload_rows=[payload],
    )
    return [
        module._worker_frame(
            frame_type="pre",
            worker_kind="manifest",
            worker_request_sha256=worker_request_sha256,
            payload=lifecycle["pre"],
        ),
        module._worker_frame(
            frame_type="payload",
            worker_kind="manifest",
            worker_request_sha256=worker_request_sha256,
            payload=payload,
            ordinal=0,
        ),
        module._worker_frame(
            frame_type="completion",
            worker_kind="manifest",
            worker_request_sha256=worker_request_sha256,
            payload=lifecycle,
        ),
    ]


@pytest.fixture(scope="module")
def frozen_worker_matrix() -> tuple[
    Any,
    dict[str, Any],
    tuple[module.ReferenceValidationCaseObservation, ...],
]:
    protocol, manifest = module._load_frozen_case_manifest_document()
    cases = module._run_case_matrix_in_process(
        protocol,
        manifest["cases"],
        deadline=time.monotonic() + 120.0,
    )
    return protocol, manifest, cases


def _call_supervised_case_worker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    protocol: Any,
    manifest: Mapping[str, Any],
    communicate: object,
) -> tuple[
    tuple[module.ReferenceValidationCaseObservation, ...],
    dict[str, Any],
    dict[str, Any],
]:
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    process = SimpleNamespace(pid=1, returncode=0)
    monkeypatch.setattr(
        module,
        "_start_fixed_validation_worker",
        lambda worker_flag, request: process,
    )
    monkeypatch.setattr(
        module,
        "_communicate_fixed_validation_worker",
        communicate,
    )
    return module._run_supervised_case_matrix(
        protocol,
        manifest["cases"],
        materialization_manifest_sha256=manifest["materialization_manifest_sha256"],
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_runner_source_sha256=reference_validation_runner_source_sha256(),
        expected_runner_start_record_sha256="1" * 64,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=receipt,
        worker_environment=worker_environment,
        deadline=time.monotonic() + 120.0,
    )


def _assert_supervisor_failure_complete(
    rows: Sequence[module.ReferenceValidationCaseObservation],
    lifecycle: Mapping[str, Any],
    *,
    expected_status: str,
    expected_error_code: str,
) -> None:
    variants = [variant for row in rows for variant in row.variant_results]
    assert len(rows) == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert len(variants) == REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    assert lifecycle["completion_state"] == "incomplete"
    assert lifecycle["failure_code"] == expected_error_code
    assert lifecycle["payload"] is None
    assert lifecycle["post"] is None
    assert all(row.observation_origin == "supervisor" for row in rows)
    assert all(not row.case_passed for row in rows)
    assert all(row.observed_status == expected_status for row in rows)
    assert all(row.observed_error_code == expected_error_code for row in rows)
    assert all(variant.observed_status == expected_status for variant in variants)
    assert all(
        variant.observed_error_code == expected_error_code for variant in variants
    )


def _install_verified_receipt(
    monkeypatch: pytest.MonkeyPatch,
    receipt: SimpleNamespace,
    *,
    now: datetime = NOW,
) -> None:
    monkeypatch.setattr(module, "_utc_now", lambda: now)
    monkeypatch.setattr(
        module,
        "require_reference_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: receipt,
    )
    monkeypatch.setattr(
        module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: receipt.code_commit_sha,
    )
    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        lambda _expected_commit: None,
    )
    monkeypatch.setattr(
        module,
        "_require_isolated_python_bootstrap_runtime",
        lambda **_kwargs: (Path("/trusted"),),
    )
    monkeypatch.setattr(module, "_require_source_only_python_runtime", lambda: None)
    monkeypatch.setattr(
        module,
        "_observe_dependency_artifact_sha256_rows",
        lambda _roots, **kwargs: dict(DEPENDENCY_ROWS),
    )

    def run_in_process(
        worker_protocol: object,
        worker_manifest_cases: object,
        **kwargs: object,
    ):
        rows = module._run_case_matrix_in_process(
            worker_protocol,
            worker_manifest_cases,
            deadline=kwargs["deadline"],
        )
        request = _fixture_worker_request(
            worker_kind="case",
            materialization_manifest_sha256=kwargs["materialization_manifest_sha256"],
            runner_start_record_sha256=kwargs["expected_runner_start_record_sha256"],
            receipt=receipt,
            code_commit_sha=receipt.code_commit_sha,
            runner_source_sha256=receipt.runner_source_sha256,
            source_manifest_sha256=receipt.source_manifest_sha256,
            authorization_nonce_sha256=receipt.authorization_nonce_sha256,
        )
        lifecycle = _complete_worker_lifecycle(
            lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
            worker_request_sha256=module._worker_request_sha256(request),
            payload_rows=[row.to_dict() for row in rows],
        )
        transcript = _worker_frames_bytes(_valid_case_worker_frames(request, rows))
        provenance = module._build_worker_execution_provenance(
            worker_kind="case",
            request=request,
            supervisor_launched_child_process_id=1,
            transcript=transcript,
            lifecycle=lifecycle,
            accepted_payload_rows=[row.to_dict() for row in rows],
            failure_stage=None,
            child_exit_code=0,
            timed_out=False,
            output_overflow=False,
            communication_failed=False,
            request_fully_written=True,
        )
        return rows, lifecycle, provenance

    monkeypatch.setattr(module, "_run_supervised_case_matrix", run_in_process)
    monkeypatch.setattr(
        module,
        "_run_supervised_frozen_case_matrix",
        lambda **_kwargs: _frozen_manifest_worker_result(receipt),
    )


def _run(root: Path):
    return run_bounded_cpu_reference_validation(
        root,
        AUTHORIZATION_NONCE,
        expected_environment_receipt_sha256=ENVIRONMENT_RECEIPT_SHA256,
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
    )


def test_runner_contract_is_frozen_and_current_decision_remains_closed() -> None:
    first = reference_validation_runner_contract_document()
    second = reference_validation_runner_contract_document()
    decision = reference_validation_runner_contract_decision()

    assert first == second
    assert first["schema_id"] == REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256
    )
    assert first["bounds"]["case_count"] == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert first["bounds"]["variant_count"] == (
        REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    )
    assert first["frozen_at_utc"] == "2026-07-19T00:00:00Z"
    assert first["bounds"]["worker_canonical_jsonl_frame_protocol_required"] is True
    assert (
        first["bounds"]["retained_worker_environment_internal_coherence_reverified"]
        is True
    )
    assert first["bounds"]["source_checkout_root_owned_read_only_required"] is True
    assert first["bounds"]["manifest_worker_frame_order"] == [
        "pre",
        "payload",
        "completion",
    ]
    assert first["bounds"]["case_worker_frame_order"] == [
        "pre",
        "payload_x27",
        "completion",
    ]
    assert (
        first["bounds"]["partial_worker_success_retained_after_lifecycle_failure"]
        is False
    )
    assert (
        first["bounds"]["native_runtime_allowlist_authorization_established"] is False
    )
    assert first["bounds"]["production_native_lifetime_closure_claimed"] is False
    assert module.FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V2 == (
        "96b133144344183191db89c86838a6d712a26f0dbfc5eee4981d34e2fe074754"
    )
    assert module.FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V3 == (
        "c450059857a38f7cf8aa44ba1efbb79ff3d6218ebc7deaf963078c2e3f44a1e9"
    )
    assert first["observation"]["in_memory_only"] is True
    assert first["observation"]["failed_metrics_and_cases_retained"] is True
    assert first["claim_policy"]["claim_safe"] is False
    assert require_reference_validation_runner_contract_document(first) == first

    assert decision["bounded_validation_runner_implemented"] is True
    assert decision["production_runner_start_consumed"] is False
    assert decision["production_validation_execution_authorized"] is False
    assert decision["production_validation_results_collected"] is False
    assert decision["result_receipt_writer_implemented"] is True


def test_runner_contract_rejects_tamper_and_source_identity_is_exact() -> None:
    tampered = copy(reference_validation_runner_contract_document())
    tampered["claim_policy"] = dict(tampered["claim_policy"])
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="does not match the frozen record",
    ):
        require_reference_validation_runner_contract_document(tampered)

    runner_source = Path(inspect.getsourcefile(module) or "")
    bootstrap_source = Path(module.reference_validation_bootstrap_path())
    assert runner_source.is_file()
    assert bootstrap_source.is_file()
    expected_source_identity = {
        "schema_id": (
            "betelgeuze.engine_v2_reference_validation_execution_sources/4.0.0"
        ),
        "sources": [
            {
                "path": (
                    "betelgeuze_engine_v2/physics/reference_validation_bootstrap.py"
                ),
                "sha256": hashlib.sha256(bootstrap_source.read_bytes()).hexdigest(),
            },
            {
                "path": (
                    "betelgeuze_engine_v2/physics/reference_validation_dependency_identity.py"
                ),
                "sha256": hashlib.sha256(
                    Path(dependency_identity.__file__).read_bytes()
                ).hexdigest(),
            },
            {
                "path": ("betelgeuze_engine_v2/physics/validation_source_identity.py"),
                "sha256": hashlib.sha256(
                    Path(source_identity.__file__).read_bytes()
                ).hexdigest(),
            },
            {
                "path": (
                    "betelgeuze_engine_v2/physics/validation_native_runtime_identity.py"
                ),
                "sha256": hashlib.sha256(
                    Path(native_identity.__file__).read_bytes()
                ).hexdigest(),
            },
            {
                "path": ("betelgeuze_engine_v2/physics/reference_validation_runner.py"),
                "sha256": hashlib.sha256(runner_source.read_bytes()).hexdigest(),
            },
        ],
    }
    assert (
        reference_validation_runner_source_sha256()
        == hashlib.sha256(module._canonical_bytes(expected_source_identity)).hexdigest()
    )
    assert (
        reference_validation_checked_out_code_commit_sha()
        == subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
        ).strip()
    )


def test_stdlib_bootstrap_and_dependency_identity_helper_are_exactly_scoped() -> None:
    bootstrap_tree = ast.parse(
        Path(bootstrap_module.__file__).read_text(encoding="utf-8")
    )
    bootstrap_imports: set[str] = set()
    for node in ast.walk(bootstrap_tree):
        if isinstance(node, ast.Import):
            bootstrap_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            bootstrap_imports.add(node.module or "")
    assert bootstrap_imports == {
        "__future__",
        "betelgeuze_engine_v2.physics",
        "hashlib",
        "hmac",
        "importlib.util",
        "json",
        "os",
        "select",
        "stat",
        "subprocess",
        "sys",
        "sysconfig",
        "time",
    }

    dependency_tree = ast.parse(
        Path(dependency_identity.__file__).read_text(encoding="utf-8")
    )
    dependency_imports: set[str] = set()
    for node in ast.walk(dependency_tree):
        if isinstance(node, ast.Import):
            dependency_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            dependency_imports.add(node.module or "")
    assert dependency_imports == {
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
        dependency_identity.REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
        == (
            "cryptography-distribution",
            "numpy-distribution",
            "openssl-executable",
            "python-runtime-executable",
            "python-standard-library",
            "torch-distribution",
        )
    )


@pytest.mark.parametrize(
    ("identity_module", "error_type"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        ),
    ),
)
def test_dependency_identity_binds_active_import_to_measured_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_module: object,
    error_type: type[Exception],
) -> None:
    measured_package = tmp_path / "measured" / "numpy"
    active_package = tmp_path / "active" / "numpy"
    measured_package.mkdir(parents=True)
    active_package.mkdir(parents=True)
    measured_origin = measured_package / "__init__.py"
    active_origin = active_package / "__init__.py"
    measured_origin.write_text("MEASURED = True\n", encoding="ascii")
    active_origin.write_text("ACTIVE = True\n", encoding="ascii")
    record_paths = {measured_origin.resolve(): "numpy/__init__.py"}

    monkeypatch.setattr(
        identity_module.util,
        "find_spec",
        lambda name: SimpleNamespace(
            origin=os.fspath(measured_origin),
            submodule_search_locations=[os.fspath(measured_package)],
        ),
    )
    assert identity_module._distribution_import_binding(
        "numpy",
        "numpy",
        record_paths=record_paths,
    ) == {
        "import_package": "numpy",
        "import_origin_record_path": "numpy/__init__.py",
    }

    monkeypatch.setattr(
        identity_module.util,
        "find_spec",
        lambda name: SimpleNamespace(
            origin=os.fspath(active_origin),
            submodule_search_locations=[os.fspath(active_package)],
        ),
    )
    with pytest.raises(error_type, match="outside its measured RECORD"):
        identity_module._distribution_import_binding(
            "numpy",
            "numpy",
            record_paths=record_paths,
        )


@pytest.mark.parametrize(
    ("identity_module", "error_type"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        ),
    ),
)
def test_dependency_identity_has_one_explicit_monotonic_preflight_deadline(
    identity_module: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type, match="preflight deadline expired"):
        identity_module._ScanBudget(time.monotonic() - 1.0)


@pytest.mark.parametrize(
    ("identity_module", "error_type", "entry_bound_name"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
            "REFERENCE_VALIDATION_DEPENDENCY_MAX_ENTRIES",
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
            "REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_MAX_ENTRIES",
        ),
    ),
)
def test_dependency_tree_entry_bound_precedes_tree_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_module: object,
    error_type: type[Exception],
    entry_bound_name: str,
) -> None:
    (tmp_path / "first").write_bytes(b"1")
    (tmp_path / "second").write_bytes(b"2")
    monkeypatch.setattr(identity_module, entry_bound_name, 1)

    with pytest.raises(error_type, match="entry bound"):
        list(
            identity_module._bounded_tree_entries(
                tmp_path,
                budget=identity_module._ScanBudget(time.monotonic() + 10.0),
            )
        )


@pytest.mark.parametrize(
    ("identity_module", "error_type"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        ),
    ),
)
def test_dependency_file_cap_is_checked_before_payload_read(
    identity_module: object,
    error_type: type[Exception],
) -> None:
    executable = Path("/usr/bin/openssl").resolve(strict=True)

    with pytest.raises(error_type, match="pre-read artifact byte bound"):
        identity_module._hash_regular_file(
            executable,
            allowed_roots=(executable.parent,),
            budget=identity_module._ScanBudget(time.monotonic() + 10.0),
            maximum_bytes=0,
        )


@pytest.mark.parametrize(
    ("identity_module", "error_type", "line_bound_name"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
            "REFERENCE_VALIDATION_DEPENDENCY_RECORD_MAX_LINE_BYTES",
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
            "REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_RECORD_MAX_LINE_BYTES",
        ),
    ),
)
def test_distribution_record_is_streamed_under_a_preallocated_line_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_module: object,
    error_type: type[Exception],
    line_bound_name: str,
) -> None:
    site_root = (tmp_path / "site-packages").resolve()
    metadata_root = site_root / "example-1.0.dist-info"
    metadata_root.mkdir(parents=True)
    record_path = metadata_root / "RECORD"
    record_path.write_bytes(b"payload.py,sha256=AAAA,1\n")
    record_path.chmod(0o444)

    class Distribution:
        _path = metadata_root

    real_fstat = os.fstat

    def root_owned_fstat(descriptor: int) -> os.stat_result:
        fields = list(real_fstat(descriptor))
        fields[stat.ST_UID] = 0
        return os.stat_result(fields)

    monkeypatch.setattr(
        identity_module,
        "_require_root_owned_read_only_directory_chain",
        lambda path: path,
    )
    monkeypatch.setattr(identity_module.os, "fstat", root_owned_fstat)
    monkeypatch.setattr(identity_module, line_bound_name, 4)

    with pytest.raises(error_type, match="line exceeds its bound"):
        identity_module._read_distribution_record_rows(
            "example",
            Distribution(),
            site_root,
            allowed_roots=(site_root,),
            budget=identity_module._ScanBudget(time.monotonic() + 10.0),
        )

    monkeypatch.setattr(identity_module, line_bound_name, 8_192)
    rows, record_relative = identity_module._read_distribution_record_rows(
        "example",
        Distribution(),
        site_root,
        allowed_roots=(site_root,),
        budget=identity_module._ScanBudget(time.monotonic() + 10.0),
    )
    assert rows == [("payload.py", "AAAA", 1)]
    assert record_relative == "example-1.0.dist-info/RECORD"


@pytest.mark.parametrize(
    ("identity_module", "error_type"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        ),
    ),
)
@pytest.mark.parametrize("injected_name", ("injected.py", "orphan.pyc"))
def test_dependency_identity_rejects_unrecorded_package_namespace_payload(
    tmp_path: Path,
    identity_module: object,
    error_type: type[Exception],
    injected_name: str,
) -> None:
    package_root = tmp_path / "numpy"
    package_root.mkdir()
    origin = package_root / "__init__.py"
    origin.write_text("VALUE = 1\n", encoding="ascii")
    (package_root / injected_name).write_bytes(b"unrecorded")
    budget = identity_module._ScanBudget(time.monotonic() + 10.0)

    with pytest.raises(error_type, match="unrecorded importable payload"):
        identity_module._require_closed_distribution_namespace(
            "numpy",
            package_root,
            record_paths={origin.resolve(): "numpy/__init__.py"},
            budget=budget,
        )


@pytest.mark.parametrize(
    ("identity_module", "error_type"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        ),
    ),
)
def test_dependency_identity_rejects_stdlib_bytecode_cache_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_module: object,
    error_type: type[Exception],
) -> None:
    cache_root = tmp_path / "__pycache__"
    cache_root.mkdir()
    (cache_root / "injected.pyc").write_bytes(b"bytecode")
    monkeypatch.setattr(
        identity_module.sysconfig,
        "get_paths",
        lambda: {"stdlib": os.fspath(tmp_path)},
    )

    with pytest.raises(error_type, match="bytecode cache payload"):
        identity_module._standard_library_identity(
            allowed_roots=(tmp_path.resolve(),),
            budget=identity_module._ScanBudget(time.monotonic() + 10.0),
        )


@pytest.mark.parametrize(
    "identity_module",
    (dependency_identity, minimization_dependency_identity),
)
def test_dependency_identity_closes_every_record_owned_top_level_namespace(
    tmp_path: Path,
    identity_module: object,
) -> None:
    site_root = tmp_path / "site-packages"
    script_root = tmp_path / "bin"
    namespace_names = ("functorch", "torch", "torchgen", "torch.libs")
    record_paths: dict[Path, str] = {}
    for namespace_name in namespace_names:
        namespace_root = site_root / namespace_name
        namespace_root.mkdir(parents=True)
        payload = namespace_root / "payload.py"
        payload.write_bytes(b"payload")
        record_paths[payload.resolve()] = f"{namespace_name}/payload.py"
    script_root.mkdir()
    script = script_root / "torchrun"
    script.write_bytes(b"script")
    record_paths[script.resolve()] = "../../../bin/torchrun"
    active_origin = site_root / "torch" / "payload.py"

    assert identity_module._record_owned_namespace_roots(
        "torch",
        site_root.resolve(),
        record_paths=record_paths,
        active_origin=active_origin.resolve(),
    ) == tuple(site_root / namespace_name for namespace_name in sorted(namespace_names))


@pytest.mark.parametrize(
    ("identity_module", "error_type"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
        ),
    ),
)
def test_dependency_identity_normalizes_console_scripts_to_install_scheme(
    tmp_path: Path,
    identity_module: object,
    error_type: type[Exception],
) -> None:
    prefix = tmp_path / "runtime"
    site_root = prefix / "lib" / "python3" / "site-packages"
    script_root = prefix / "bin"
    site_root.mkdir(parents=True)
    script_root.mkdir()
    script = script_root / "f2py"
    script.write_bytes(b"script")
    install_roots = (
        ("purelib", site_root.resolve()),
        ("scripts", script_root.resolve()),
        ("data", prefix.resolve()),
    )

    assert (
        identity_module._normalized_record_payload_path(
            "numpy",
            "../../../bin/f2py",
            script.resolve(),
            distribution_root=site_root.resolve(),
            install_scheme_roots=install_roots,
        )
        == "scripts:f2py"
    )

    with pytest.raises(error_type, match="escaped its install scheme"):
        identity_module._normalized_record_payload_path(
            "numpy",
            "../../../../outside",
            (tmp_path / "outside").resolve(),
            distribution_root=site_root.resolve(),
            install_scheme_roots=install_roots,
        )


@pytest.mark.parametrize(
    ("identity_module", "error_type", "required_ids"),
    (
        (
            dependency_identity,
            dependency_identity.ReferenceValidationDependencyIdentityError,
            dependency_identity.REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
        ),
        (
            minimization_dependency_identity,
            minimization_dependency_identity.ReferenceMinimizationValidationDependencyIdentityError,
            minimization_dependency_identity.REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
        ),
    ),
)
def test_dependency_per_file_manifest_is_canonical_complete_and_tamper_evident(
    identity_module: object,
    error_type: type[Exception],
    required_ids: tuple[str, ...],
) -> None:
    artifacts = [
        identity_module._artifact_observation(
            artifact_id,
            {
                "files": [
                    {
                        "path": f"payload-{ordinal}",
                        "sha256": f"{ordinal + 1:064x}",
                        "size": ordinal + 1,
                    }
                ]
            },
        )
        for ordinal, artifact_id in enumerate(required_ids)
    ]
    document = identity_module._dependency_manifest_document(artifacts)
    projection = dict(document)
    manifest_sha256 = projection.pop("manifest_sha256")

    assert document["file_count"] == len(required_ids)
    assert document["total_bytes"] == sum(range(1, len(required_ids) + 1))
    assert (
        manifest_sha256
        == hashlib.sha256(identity_module._canonical_bytes(projection)).hexdigest()
    )
    assert [row["artifact_id"] for row in document["artifacts"]] == list(required_ids)

    with pytest.raises(error_type, match="artifact order drifted"):
        identity_module._dependency_manifest_document(list(reversed(artifacts)))

    tampered = deepcopy(artifacts)
    tampered[0]["identity"]["files"][0]["size"] = 999
    with pytest.raises(error_type, match="artifact digest is invalid"):
        identity_module._dependency_manifest_document(tampered)

    malformed_row = deepcopy(artifacts)
    malformed_row[0]["identity"]["files"][0]["unexpected"] = True
    malformed_row[0]["sha256"] = hashlib.sha256(
        identity_module._canonical_bytes(malformed_row[0]["identity"])
    ).hexdigest()
    with pytest.raises(error_type, match="file row is invalid"):
        identity_module._dependency_manifest_document(malformed_row)


@pytest.mark.parametrize(
    ("bootstrap", "error_type"),
    (
        (
            bootstrap_module,
            bootstrap_module._ReferenceValidationBootstrapError,
        ),
        (
            minimization_bootstrap_module,
            minimization_bootstrap_module._ReferenceMinimizationValidationBootstrapError,
        ),
    ),
)
def test_bootstrap_rejects_mutable_source_tree_before_package_import(
    tmp_path: Path,
    bootstrap: object,
    error_type: type[Exception],
) -> None:
    (tmp_path / "betelgeuze_engine_v2").mkdir()
    (tmp_path / "betelgeuze_engine_v2" / "__init__.py").write_text(
        "VALUE = 1\n",
        encoding="ascii",
    )
    with pytest.raises(error_type):
        bootstrap._require_immutable_source_snapshot(
            os.fspath(tmp_path),
            deadline=time.monotonic() + 10.0,
        )


@pytest.mark.parametrize(
    ("bootstrap", "error_type"),
    (
        (
            bootstrap_module,
            bootstrap_module._ReferenceValidationBootstrapError,
        ),
        (
            minimization_bootstrap_module,
            minimization_bootstrap_module._ReferenceMinimizationValidationBootstrapError,
        ),
    ),
)
def test_bootstrap_rejects_root_execution_before_source_scan(
    monkeypatch: pytest.MonkeyPatch,
    bootstrap: object,
    error_type: type[Exception],
) -> None:
    monkeypatch.setattr(bootstrap.os, "geteuid", lambda: 0)

    with pytest.raises(error_type, match="non-root uid"):
        bootstrap._require_immutable_source_snapshot(
            "/unreadable",
            deadline=time.monotonic() + 10.0,
        )


@pytest.mark.parametrize(
    ("bootstrap", "error_type", "entry_bound_name"),
    (
        (
            bootstrap_module,
            bootstrap_module._ReferenceValidationBootstrapError,
            "REFERENCE_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_ENTRIES",
        ),
        (
            minimization_bootstrap_module,
            minimization_bootstrap_module._ReferenceMinimizationValidationBootstrapError,
            "REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_SOURCE_TREE_MAX_ENTRIES",
        ),
    ),
)
def test_bootstrap_source_entry_bound_precedes_directory_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bootstrap: object,
    error_type: type[Exception],
    entry_bound_name: str,
) -> None:
    package_root = tmp_path / "betelgeuze_engine_v2"
    package_root.mkdir()
    (package_root / "first.py").write_bytes(b"1")
    (package_root / "second.py").write_bytes(b"2")
    monkeypatch.setattr(bootstrap.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(
        bootstrap,
        "_require_root_owned_read_only_directory",
        lambda path: os.path.realpath(path),
    )
    monkeypatch.setattr(bootstrap, entry_bound_name, 1)

    with pytest.raises(error_type, match="entry bound"):
        bootstrap._require_immutable_source_snapshot(
            os.fspath(tmp_path),
            deadline=time.monotonic() + 10.0,
        )


@pytest.mark.parametrize(
    ("bootstrap", "error_type", "source_cap_name"),
    (
        (
            bootstrap_module,
            bootstrap_module._ReferenceValidationBootstrapError,
            "REFERENCE_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_BYTES",
        ),
        (
            minimization_bootstrap_module,
            minimization_bootstrap_module._ReferenceMinimizationValidationBootstrapError,
            "REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_EXECUTION_SOURCE_MAX_BYTES",
        ),
    ),
)
def test_bootstrap_execution_source_cap_is_checked_before_read(
    monkeypatch: pytest.MonkeyPatch,
    bootstrap: object,
    error_type: type[Exception],
    source_cap_name: str,
) -> None:
    monkeypatch.setattr(bootstrap, source_cap_name, 0)

    with pytest.raises(error_type, match="pre-read file policy"):
        bootstrap._bounded_execution_source_sha256(
            bootstrap.__file__,
            deadline=time.monotonic() + 10.0,
        )


@pytest.mark.parametrize(
    ("bootstrap", "error_type", "maximum"),
    (
        (
            bootstrap_module,
            bootstrap_module._ReferenceValidationBootstrapError,
            bootstrap_module.REFERENCE_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS,
        ),
        (
            minimization_bootstrap_module,
            minimization_bootstrap_module._ReferenceMinimizationValidationBootstrapError,
            minimization_bootstrap_module.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_PREFLIGHT_MAX_WALL_SECONDS,
        ),
    ),
)
def test_bootstrap_rejects_caller_extended_inner_preflight_deadline(
    bootstrap: object,
    error_type: type[Exception],
    maximum: float,
) -> None:
    with pytest.raises(error_type, match="exceeds its frozen bound"):
        bootstrap._require_canonical_preflight_deadline(
            (time.monotonic() + maximum + 60.0).hex()
        )
    with pytest.raises(error_type, match="not canonical"):
        bootstrap._require_canonical_preflight_deadline("nan")


@pytest.mark.parametrize(
    ("bootstrap", "error_type", "deadline_environment"),
    (
        (
            bootstrap_module,
            bootstrap_module._ReferenceValidationBootstrapError,
            bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        ),
        (
            minimization_bootstrap_module,
            minimization_bootstrap_module._ReferenceMinimizationValidationBootstrapError,
            minimization_bootstrap_module.REFERENCE_MINIMIZATION_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        ),
    ),
)
def test_bootstrap_stdin_wait_is_bounded_by_carried_preflight_deadline(
    monkeypatch: pytest.MonkeyPatch,
    bootstrap: object,
    error_type: type[Exception],
    deadline_environment: str,
) -> None:
    read_descriptor, write_descriptor = os.pipe()
    try:
        with os.fdopen(read_descriptor, "rb", buffering=0) as reader:
            monkeypatch.setattr(bootstrap.sys, "stdin", reader)
            monkeypatch.setenv(
                deadline_environment,
                (time.monotonic() + 0.1).hex(),
            )
            with pytest.raises(error_type, match="preflight deadline expired"):
                bootstrap._read_bootstrap_request()
    finally:
        os.close(write_descriptor)


def test_clean_checkout_preflight_uses_only_the_root_owned_absolute_git(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = reference_validation_checked_out_code_commit_sha()
    seen: dict[str, object] = {}

    def clean_run(command: object, **kwargs: object) -> SimpleNamespace:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout=b"")

    monkeypatch.setattr(subprocess, "run", clean_run)
    module._require_clean_checked_out_code_commit(commit)
    command = seen["command"]
    kwargs = seen["kwargs"]
    assert isinstance(command, list)
    assert command[0] == "/usr/bin/git"
    assert command[-3:] == ["status", "--porcelain=v1", "--untracked-files=all"]
    assert isinstance(kwargs, dict)
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["timeout"] == 10
    assert kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=b" M betelgeuze_engine_v2/physics/reference_forcefield.py\n",
        ),
    )
    with pytest.raises(ReferenceValidationRunnerError, match="not exactly clean"):
        module._require_clean_checked_out_code_commit(commit)


def test_persisted_observation_rejects_forged_variant_metric_and_pass_flag() -> None:
    protocol, manifest_cases = module._load_frozen_case_matrix()
    cases = module._run_case_matrix_in_process(
        protocol,
        manifest_cases,
        deadline=time.monotonic() + 120.0,
    )
    observation = module.ReferenceValidationRunObservation(
        runner_start_record_sha256="1" * 64,
        execution_environment_receipt_sha256="2" * 64,
        environment_fingerprint_sha256="3" * 64,
        authorization_receipt_sha256="4" * 64,
        authorization_nonce_sha256="5" * 64,
        code_commit_sha="6" * 40,
        runner_source_sha256="7" * 64,
        source_manifest_sha256="8" * 64,
        dependency_artifact_sha256_rows=tuple(sorted(DEPENDENCY_ROWS.items())),
        command_argv=module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
        seed=123,
        started_at_utc="2026-07-17T09:00:00Z",
        completed_at_utc="2026-07-17T09:01:00Z",
        case_results=cases,
        **_observation_lifecycle_fields(cases),
    )

    def resign(payload: dict[str, object]) -> dict[str, object]:
        projection = dict(payload)
        projection.pop("observation_sha256", None)
        payload["observation_sha256"] = module._sha256(projection)
        return payload

    forged_variant = deepcopy(observation.to_dict())
    forged_variant["case_results"][0]["variant_results"][0]["variant_id"] = (
        "forged-variant"
    )
    resign(forged_variant)
    with pytest.raises(ReferenceValidationRunnerError, match="frozen matrix"):
        module.require_reference_validation_run_observation_document(forged_variant)

    forged_metric = deepcopy(observation.to_dict())
    forged_metric["case_results"][0]["metric_values"][0]["metric_id"] = "forged_metric"
    resign(forged_metric)
    with pytest.raises(ReferenceValidationRunnerError, match="frozen matrix"):
        module.require_reference_validation_run_observation_document(forged_metric)

    contradictory_pass = deepcopy(observation.to_dict())
    metric = contradictory_pass["case_results"][0]["metric_values"][0]
    metric["passed"] = not metric["passed"]
    resign(contradictory_pass)
    with pytest.raises(ReferenceValidationRunnerError, match="contradicts"):
        module.require_reference_validation_run_observation_document(contradictory_pass)

    forged_continuous_type = deepcopy(observation.to_dict())
    metric = forged_continuous_type["case_results"][0]["metric_values"][0]
    metric["value"] = False
    metric["passed"] = True
    resign(forged_continuous_type)
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="continuous metric observation must be binary64",
    ):
        module.require_reference_validation_run_observation_document(
            forged_continuous_type
        )

    forged_metric_value = deepcopy(observation.to_dict())
    metric = forged_metric_value["case_results"][0]["metric_values"][0]
    metric["value"] = 5.0e-11
    metric["passed"] = True
    resign(forged_metric_value)
    with pytest.raises(ReferenceValidationRunnerError, match="frozen matrix"):
        module.require_reference_validation_run_observation_document(
            forged_metric_value
        )

    forged_variant_status = deepcopy(observation.to_dict())
    variant = forged_variant_status["case_results"][0]["variant_results"][0]
    variant["observed_status"] = "unexpected_error"
    variant["observed_error_code"] = "forged_error"
    for key in tuple(variant):
        if key not in {
            "ordinal",
            "variant_id",
            "runtime_input_sha256",
            "oracle_input_sha256",
            "observed_status",
            "observed_error_code",
        }:
            del variant[key]
    resign(forged_variant_status)
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="case status or error contradicts",
    ):
        module.require_reference_validation_run_observation_document(
            forged_variant_status
        )


def test_git_replacement_refs_are_rejected_loose_or_packed(tmp_path: Path) -> None:
    git_dir = tmp_path / "git"
    common_dir = tmp_path / "common"
    git_dir.mkdir()
    common_dir.mkdir()
    module._require_no_git_replacement_refs(git_dir, common_dir)

    loose = common_dir / "refs" / "replace"
    loose.mkdir(parents=True)
    with pytest.raises(ReferenceValidationRunnerError, match="replacement refs"):
        module._require_no_git_replacement_refs(git_dir, common_dir)
    loose.rmdir()

    (common_dir / "packed-refs").write_text(
        f"{'a' * 40} refs/replace/{'b' * 40}\n",
        encoding="ascii",
    )
    with pytest.raises(ReferenceValidationRunnerError, match="replacement refs"):
        module._require_no_git_replacement_refs(git_dir, common_dir)


def test_bounded_runner_retains_exact_matrix_and_consumes_start_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())

    observation = _run(root)
    protocol = frozen_cpu_reference_validation_protocol()
    payload = observation.to_dict()

    assert [row.case_id for row in observation.case_results] == [
        row.case_id for row in protocol.cases
    ]
    assert len(observation.case_results) == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert sum(len(row.variant_results) for row in observation.case_results) == (
        REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    )
    fail_closed = [
        row for row in observation.case_results if row.expected_outcome == "fail_closed"
    ]
    assert len(fail_closed) == 12
    assert all(row.observed_status == "fail_closed_as_expected" for row in fail_closed)
    assert all(
        row.metric_values
        for row in observation.case_results
        if row.expected_outcome == "pass"
    )
    assert any(
        not metric.passed
        for row in observation.case_results
        for metric in row.metric_values
    )
    assert all(
        not variant.component_energies_kcal_per_mol
        and variant.total_energy_kcal_per_mol is None
        and not variant.forces_kcal_per_mol_angstrom
        for row in fail_closed
        for variant in row.variant_results
    )
    assert payload["coverage_summary"] == {
        "case_count": 27,
        "variant_count": 59,
        "case_pass_count": sum(row.case_passed for row in observation.case_results),
        "case_failure_count": sum(
            not row.case_passed for row in observation.case_results
        ),
        "all_cases_retained": True,
        "all_variants_retained": True,
        "skipped_cases": 0,
    }
    assert payload["production_validation_results_collected"] is False
    assert payload["result_receipt_written"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert payload["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256

    paths = list(root.iterdir())
    assert [path.name for path in paths] == [f"{AUTHORIZATION_NONCE}.runner-start.json"]
    assert paths[0].stat().st_nlink == 1
    assert paths[0].stat().st_mode & 0o777 == 0o600
    start = json.loads(paths[0].read_text(encoding="ascii"))
    assert start["schema_id"] == REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID
    assert start["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256
    assert start["result_values_present"] is False
    assert start["result_receipt_written"] is False
    assert (
        module.read_reference_validation_runner_start_record(
            root,
            AUTHORIZATION_NONCE,
            expected_record_sha256=observation.runner_start_record_sha256,
            expected_environment_receipt_sha256=ENVIRONMENT_RECEIPT_SHA256,
            expected_runner_source_sha256=observation.runner_source_sha256,
            expected_source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        )["source_manifest_sha256"]
        == SOURCE_MANIFEST_SHA256
    )
    with pytest.raises(ReferenceValidationRunnerError, match="bounded runner contract"):
        module.read_reference_validation_runner_start_record(
            root,
            AUTHORIZATION_NONCE,
            expected_record_sha256=observation.runner_start_record_sha256,
            expected_environment_receipt_sha256=ENVIRONMENT_RECEIPT_SHA256,
            expected_runner_source_sha256=observation.runner_source_sha256,
            expected_source_manifest_sha256="c" * 64,
        )

    with pytest.raises(
        ReferenceValidationRunnerAlreadyStartedError,
        match="already started",
    ):
        _run(root)


@pytest.mark.parametrize(
    ("receipt_overrides", "now", "message"),
    [
        ({"started_at_utc": "2026-07-17T08:54:59Z"}, NOW, "not fresh"),
        ({"code_commit_sha": "8" * 40}, NOW, "code commit"),
        ({"runner_source_sha256": "9" * 64}, NOW, "runner source"),
        (
            {"dependency_artifact_sha256_rows": (("other-wheel", "a" * 64),)},
            NOW,
            "dependency artifact rows",
        ),
    ],
)
def test_runner_preflight_rejects_stale_or_crosswired_receipt_before_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    receipt_overrides: dict[str, object],
    now: datetime,
    message: str,
) -> None:
    root = _private_root(tmp_path)
    _install_verified_receipt(
        monkeypatch,
        _receipt(**receipt_overrides),
        now=now,
    )

    with pytest.raises(ReferenceValidationRunnerError, match=message):
        _run(root)
    assert list(root.iterdir()) == []


def test_runner_rejects_checkout_or_frozen_evaluator_source_drift_before_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from betelgeuze_engine_v2.physics import reference_validation_artifact_binding

    checkout_root = _private_root(tmp_path, "checkout")
    _install_verified_receipt(monkeypatch, _receipt())
    monkeypatch.setattr(
        module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: "0" * 40,
    )
    with pytest.raises(ReferenceValidationRunnerError, match="checked-out code commit"):
        _run(checkout_root)
    assert list(checkout_root.iterdir()) == []

    dirty_root = _private_root(tmp_path, "dirty")
    monkeypatch.setattr(
        module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: CODE_COMMIT_SHA,
    )

    def reject_dirty_checkout(_expected_commit: str) -> None:
        raise ReferenceValidationRunnerError(
            "validation checkout is not exactly clean at the authorized commit"
        )

    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        reject_dirty_checkout,
    )
    with pytest.raises(ReferenceValidationRunnerError, match="not exactly clean"):
        _run(dirty_root)
    assert list(dirty_root.iterdir()) == []

    evaluator_root = _private_root(tmp_path, "evaluator")
    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        lambda _expected_commit: None,
    )
    monkeypatch.setattr(
        reference_validation_artifact_binding,
        "reference_forcefield_source_sha256",
        lambda: "0" * 64,
    )
    with pytest.raises(ReferenceValidationRunnerError, match="artifact source drifted"):
        _run(evaluator_root)
    assert list(evaluator_root.iterdir()) == []


def test_unexpected_evaluator_failures_are_sanitized_and_fully_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from betelgeuze_engine_v2.physics import reference_forcefield

    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())

    def _unexpected(*args: object, **kwargs: object):
        raise ValueError("sensitive-internal-diagnostic-must-not-escape")

    monkeypatch.setattr(
        reference_forcefield,
        "evaluate_reference_force_field",
        _unexpected,
    )
    observation = _run(root)
    variants = [
        variant for case in observation.case_results for variant in case.variant_results
    ]

    assert len(variants) == REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    assert all(variant.observed_status == "unexpected_error" for variant in variants)
    assert all(
        variant.observed_error_code == "unexpected_reference_evaluator_error"
        for variant in variants
    )
    assert "sensitive-internal-diagnostic" not in json.dumps(observation.to_dict())


def test_evaluator_is_interrupted_at_the_frozen_wall_clock_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from betelgeuze_engine_v2.physics import reference_forcefield

    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())
    manifest_worker_result = _frozen_manifest_worker_result()
    monkeypatch.setattr(
        module,
        "_run_supervised_frozen_case_matrix",
        lambda **_kwargs: manifest_worker_result,
    )
    monkeypatch.setattr(module, "REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS", 0.05)

    def _slow(*args: object, **kwargs: object):
        time.sleep(5.0)
        return None

    monkeypatch.setattr(reference_forcefield, "evaluate_reference_force_field", _slow)
    started = time.monotonic()
    observation = _run(root)
    elapsed = time.monotonic() - started

    variants = [
        variant for case in observation.case_results for variant in case.variant_results
    ]
    assert elapsed < 1.0
    assert len(variants) == REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    assert all(
        variant.observed_status == "time_budget_exhausted" for variant in variants
    )


def test_case_materialization_is_interrupted_and_all_variants_are_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from betelgeuze_engine_v2.physics import reference_validation_artifact_binding
    from betelgeuze_engine_v2.physics import reference_validation_materializer

    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())
    manifest_worker_result = _frozen_manifest_worker_result()
    monkeypatch.setattr(
        module,
        "_run_supervised_frozen_case_matrix",
        lambda **_kwargs: manifest_worker_result,
    )
    binding = reference_validation_artifact_binding.frozen_reference_validation_artifact_binding()
    manifest = reference_validation_materializer.reference_validation_materialization_manifest_document()
    monkeypatch.setattr(module, "REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS", 0.05)
    monkeypatch.setattr(
        reference_validation_artifact_binding,
        "frozen_reference_validation_artifact_binding",
        lambda: binding,
    )
    monkeypatch.setattr(
        reference_validation_materializer,
        "reference_validation_materialization_manifest_document",
        lambda: manifest,
    )

    def slow_materialization(*args: object, **kwargs: object):
        time.sleep(5.0)
        raise AssertionError("deadline did not interrupt materialization")

    monkeypatch.setattr(
        reference_validation_materializer,
        "materialize_frozen_reference_validation_case",
        slow_materialization,
    )
    started = time.monotonic()
    observation = _run(root)
    elapsed = time.monotonic() - started

    variants = [
        variant for case in observation.case_results for variant in case.variant_results
    ]
    assert elapsed < 1.0
    assert len(variants) == REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    assert all(
        variant.observed_status == "time_budget_exhausted" for variant in variants
    )


def test_expired_manifest_preflight_budget_does_not_consume_runner_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())
    monkeypatch.setattr(module, "REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS", -1.0)

    with pytest.raises(
        ReferenceValidationRunnerError,
        match="time budget expired before runner start",
    ):
        _run(root)

    assert list(root.iterdir()) == []


def test_supervisor_hard_kills_a_case_worker_at_the_wall_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol, manifest = module._load_frozen_case_manifest_document()
    manifest_cases = manifest["cases"]
    seen: dict[str, object] = {}

    class StalledProcess:
        args = [sys.executable, "--case-worker"]
        pid = 1
        returncode: int | None = None

        def __init__(self) -> None:
            self.communicate_calls = 0

        def communicate(self, **kwargs: object):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(self.args, kwargs["timeout"])
            self.returncode = -9
            return b"", None

        def kill(self) -> None:
            seen["killed"] = True

    stalled = StalledProcess()

    def popen(command: object, **kwargs: object) -> StalledProcess:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return stalled

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(
        module,
        "_communicate_fixed_validation_worker",
        lambda process, *_args, **_kwargs: (process.kill() or b"", True, False),
    )
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    rows, lifecycle, provenance = module._run_supervised_case_matrix(
        protocol,
        manifest_cases,
        materialization_manifest_sha256=manifest["materialization_manifest_sha256"],
        expected_code_commit_sha=reference_validation_checked_out_code_commit_sha(),
        expected_runner_source_sha256=reference_validation_runner_source_sha256(),
        expected_runner_start_record_sha256="1" * 64,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=receipt,
        worker_environment=worker_environment,
        deadline=time.monotonic() + 0.01,
    )

    assert seen["killed"] is True
    assert seen["command"][-1] == "--case-worker"
    assert seen["kwargs"]["stderr"] is subprocess.DEVNULL
    assert len(rows) == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert lifecycle["completion_state"] == "incomplete"
    assert lifecycle["failure_code"] == "runner_time_budget_exhausted"
    assert provenance["timed_out"] is True
    assert all(row.observation_origin == "supervisor" for row in rows)
    assert all(row.observed_status == "time_budget_exhausted" for row in rows)
    assert all(
        variant.observed_status == "time_budget_exhausted"
        for row in rows
        for variant in row.variant_results
    )


def test_supervisor_hard_kills_manifest_materialization_before_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class StalledProcess:
        args = [sys.executable, "--manifest-worker"]
        returncode: int | None = None

        def __init__(self) -> None:
            self.communicate_calls = 0

        def communicate(self, **kwargs: object):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(self.args, kwargs["timeout"])
            self.returncode = -9
            return b"", None

        def kill(self) -> None:
            seen["killed"] = True

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: StalledProcess())
    monkeypatch.setattr(
        module,
        "_communicate_fixed_validation_worker",
        lambda process, *_args, **_kwargs: (process.kill() or b"", True, False),
    )
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="materialization preflight did not complete",
    ):
        module._run_supervised_frozen_case_matrix(
            expected_code_commit_sha=reference_validation_checked_out_code_commit_sha(),
            expected_runner_source_sha256=reference_validation_runner_source_sha256(),
            expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
            dependency_roots=(Path("/trusted"),),
            environment_receipt=receipt,
            worker_environment=worker_environment,
            deadline=time.monotonic() + 0.01,
        )
    assert seen["killed"] is True


def test_worker_launch_uses_receipt_bound_environment_after_live_env_tamper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    request = module._fixed_worker_request(
        worker_kind="case",
        expected_materialization_manifest_sha256="f" * 64,
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_runner_source_sha256=reference_validation_runner_source_sha256(),
        expected_source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        expected_authorization_nonce_sha256=AUTHORIZATION_NONCE,
        expected_runner_start_record_sha256="1" * 64,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=receipt,
        worker_environment=worker_environment,
    )
    seen: dict[str, object] = {}
    sentinel = object()

    def popen(command: list[str], **kwargs: object) -> object:
        seen.update(command=command, kwargs=kwargs)
        return sentinel

    monkeypatch.setenv("PYTHONHASHSEED", "124")
    monkeypatch.setenv(module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV, "999")
    monkeypatch.setattr(subprocess, "Popen", popen)

    assert module._start_fixed_validation_worker("--case-worker", request) is sentinel
    assert seen["command"] == [
        os.path.realpath(sys.executable),
        "-S",
        "-B",
        "-X",
        "pycache_prefix=/dev/null",
        "-c",
        module._REFERENCE_VALIDATION_FIXED_WORKER_BOOTSTRAP,
        "--case-worker",
    ]
    kwargs = seen["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["env"] == worker_environment
    assert kwargs["env"]["PYTHONHASHSEED"] == "123"
    assert kwargs["env"][module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV] == "456"


def test_worker_request_enforces_uint32_python_hash_seed() -> None:
    receipt = _receipt(
        python_hash_seed=2**32 - 1,
        environment_variable_rows=_environment_rows(python_hash_seed=2**32 - 1),
    )
    environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    accepted = module._fixed_worker_request(
        worker_kind="manifest",
        expected_materialization_manifest_sha256=None,
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_runner_source_sha256=reference_validation_runner_source_sha256(),
        expected_source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        expected_authorization_nonce_sha256=AUTHORIZATION_NONCE,
        expected_runner_start_record_sha256=None,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=receipt,
        worker_environment=environment,
    )
    assert accepted["expected_python_hash_seed"] == 2**32 - 1

    rejected = dict(accepted)
    rejected["expected_python_hash_seed"] = 2**32
    rejected_environment = dict(environment)
    rejected_environment["PYTHONHASHSEED"] = str(2**32)
    rejected["expected_worker_environment"] = rejected_environment
    rejected["expected_worker_environment_sha256"] = module._sha256(
        rejected_environment
    )
    with pytest.raises(ReferenceValidationRunnerError, match="hash seed"):
        module._load_case_worker_request(module._canonical_bytes(rejected) + b"\n")


def test_worker_preflight_rechecks_dependencies_before_deterministic_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    repository_root = Path(module.__file__).resolve().parents[2]
    monkeypatch.chdir(repository_root)
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    request = module._fixed_worker_request(
        worker_kind="case",
        expected_materialization_manifest_sha256="f" * 64,
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_runner_source_sha256=reference_validation_runner_source_sha256(),
        expected_source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        expected_authorization_nonce_sha256=AUTHORIZATION_NONCE,
        expected_runner_start_record_sha256="1" * 64,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=receipt,
        worker_environment=worker_environment,
    )
    executable = os.path.realpath(sys.executable)
    expected_argv = (
        executable,
        "-S",
        "-B",
        "-X",
        "pycache_prefix=/dev/null",
        "-c",
        module._REFERENCE_VALIDATION_FIXED_WORKER_BOOTSTRAP,
        "--case-worker",
    )
    monkeypatch.setattr(module.os, "environ", dict(worker_environment))
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
            argv=["-c", "--case-worker"],
        ),
    )
    monkeypatch.setattr(module, "_read_worker_process_argv", lambda: expected_argv)
    monkeypatch.setattr(
        module,
        "_python_hash_probe_sha256",
        lambda: request["expected_python_hash_probe_sha256"],
    )
    monkeypatch.setattr(
        module,
        "_require_source_only_python_runtime",
        lambda: events.append("source-only"),
    )
    monkeypatch.setattr(
        module,
        "_require_trusted_dependency_roots",
        lambda roots: events.append("roots") or (Path("/trusted"),),
    )
    monkeypatch.setattr(
        module,
        "_observe_dependency_artifact_sha256_rows",
        lambda roots, **kwargs: events.append("dependencies") or dict(DEPENDENCY_ROWS),
    )
    monkeypatch.setattr(
        module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: events.append("commit") or CODE_COMMIT_SHA,
    )
    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        lambda commit: events.append("clean"),
    )
    monkeypatch.setattr(
        module,
        "reference_validation_runner_source_sha256",
        lambda: events.append("source") or request["expected_runner_source_sha256"],
    )
    monkeypatch.setattr(
        module,
        "_require_deadline_timer_available",
        lambda: events.append("deadline"),
    )
    monkeypatch.setattr(
        module,
        "_configure_deterministic_torch_runtime",
        lambda seed: events.append(f"deterministic:{seed}"),
    )

    module._require_fixed_worker_preflight(request)

    assert events == [
        "source-only",
        "roots",
        "dependencies",
        "commit",
        "clean",
        "source",
        "deadline",
        "deterministic:456",
    ]
    events.clear()
    drifted_dependencies = dict(DEPENDENCY_ROWS)
    drifted_dependencies["torch-distribution"] = "f" * 64
    monkeypatch.setattr(
        module,
        "_observe_dependency_artifact_sha256_rows",
        lambda roots, **kwargs: events.append("dependencies") or drifted_dependencies,
    )
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="dependency bytes do not match",
    ):
        module._require_fixed_worker_preflight(request)
    assert not any(event.startswith("deterministic:") for event in events)


def test_source_only_import_runtime_requires_redirected_disabled_bytecode() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": "/dev/null",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from betelgeuze_engine_v2.physics import "
                "reference_validation_runner as runner; "
                "runner._require_source_only_python_runtime()"
            ),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")


def test_isolated_bootstrap_ignores_pythonpath_user_site_and_sitecustomize(
    tmp_path: Path,
) -> None:
    shadow_root = tmp_path / "shadow"
    shadow_torch = shadow_root / "torch"
    shadow_torch.mkdir(parents=True)
    import_marker = tmp_path / "shadow-imported"
    site_marker = tmp_path / "sitecustomize-imported"
    shadow_torch.joinpath("__init__.py").write_text(
        f"from pathlib import Path\nPath({str(import_marker)!r}).touch()\n",
        encoding="ascii",
    )
    shadow_root.joinpath("sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(site_marker)!r}).touch()\n",
        encoding="ascii",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": os.fspath(shadow_root),
            "PYTHONUSERBASE": os.fspath(shadow_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "123",
            "PYTHONPYCACHEPREFIX": "/dev/null",
            module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV: "456",
        }
    )
    reservation_root = _private_root(tmp_path, "reservations")
    artifact_root = _private_root(tmp_path, "artifacts")
    request = {
        "schema_id": module.REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID,
        "reservation_root": os.fspath(reservation_root),
        "artifact_output_root": os.fspath(artifact_root),
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "authorization_receipt": {},
        "review_attestation": {},
        "expected_implementation_author_identity_sha256": "9" * 64,
        "network_isolation_attestation": {},
        "expected_code_commit_sha": reference_validation_checked_out_code_commit_sha(),
        "expected_runner_source_sha256": reference_validation_runner_source_sha256(),
        "expected_dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [],
        "externally_conflicting_nonce_sha256s": [],
        "revoked_network_attestation_sha256s": [],
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            module.reference_validation_bootstrap_path(),
        ],
        cwd=tmp_path,
        env=environment,
        input=module._canonical_bytes(request) + b"\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 2
    assert completed.stdout == b""
    assert completed.stderr == b""
    assert not import_marker.exists()
    assert not site_marker.exists()


def test_bootstrap_outer_reexecs_before_reading_request_with_minimal_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_bootstrap = bootstrap_module.reference_validation_bootstrap_path()
    executable = os.path.realpath(sys.executable)
    seen: dict[str, object] = {}
    monkeypatch.delenv(
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        raising=False,
    )
    monkeypatch.setenv("PYTHONHASHSEED", "4294967295")
    monkeypatch.setenv(module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV, "456")
    monkeypatch.setenv("PYTHONPATH", "/hostile")
    monkeypatch.setenv("LD_PRELOAD", "/hostile.so")
    monkeypatch.setattr(
        bootstrap_module,
        "_prepare_isolated_outer_launcher",
        lambda **kwargs: (executable, expected_bootstrap),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "_read_bootstrap_request",
        lambda: (_ for _ in ()).throw(AssertionError("stdin read before exec")),
    )
    monkeypatch.setattr(
        bootstrap_module.os,
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

    monkeypatch.setattr(bootstrap_module.os, "execve", reject_execve)

    assert bootstrap_module.main() == 2
    assert seen["cwd"] == "/"
    assert seen["path"] == executable
    assert seen["argv"] == (
        executable,
        *bootstrap_module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    environment = seen["environment"]
    assert isinstance(environment, dict)
    deadline_value = environment.pop(
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV
    )
    assert isinstance(deadline_value, str)
    assert float.fromhex(deadline_value).hex() == deadline_value
    assert float.fromhex(deadline_value) > time.monotonic()
    assert environment == {
        **bootstrap_module._CONTROLLED_INNER_FIXED_ENVIRONMENT,
        "PYTHONHASHSEED": "4294967295",
        module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV: "456",
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV: (
            bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STATE
        ),
    }
    assert "PYTHONPATH" not in environment
    assert "LD_PRELOAD" not in environment


@pytest.mark.parametrize("seed", ["0", "4294967295"])
def test_controlled_inner_environment_accepts_python_hash_seed_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    seed: str,
) -> None:
    monkeypatch.setenv("PYTHONHASHSEED", seed)
    monkeypatch.setenv(module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV, str(2**63 - 1))
    assert (
        bootstrap_module.reference_validation_controlled_inner_environment()[
            "PYTHONHASHSEED"
        ]
        == seed
    )


@pytest.mark.parametrize("seed", ["-1", "01", "random", "4294967296"])
def test_controlled_inner_environment_rejects_invalid_python_hash_seed(
    monkeypatch: pytest.MonkeyPatch,
    seed: str,
) -> None:
    monkeypatch.setenv("PYTHONHASHSEED", seed)
    monkeypatch.setenv(module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV, "456")
    with pytest.raises(
        bootstrap_module._ReferenceValidationBootstrapError,
        match="PYTHONHASHSEED",
    ):
        bootstrap_module.reference_validation_controlled_inner_environment()


def test_seeded_inner_loader_produces_stable_hashes_in_fresh_processes(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "hash_probe.py"
    probe.write_text(
        "print(repr((hash('betelgeuze-seed-probe'),"
        "hash(b'betelgeuze-seed-probe'),"
        "hash(('betelgeuze-seed-probe',17)))))\n",
        encoding="ascii",
    )

    def run(seed: str) -> bytes:
        environment = {
            **bootstrap_module._CONTROLLED_INNER_FIXED_ENVIRONMENT,
            "PYTHONHASHSEED": seed,
            module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV: "456",
            bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV: (
                bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STATE
            ),
        }
        return subprocess.check_output(
            [
                os.path.realpath(sys.executable),
                *bootstrap_module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
                os.fspath(probe),
            ],
            cwd="/",
            env=environment,
        )

    same_seed = [run("123") for _ in range(3)]
    assert same_seed[0] == same_seed[1] == same_seed[2]
    assert run("124") != same_seed[0]


def test_runner_rejects_execution_without_isolated_bootstrap() -> None:
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="seeded controlled dependency bootstrap",
    ):
        module._require_isolated_python_bootstrap_runtime()


def test_bootstrap_verifies_signed_clean_checkout_before_package_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = (
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STATE,
        bootstrap_module.reference_validation_bootstrap_path(),
        os.fspath(Path(module.__file__).resolve().parents[2]),
        ("/trusted/site-packages",),
        ("/checkout", "/trusted/site-packages"),
    )
    seen: list[str] = []
    monkeypatch.delattr(
        bootstrap_module.sys,
        bootstrap_module.REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE,
        raising=False,
    )
    monkeypatch.setattr(
        bootstrap_module,
        "_prepare_seeded_controlled_import_boundary",
        lambda **kwargs: state,
    )
    monkeypatch.setenv(
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STATE,
    )
    monkeypatch.setenv(
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        (time.monotonic() + 10.0).hex(),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "_read_bootstrap_request",
        lambda: (b"{}\n", {}),
    )

    def reject_before_import(*_args: object, **_kwargs: object) -> None:
        seen.append("checkout_verified")
        raise RuntimeError("stop before package import")

    monkeypatch.setattr(
        bootstrap_module,
        "_require_signed_clean_checkout_before_import",
        reject_before_import,
    )

    assert bootstrap_module.main() == 2
    assert seen == ["checkout_verified"]
    assert not hasattr(
        bootstrap_module.sys,
        bootstrap_module.REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE,
    )


def test_bootstrap_checks_dependency_bytes_before_runner_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    state = (
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STATE,
        bootstrap_module.reference_validation_bootstrap_path(),
        "/checkout",
        ("/trusted",),
        ("/checkout", "/trusted"),
    )
    raw = b"{}\n"
    attribute = bootstrap_module.REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE
    monkeypatch.delattr(bootstrap_module.sys, attribute, raising=False)
    monkeypatch.setattr(
        bootstrap_module,
        "_prepare_seeded_controlled_import_boundary",
        lambda **kwargs: state,
    )
    monkeypatch.setenv(
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STATE,
    )
    monkeypatch.setenv(
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        (time.monotonic() + 10.0).hex(),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "_read_bootstrap_request",
        lambda: (raw, {}),
    )

    def verify_signed_source(*_args: object, **_kwargs: object) -> dict[str, object]:
        events.append("signed-clean")
        return deepcopy(BOOTSTRAP_SOURCE_MANIFEST)

    monkeypatch.setattr(
        bootstrap_module,
        "_require_signed_clean_checkout_before_import",
        verify_signed_source,
    )
    monkeypatch.setattr(
        bootstrap_module,
        "_require_observed_dependency_artifact_rows_before_import",
        lambda repository_root, roots, request, **kwargs: events.append("dependencies"),
    )

    def run_runner(received: bytes) -> int:
        assert getattr(bootstrap_module.sys, attribute) == (
            *state,
            bootstrap_module._canonical_bytes(BOOTSTRAP_SOURCE_MANIFEST),
        )
        assert received == raw
        events.append("runner")
        return 0

    monkeypatch.setattr(module, "_main_from_canonical_request", run_runner)

    assert bootstrap_module.main() == 0
    assert events == ["signed-clean", "dependencies", "runner"]


def test_bootstrap_dependency_failure_blocks_runner_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = (
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STATE,
        bootstrap_module.reference_validation_bootstrap_path(),
        "/checkout",
        ("/trusted",),
        ("/checkout", "/trusted"),
    )
    attribute = bootstrap_module.REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE
    monkeypatch.delattr(bootstrap_module.sys, attribute, raising=False)
    monkeypatch.setattr(
        bootstrap_module,
        "_prepare_seeded_controlled_import_boundary",
        lambda **kwargs: state,
    )
    monkeypatch.setenv(
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_STATE,
    )
    monkeypatch.setenv(
        bootstrap_module.REFERENCE_VALIDATION_CONTROLLED_INNER_PREFLIGHT_DEADLINE_ENV,
        (time.monotonic() + 10.0).hex(),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "_read_bootstrap_request",
        lambda: (b"{}\n", {}),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "_require_signed_clean_checkout_before_import",
        lambda *_args, **_kwargs: deepcopy(BOOTSTRAP_SOURCE_MANIFEST),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "_require_observed_dependency_artifact_rows_before_import",
        lambda repository_root, roots, request, **kwargs: (_ for _ in ()).throw(
            RuntimeError("dependency drift")
        ),
    )
    monkeypatch.setattr(
        module,
        "_main_from_canonical_request",
        lambda raw: (_ for _ in ()).throw(AssertionError("runner imported")),
    )

    assert bootstrap_module.main() == 2
    assert not hasattr(bootstrap_module.sys, attribute)


def test_bootstrap_trusts_only_operator_signed_commit_and_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key_id = "bootstrap-operator"
    operator_identity = "8" * 64
    verification_key = b"bootstrap-operator-verification-key-material"
    commit = reference_validation_checked_out_code_commit_sha()
    source = reference_validation_runner_source_sha256()
    author_identity = "7" * 64
    projection = {
        "authorization_key_id": key_id,
        "authorization_operator_identity_sha256": operator_identity,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "implementation_author_identity_sha256": author_identity,
        "code_commit_sha": commit,
        "runner_source_sha256": source,
        "dependency_artifact_sha256_rows": [
            {"artifact_id": artifact_id, "sha256": digest}
            for artifact_id, digest in sorted(DEPENDENCY_ROWS.items())
        ],
    }
    receipt = dict(projection)
    receipt["receipt_sha256"] = hashlib.sha256(
        bootstrap_module._canonical_bytes(projection)
    ).hexdigest()
    receipt["signature"] = {
        "algorithm": "hmac-sha256",
        "key_id": key_id,
        "value": hmac.new(
            verification_key,
            bootstrap_module._canonical_bytes(receipt),
            hashlib.sha256,
        ).hexdigest(),
    }
    request: dict[str, object] = {
        "authorization_receipt": receipt,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "expected_implementation_author_identity_sha256": author_identity,
        "expected_dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
    }
    monkeypatch.setattr(
        bootstrap_module,
        "_load_bootstrap_operator_keys",
        lambda: {key_id: (operator_identity, verification_key)},
    )

    bootstrap_module._require_bootstrap_authorization_signature(
        request,
        expected_commit=commit,
        expected_source=source,
    )
    with pytest.raises(
        RuntimeError,
        match="source binding is invalid",
    ):
        bootstrap_module._require_bootstrap_authorization_signature(
            request,
            expected_commit="f" * 40,
            expected_source=source,
        )


def test_validation_roots_must_not_overlap_the_source_checkout() -> None:
    repository_root = Path(module.__file__).resolve().parents[2]
    with pytest.raises(
        run_start_module.ReferenceValidationRunStartError,
        match="outside the source checkout",
    ):
        run_start_module._require_reference_validation_root_outside_checkout(
            repository_root,
            name="artifact output root",
        )
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="outside the source checkout",
    ):
        run_bounded_cpu_reference_validation(
            repository_root,
            AUTHORIZATION_NONCE,
            expected_environment_receipt_sha256=ENVIRONMENT_RECEIPT_SHA256,
            expected_code_commit_sha=CODE_COMMIT_SHA,
            expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        )


def test_source_only_import_runtime_ignores_a_valid_timestamp_cache(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cached_target.py"
    source.write_text("VALUE='cache!'\n", encoding="ascii")
    original_stat = source.stat()
    py_compile.compile(source, doraise=True)
    source.write_text("VALUE='source'\n", encoding="ascii")
    os.utime(
        source,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )
    command = [
        sys.executable,
        "-c",
        "import cached_target; print(cached_target.VALUE)",
    ]
    vulnerable_environment = os.environ.copy()
    vulnerable_environment["PYTHONPATH"] = os.fspath(tmp_path)
    vulnerable_environment.pop("PYTHONDONTWRITEBYTECODE", None)
    vulnerable_environment.pop("PYTHONPYCACHEPREFIX", None)
    vulnerable = subprocess.run(
        command,
        env=vulnerable_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert vulnerable.returncode == 0
    assert vulnerable.stdout == b"cache!\n"

    source_only_environment = dict(vulnerable_environment)
    source_only_environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": "/dev/null",
        }
    )
    source_only = subprocess.run(
        command,
        env=source_only_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert source_only.returncode == 0
    assert source_only.stdout == b"source\n"


def test_runner_public_surface_has_no_unsafe_clock_writer_or_evaluator() -> None:
    signature = inspect.signature(run_bounded_cpu_reference_validation)
    assert "checked_at" not in signature.parameters
    assert module.main() == 2
    public = set(module.__all__)
    assert not any(name.startswith("delete_") for name in public)
    assert not any(name.startswith("release_") for name in public)
    assert not any(name.startswith("write_result") for name in public)

    source = inspect.getsource(module)
    tree = ast.parse(source)
    top_level_imports = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module == "reference_forcefield"
        for node in top_level_imports
    )
    imported_modules = {
        alias.name.split(".", 1)[0]
        for node in top_level_imports
        for alias in node.names
        if isinstance(node, ast.Import)
    }
    assert "subprocess" not in imported_modules
    assert "socket" not in imported_modules


def test_exact_module_entrypoint_dispatches_canonical_stdin_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = {
        "schema_id": module.REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID,
        "reservation_root": "/private/reservations",
        "artifact_output_root": "/private/results",
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "authorization_receipt": {"signed": "authorization"},
        "review_attestation": {"signed": "review"},
        "expected_implementation_author_identity_sha256": "9" * 64,
        "network_isolation_attestation": {"signed": "network"},
        "expected_code_commit_sha": CODE_COMMIT_SHA,
        "expected_runner_source_sha256": "b" * 64,
        "expected_dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [],
        "externally_conflicting_nonce_sha256s": [],
        "revoked_network_attestation_sha256s": [],
    }
    response = {
        "schema_id": module.REFERENCE_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "claim_safe": False,
    }
    encoded_request = module._canonical_bytes(request) + b"\n"
    output = io.BytesIO()
    monkeypatch.setattr(
        module.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(encoded_request)),
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


def test_preconfigured_trust_store_parses_keys_and_enforces_root_owned_stats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schema_id": module.REFERENCE_VALIDATION_TRUST_STORE_SCHEMA_ID,
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

    assert set(reviewer_keys) == {"reviewer"}
    assert set(operator_keys) == {"operator"}
    assert reviewer_keys["reviewer"].verification_key == b"\xaa" * 32
    assert operator_keys["operator"].verification_key == b"\xbb" * 32

    module._validate_preconfigured_trust_directory(
        SimpleNamespace(st_mode=module.stat.S_IFDIR | 0o755, st_uid=0)
    )
    with pytest.raises(ReferenceValidationRunnerError, match="directory policy"):
        module._validate_preconfigured_trust_directory(
            SimpleNamespace(st_mode=module.stat.S_IFDIR | 0o777, st_uid=0)
        )
    validate_file(
        SimpleNamespace(
            st_mode=module.stat.S_IFREG | 0o600,
            st_uid=0,
            st_nlink=1,
            st_size=store_path.stat().st_size,
        )
    )
    with pytest.raises(ReferenceValidationRunnerError, match="file policy"):
        validate_file(
            SimpleNamespace(
                st_mode=module.stat.S_IFREG | 0o600,
                st_uid=1,
                st_nlink=1,
                st_size=store_path.stat().st_size,
            )
        )


def test_exact_module_invocation_cannot_self_authorize_with_request_keys(
    tmp_path: Path,
) -> None:
    reservation_root = _private_root(tmp_path, "reservations")
    artifact_root = _private_root(tmp_path, "artifacts")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    reviewed_at = now - timedelta(minutes=1)
    review_expires_at = now + timedelta(minutes=10)
    authorization_expires_at = now + timedelta(minutes=5)
    network_expires_at = now + timedelta(minutes=2)
    author_identity = "1" * 64
    reviewer_identity = "2" * 64
    operator_identity = "3" * 64
    review_key_id = "entrypoint-reviewer"
    operator_key_id = "entrypoint-operator"
    review_key = b"entrypoint-review-key-material-32-bytes-minimum"
    operator_key = b"entrypoint-operator-key-material-32-bytes-minimum"
    nonce = hashlib.sha256(os.fspath(tmp_path).encode("utf-8")).hexdigest()
    review_nonce = hashlib.sha256(f"review:{tmp_path}".encode("utf-8")).hexdigest()
    code_commit = reference_validation_checked_out_code_commit_sha()
    runner_source = reference_validation_runner_source_sha256()
    dependencies = {
        "cryptography-distribution": "4" * 64,
        "numpy-distribution": "5" * 64,
        "openssl-executable": "6" * 64,
        "python-runtime-executable": "7" * 64,
        "python-standard-library": "8" * 64,
        "torch-distribution": "9" * 64,
    }
    review = build_signed_reference_validation_review_attestation(
        implementation_author_identity_sha256=author_identity,
        independent_reviewer_identity_sha256=reviewer_identity,
        reviewer_key_id=review_key_id,
        signing_key=review_key,
        reviewed_at=reviewed_at,
        expires_at=review_expires_at,
        nonce_sha256=review_nonce,
    )
    reviewer_keys = {
        review_key_id: ScientificReviewerTrustAnchor(
            reviewer_identity,
            review_key,
        )
    }
    authorization = build_signed_reference_validation_authorization_receipt(
        review_attestation=review,
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=author_identity,
        authorization_operator_identity_sha256=operator_identity,
        authorization_key_id=operator_key_id,
        signing_key=operator_key,
        issued_at=now,
        expires_at=authorization_expires_at,
        authorization_nonce_sha256=nonce,
        code_commit_sha=code_commit,
        runner_source_sha256=runner_source,
        execution_environment_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        result_receipt_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        dependency_artifact_sha256_rows=dependencies,
    )
    operator_keys = {
        operator_key_id: AuthorizationOperatorTrustAnchor(
            operator_identity,
            operator_key,
        )
    }
    reserve_reference_validation_authorization_nonce(
        reservation_root,
        authorization_receipt=authorization,
        review_attestation=review,
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=author_identity,
        trusted_operator_keys=operator_keys,
        reserved_at=now,
        expected_code_commit_sha=code_commit,
        expected_runner_source_sha256=runner_source,
        expected_dependency_artifact_sha256_rows=dependencies,
    )
    namespace_identity = hashlib.sha256(
        os.readlink("/proc/self/ns/net").encode("utf-8")
    ).hexdigest()
    network = build_signed_reference_validation_network_isolation_attestation(
        authorization_receipt_sha256=authorization["receipt_sha256"],
        authorization_nonce_sha256=nonce,
        authorization_operator_identity_sha256=operator_identity,
        authorization_key_id=operator_key_id,
        signing_key=operator_key,
        code_commit_sha=code_commit,
        runner_source_sha256=runner_source,
        artifact_output_root_identity_sha256=(
            reference_validation_artifact_output_root_identity_sha256(artifact_root)
        ),
        network_namespace_identity_sha256=namespace_identity,
        observed_at=now,
        expires_at=network_expires_at,
    )
    request = {
        "schema_id": module.REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID,
        "reservation_root": os.fspath(reservation_root),
        "artifact_output_root": os.fspath(artifact_root),
        "authorization_nonce_sha256": nonce,
        "authorization_receipt": authorization,
        "review_attestation": review,
        "expected_implementation_author_identity_sha256": author_identity,
        "network_isolation_attestation": network,
        "expected_code_commit_sha": code_commit,
        "expected_runner_source_sha256": runner_source,
        "expected_dependency_artifact_sha256_rows": dependencies,
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [],
        "externally_conflicting_nonce_sha256s": [],
        "revoked_network_attestation_sha256s": [],
    }
    environment = os.environ.copy()
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "HIP_VISIBLE_DEVICES": "",
            "ROCR_VISIBLE_DEVICES": "",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "MKL_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": "/dev/null",
            "TZ": "UTC",
            "PYTHONHASHSEED": "123",
            "BETELGEUZE_REFERENCE_VALIDATION_SEED": "456",
        }
    )
    self_authorized_request = dict(request)
    self_authorized_request["trusted_reviewer_keys"] = [
        {
            "key_id": review_key_id,
            "reviewer_identity_sha256": reviewer_identity,
            "verification_key_hex": review_key.hex(),
        }
    ]
    self_authorized_request["trusted_operator_keys"] = [
        {
            "key_id": operator_key_id,
            "operator_identity_sha256": operator_identity,
            "verification_key_hex": operator_key.hex(),
        }
    ]
    for candidate in (self_authorized_request, request):
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                module.reference_validation_bootstrap_path(),
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            input=module._canonical_bytes(candidate) + b"\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        assert completed.returncode == 2
        assert completed.stdout == b""
        assert operator_key.hex().encode("ascii") not in completed.stderr

    assert list(artifact_root.iterdir()) == []
    secret_hex = operator_key.hex().encode("ascii")
    assert secret_hex not in completed.stdout
    assert secret_hex not in completed.stderr


def test_manifest_worker_accepts_exact_pre_payload_completion_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    expected_protocol, manifest, _cases = frozen_worker_matrix
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    monkeypatch.setattr(
        module,
        "_start_fixed_validation_worker",
        lambda worker_flag, request: SimpleNamespace(pid=1, returncode=0),
    )

    def communicate(process: object, request: Mapping[str, Any], *, deadline: float):
        frames = _valid_manifest_worker_frames(request, manifest)
        return _worker_frames_bytes(frames), False, True

    monkeypatch.setattr(
        module,
        "_communicate_fixed_validation_worker",
        communicate,
    )
    protocol, cases, manifest_sha256, lifecycle, provenance = (
        module._run_supervised_frozen_case_matrix(
            expected_code_commit_sha=CODE_COMMIT_SHA,
            expected_runner_source_sha256=reference_validation_runner_source_sha256(),
            expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
            dependency_roots=(Path("/trusted"),),
            environment_receipt=receipt,
            worker_environment=worker_environment,
            deadline=time.monotonic() + 120.0,
        )
    )

    assert protocol == expected_protocol
    assert cases == manifest["cases"]
    assert manifest_sha256 == manifest["materialization_manifest_sha256"]
    assert lifecycle["completion_state"] == "complete"
    assert lifecycle["payload"]["payload_row_count"] == 1
    assert lifecycle["pre"]["snapshot"] == lifecycle["post"]["snapshot"]
    assert provenance["supervisor_launched_child_process_id"] == 1


@pytest.mark.parametrize("worker_kind", ["manifest", "case"])
def test_worker_main_emits_canonical_pre_payload_completion_frames(
    worker_kind: str,
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    protocol, manifest, cases = frozen_worker_matrix
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    request = module._fixed_worker_request(
        worker_kind=worker_kind,
        expected_materialization_manifest_sha256=(
            None
            if worker_kind == "manifest"
            else manifest["materialization_manifest_sha256"]
        ),
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_runner_source_sha256=reference_validation_runner_source_sha256(),
        expected_source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        expected_authorization_nonce_sha256=AUTHORIZATION_NONCE,
        expected_runner_start_record_sha256=(
            None if worker_kind == "manifest" else "1" * 64
        ),
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=receipt,
        worker_environment=worker_environment,
    )
    request_sha256 = module._worker_request_sha256(request)
    input_bytes = io.BytesIO(module._canonical_bytes(request) + b"\n")
    output_bytes = io.BytesIO()
    monkeypatch.setattr(
        module,
        "sys",
        SimpleNamespace(
            stdin=SimpleNamespace(buffer=input_bytes),
            stdout=SimpleNamespace(buffer=output_bytes),
        ),
    )
    monkeypatch.setattr(module, "_require_fixed_worker_preflight", lambda request: None)
    monkeypatch.setattr(
        module,
        "_load_frozen_case_manifest_document",
        lambda: (protocol, manifest),
    )
    monkeypatch.setattr(
        module,
        "_iter_case_matrix_in_process",
        lambda protocol, manifest_cases, **kwargs: iter(cases),
    )

    def build_pre(*, lane: str, worker_request_sha256: str, **kwargs: object):
        return native_identity.build_worker_runtime_pre_evidence(
            lane=lane,
            worker_request_sha256=worker_request_sha256,
            snapshot=_test_native_snapshot(),
        )

    def build_complete(
        *,
        lane: str,
        worker_request_sha256: str,
        pre_evidence: Mapping[str, Any],
        payload_rows: Sequence[Mapping[str, Any]],
        **kwargs: object,
    ):
        return native_identity.build_complete_worker_runtime_lifecycle_evidence(
            lane=lane,
            worker_request_sha256=worker_request_sha256,
            pre_evidence=pre_evidence,
            payload_rows=payload_rows,
            post_snapshot=_test_native_snapshot(),
        )

    monkeypatch.setattr(module, "build_worker_runtime_pre_evidence", build_pre)
    monkeypatch.setattr(
        module,
        "build_complete_worker_runtime_lifecycle_evidence",
        build_complete,
    )

    assert module._fixed_worker_main([f"--{worker_kind}-worker"]) == 0
    frames = [
        module._decode_worker_frame(line)
        for line in output_bytes.getvalue().splitlines(keepends=True)
    ]
    expected_payloads = (
        [module._manifest_worker_payload(manifest)]
        if worker_kind == "manifest"
        else [row.to_dict() for row in cases]
    )
    assert [frame["frame_type"] for frame in frames] == [
        "pre",
        *(["payload"] * len(expected_payloads)),
        "completion",
    ]
    assert all(frame["worker_kind"] == worker_kind for frame in frames)
    assert all(frame["worker_request_sha256"] == request_sha256 for frame in frames)
    assert [frame["ordinal"] for frame in frames[1:-1]] == list(
        range(len(expected_payloads))
    )
    assert [frame["payload"] for frame in frames[1:-1]] == expected_payloads
    lane = (
        native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST
        if worker_kind == "manifest"
        else native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE
    )
    lifecycle = native_identity.require_worker_runtime_lifecycle_evidence(
        frames[-1]["evidence"],
        expected_lane=lane,
        expected_worker_request_sha256=request_sha256,
        expected_payload_rows=expected_payloads,
    )
    assert lifecycle["completion_state"] == "complete"
    assert lifecycle["pre"] == frames[0]["evidence"]


@pytest.mark.parametrize(
    "mutation",
    [
        "omitted_payload",
        "reordered",
        "duplicate",
        "extra",
        "request_sha256",
        "aggregate",
        "post",
    ],
)
def test_manifest_worker_rejects_nonexact_frame_or_lifecycle(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    _protocol, manifest, _cases = frozen_worker_matrix
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    monkeypatch.setattr(
        module,
        "_start_fixed_validation_worker",
        lambda worker_flag, request: SimpleNamespace(pid=1, returncode=0),
    )

    def communicate(process: object, request: Mapping[str, Any], *, deadline: float):
        frames = _valid_manifest_worker_frames(request, manifest)
        if mutation == "omitted_payload":
            del frames[1]
        elif mutation == "reordered":
            frames[0], frames[1] = frames[1], frames[0]
        elif mutation == "duplicate":
            frames.insert(2, deepcopy(frames[1]))
        elif mutation == "extra":
            frames.append(deepcopy(frames[-1]))
        elif mutation == "request_sha256":
            frames[1]["worker_request_sha256"] = "0" * 64
        elif mutation == "aggregate":
            frames[-1]["evidence"]["payload_aggregate_sha256"] = "0" * 64
        elif mutation == "post":
            frames[-1]["evidence"]["post"]["snapshot"]["mapping_rows"][0][
                "address_end_hex"
            ] = "3"
        else:  # pragma: no cover - closed parameter set
            raise AssertionError(mutation)
        return _worker_frames_bytes(frames), False, True

    monkeypatch.setattr(
        module,
        "_communicate_fixed_validation_worker",
        communicate,
    )
    with pytest.raises(ReferenceValidationRunnerError):
        module._run_supervised_frozen_case_matrix(
            expected_code_commit_sha=CODE_COMMIT_SHA,
            expected_runner_source_sha256=reference_validation_runner_source_sha256(),
            expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
            dependency_roots=(Path("/trusted"),),
            environment_receipt=receipt,
            worker_environment=worker_environment,
            deadline=time.monotonic() + 120.0,
        )


def test_case_worker_accepts_exact_pre_payload_completion_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    protocol, manifest, expected_cases = frozen_worker_matrix

    def communicate(process: object, request: Mapping[str, Any], *, deadline: float):
        frames = _valid_case_worker_frames(request, expected_cases)
        return _worker_frames_bytes(frames), False, True

    cases, lifecycle, _provenance = _call_supervised_case_worker(
        monkeypatch,
        protocol=protocol,
        manifest=manifest,
        communicate=communicate,
    )

    assert cases == expected_cases
    assert all(case.observation_origin == "worker" for case in cases)
    assert lifecycle["completion_state"] == "complete"
    assert lifecycle["failure_code"] is None
    assert lifecycle["payload"]["payload_row_count"] == 27
    assert lifecycle["pre"]["snapshot"] == lifecycle["post"]["snapshot"]


@pytest.mark.parametrize(
    "mutation",
    [
        "omitted_payload",
        "omitted_completion",
        "reordered",
        "duplicate",
        "extra",
        "request_sha256",
        "aggregate",
        "post",
        "malformed",
    ],
)
def test_case_worker_protocol_failure_discards_every_worker_payload(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    protocol, manifest, worker_cases = frozen_worker_matrix

    def communicate(process: object, request: Mapping[str, Any], *, deadline: float):
        frames = _valid_case_worker_frames(request, worker_cases)
        if mutation == "omitted_payload":
            del frames[7]
        elif mutation == "omitted_completion":
            frames.pop()
        elif mutation == "reordered":
            frames[1], frames[2] = frames[2], frames[1]
        elif mutation == "duplicate":
            frames.insert(2, deepcopy(frames[1]))
        elif mutation == "extra":
            frames.append(deepcopy(frames[-1]))
        elif mutation == "request_sha256":
            frames[7]["worker_request_sha256"] = "0" * 64
        elif mutation == "aggregate":
            frames[-1]["evidence"]["payload_aggregate_sha256"] = "0" * 64
        elif mutation == "post":
            frames[-1]["evidence"]["post"]["snapshot"]["mapping_rows"][0][
                "address_end_hex"
            ] = "3"
        elif mutation == "malformed":
            lines = [module._canonical_bytes(dict(frame)) + b"\n" for frame in frames]
            lines[7] = b'{"malformed":]\n'
            return b"".join(lines), False, True
        else:  # pragma: no cover - closed parameter set
            raise AssertionError(mutation)
        return _worker_frames_bytes(frames), False, True

    rows, lifecycle, _provenance = _call_supervised_case_worker(
        monkeypatch,
        protocol=protocol,
        manifest=manifest,
        communicate=communicate,
    )
    _assert_supervisor_failure_complete(
        rows,
        lifecycle,
        expected_status="unexpected_error",
        expected_error_code="case_worker_protocol_invalid",
    )


@pytest.mark.parametrize("emitted_payload_count", [1, 26, 27])
def test_case_worker_partial_timeout_discards_one_twenty_six_or_twenty_seven_rows(
    emitted_payload_count: int,
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    protocol, manifest, worker_cases = frozen_worker_matrix

    def communicate(process: object, request: Mapping[str, Any], *, deadline: float):
        frames = _valid_case_worker_frames(request, worker_cases)
        partial = frames[: emitted_payload_count + 1]
        return _worker_frames_bytes(partial), True, False

    rows, lifecycle, _provenance = _call_supervised_case_worker(
        monkeypatch,
        protocol=protocol,
        manifest=manifest,
        communicate=communicate,
    )
    _assert_supervisor_failure_complete(
        rows,
        lifecycle,
        expected_status="time_budget_exhausted",
        expected_error_code="runner_time_budget_exhausted",
    )


def test_case_worker_nonzero_exit_discards_a_complete_looking_payload(
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    protocol, manifest, worker_cases = frozen_worker_matrix

    def communicate(process: object, request: Mapping[str, Any], *, deadline: float):
        frames = _valid_case_worker_frames(request, worker_cases)
        return _worker_frames_bytes(frames), False, False

    rows, lifecycle, _provenance = _call_supervised_case_worker(
        monkeypatch,
        protocol=protocol,
        manifest=manifest,
        communicate=communicate,
    )
    _assert_supervisor_failure_complete(
        rows,
        lifecycle,
        expected_status="unexpected_error",
        expected_error_code="case_worker_nonzero_exit",
    )


@pytest.mark.parametrize(
    ("worker_kind", "field", "replacement"),
    [
        ("case", "expected_protocol_sha256", "0" * 64),
        ("case", "expected_case_count", 26),
        ("case", "expected_variant_count", 58),
        ("case", "expected_materialization_manifest_sha256", None),
        ("manifest", "expected_materialization_manifest_sha256", "f" * 64),
    ],
)
def test_worker_request_rejects_protocol_coverage_or_manifest_binding_drift(
    worker_kind: str,
    field: str,
    replacement: object,
) -> None:
    receipt = _receipt()
    worker_environment = module._case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    request = module._fixed_worker_request(
        worker_kind=worker_kind,
        expected_materialization_manifest_sha256=(
            None if worker_kind == "manifest" else "f" * 64
        ),
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_runner_source_sha256=reference_validation_runner_source_sha256(),
        expected_source_manifest_sha256=SOURCE_MANIFEST_SHA256,
        expected_authorization_nonce_sha256=AUTHORIZATION_NONCE,
        expected_runner_start_record_sha256=(
            None if worker_kind == "manifest" else "1" * 64
        ),
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=receipt,
        worker_environment=worker_environment,
    )
    request[field] = replacement

    with pytest.raises(ReferenceValidationRunnerError, match="runtime binding"):
        module._load_case_worker_request(module._canonical_bytes(request) + b"\n")


def test_run_observation_rejects_lifecycle_origin_and_aggregate_cross_wiring(
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    _protocol, _manifest, cases = frozen_worker_matrix
    observation = module.ReferenceValidationRunObservation(
        runner_start_record_sha256="1" * 64,
        execution_environment_receipt_sha256="2" * 64,
        environment_fingerprint_sha256="3" * 64,
        authorization_receipt_sha256="4" * 64,
        authorization_nonce_sha256="5" * 64,
        code_commit_sha="6" * 40,
        runner_source_sha256="7" * 64,
        source_manifest_sha256="8" * 64,
        dependency_artifact_sha256_rows=tuple(sorted(DEPENDENCY_ROWS.items())),
        command_argv=module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
        seed=123,
        started_at_utc="2026-07-17T09:00:00Z",
        completed_at_utc="2026-07-17T09:01:00Z",
        case_results=cases,
        **_observation_lifecycle_fields(cases),
    )

    def resign(payload: dict[str, Any]) -> dict[str, Any]:
        projection = dict(payload)
        projection.pop("observation_sha256", None)
        payload["observation_sha256"] = module._sha256(projection)
        return payload

    aggregate_tamper = deepcopy(observation.to_dict())
    aggregate_tamper["retained_case_payload_aggregate_sha256"] = "0" * 64
    with pytest.raises(ReferenceValidationRunnerError, match="aggregate drifted"):
        module.require_reference_validation_run_observation_document(
            resign(aggregate_tamper)
        )

    incomplete_with_worker_rows = deepcopy(observation.to_dict())
    complete_case_lifecycle = incomplete_with_worker_rows[
        "case_worker_lifecycle_evidence"
    ]
    incomplete_with_worker_rows["case_worker_lifecycle_evidence"] = (
        native_identity.build_incomplete_worker_runtime_lifecycle_evidence(
            lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
            worker_request_sha256=complete_case_lifecycle["worker_request_sha256"],
            failure_code="case_worker_protocol_invalid",
            pre_evidence=complete_case_lifecycle["pre"],
        )
    )
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="worker execution provenance",
    ):
        module.require_reference_validation_run_observation_document(
            resign(incomplete_with_worker_rows)
        )

    complete_with_supervisor_row = deepcopy(observation.to_dict())
    complete_with_supervisor_row["case_results"][0]["observation_origin"] = "supervisor"
    supervisor_payload_rows = complete_with_supervisor_row["case_results"]
    complete_with_supervisor_row["case_worker_lifecycle_evidence"] = (
        _complete_worker_lifecycle(
            lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
            worker_request_sha256=CASE_WORKER_REQUEST_SHA256,
            payload_rows=supervisor_payload_rows,
        )
    )
    complete_with_supervisor_row["retained_case_payload_aggregate_sha256"] = (
        module._sha256(supervisor_payload_rows)
    )
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="worker execution provenance",
    ):
        module.require_reference_validation_run_observation_document(
            resign(complete_with_supervisor_row)
        )

    incomplete_manifest = deepcopy(observation.to_dict())
    complete_manifest_lifecycle = incomplete_manifest[
        "manifest_worker_lifecycle_evidence"
    ]
    incomplete_manifest["manifest_worker_lifecycle_evidence"] = (
        native_identity.build_incomplete_worker_runtime_lifecycle_evidence(
            lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
            worker_request_sha256=complete_manifest_lifecycle["worker_request_sha256"],
            failure_code="manifest_worker_protocol_invalid",
            pre_evidence=complete_manifest_lifecycle["pre"],
        )
    )
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="worker execution provenance",
    ):
        module.require_reference_validation_run_observation_document(
            resign(incomplete_manifest)
        )


def test_run_observation_rejects_unreachable_incomplete_failure_code(
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    protocol, manifest, _cases = frozen_worker_matrix
    rows = module._supervisor_failure_complete_case_matrix(
        protocol,
        manifest["cases"],
        observed_status="unexpected_error",
        observed_error_code="made_up_failure",
    )
    lifecycle_fields = _observation_lifecycle_fields(rows)
    complete_case_lifecycle = json.loads(
        lifecycle_fields["case_worker_lifecycle_evidence_bytes"].decode("ascii")
    )
    lifecycle_fields["case_worker_lifecycle_evidence_bytes"] = module._canonical_bytes(
        native_identity.build_incomplete_worker_runtime_lifecycle_evidence(
            lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
            worker_request_sha256=complete_case_lifecycle["worker_request_sha256"],
            failure_code="made_up_failure",
            pre_evidence=complete_case_lifecycle["pre"],
        )
    )

    with pytest.raises(
        ReferenceValidationRunnerError, match="worker execution provenance"
    ):
        module.ReferenceValidationRunObservation(
            runner_start_record_sha256="1" * 64,
            execution_environment_receipt_sha256="2" * 64,
            environment_fingerprint_sha256="3" * 64,
            authorization_receipt_sha256="4" * 64,
            authorization_nonce_sha256="5" * 64,
            code_commit_sha="6" * 40,
            runner_source_sha256="7" * 64,
            source_manifest_sha256="8" * 64,
            dependency_artifact_sha256_rows=tuple(sorted(DEPENDENCY_ROWS.items())),
            command_argv=module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
            seed=123,
            started_at_utc="2026-07-17T09:00:00Z",
            completed_at_utc="2026-07-17T09:01:00Z",
            case_results=rows,
            **lifecycle_fields,
        )


def _resign_worker_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    projection = dict(payload)
    projection.pop("provenance_sha256", None)
    payload["provenance_sha256"] = module._sha256(projection)
    return payload


def _resign_run_observation(payload: dict[str, Any]) -> dict[str, Any]:
    projection = dict(payload)
    projection.pop("observation_sha256", None)
    payload["observation_sha256"] = module._sha256(projection)
    return payload


@pytest.mark.parametrize("mutation", ["request_duplicate_key", "request_noncanonical"])
def test_run_observation_rejects_forged_request_transport_even_when_rehashed(
    mutation: str,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    _protocol, _manifest, cases = frozen_worker_matrix
    observation = module.ReferenceValidationRunObservation(
        runner_start_record_sha256="1" * 64,
        execution_environment_receipt_sha256="2" * 64,
        environment_fingerprint_sha256="3" * 64,
        authorization_receipt_sha256="4" * 64,
        authorization_nonce_sha256="5" * 64,
        code_commit_sha="6" * 40,
        runner_source_sha256="7" * 64,
        source_manifest_sha256="8" * 64,
        dependency_artifact_sha256_rows=tuple(sorted(DEPENDENCY_ROWS.items())),
        command_argv=module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
        seed=123,
        started_at_utc="2026-07-17T09:00:00Z",
        completed_at_utc="2026-07-17T09:01:00Z",
        case_results=cases,
        **_observation_lifecycle_fields(cases),
    )
    forged = deepcopy(observation.to_dict())
    provenance = forged["case_worker_execution_provenance"]
    request_bytes = bytes.fromhex(provenance["worker_request_canonical_jsonl_hex"])
    if mutation == "request_duplicate_key":
        schema = module.REFERENCE_VALIDATION_CASE_WORKER_REQUEST_SCHEMA_ID.encode(
            "ascii"
        )
        request_bytes = b'{"schema_id":"' + schema + b'",' + request_bytes[1:]
    else:
        request_bytes = request_bytes[:-1] + b" \n"
    provenance["worker_request_canonical_jsonl_hex"] = request_bytes.hex()
    provenance["worker_request_byte_count"] = len(request_bytes)
    provenance["worker_request_transport_sha256"] = hashlib.sha256(
        request_bytes
    ).hexdigest()
    _resign_worker_provenance(provenance)

    with pytest.raises(
        ReferenceValidationRunnerError,
        match="worker execution provenance is invalid",
    ):
        module.require_reference_validation_run_observation_document(
            _resign_run_observation(forged)
        )


@pytest.mark.parametrize("mutation", ["transcript_sha", "child_pid"])
def test_run_observation_rejects_rehashed_transcript_or_pid_forgery(
    mutation: str,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    _protocol, _manifest, cases = frozen_worker_matrix
    observation = module.ReferenceValidationRunObservation(
        runner_start_record_sha256="1" * 64,
        execution_environment_receipt_sha256="2" * 64,
        environment_fingerprint_sha256="3" * 64,
        authorization_receipt_sha256="4" * 64,
        authorization_nonce_sha256="5" * 64,
        code_commit_sha="6" * 40,
        runner_source_sha256="7" * 64,
        source_manifest_sha256="8" * 64,
        dependency_artifact_sha256_rows=tuple(sorted(DEPENDENCY_ROWS.items())),
        command_argv=module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
        seed=123,
        started_at_utc="2026-07-17T09:00:00Z",
        completed_at_utc="2026-07-17T09:01:00Z",
        case_results=cases,
        **_observation_lifecycle_fields(cases),
    )
    forged = deepcopy(observation.to_dict())
    provenance = forged["case_worker_execution_provenance"]
    if mutation == "transcript_sha":
        provenance["transcript_sha256"] = "0" * 64
    else:
        provenance["supervisor_launched_child_process_id"] = 2
    _resign_worker_provenance(provenance)

    with pytest.raises(ReferenceValidationRunnerError, match="provenance"):
        module.require_reference_validation_run_observation_document(
            _resign_run_observation(forged)
        )


def test_run_observation_rejects_self_consistent_worker_transplant_between_runs(
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    _protocol, _manifest, cases = frozen_worker_matrix
    fields_a = _observation_lifecycle_fields(cases)
    fields_b = _observation_lifecycle_fields(
        cases,
        runner_start_record_sha256="9" * 64,
        execution_environment_receipt_sha256="a" * 64,
        environment_fingerprint_sha256="b" * 64,
        authorization_nonce_sha256="c" * 64,
    )
    observation = module.ReferenceValidationRunObservation(
        runner_start_record_sha256="1" * 64,
        execution_environment_receipt_sha256="2" * 64,
        environment_fingerprint_sha256="3" * 64,
        authorization_receipt_sha256="4" * 64,
        authorization_nonce_sha256="5" * 64,
        code_commit_sha="6" * 40,
        runner_source_sha256="7" * 64,
        source_manifest_sha256="8" * 64,
        dependency_artifact_sha256_rows=tuple(sorted(DEPENDENCY_ROWS.items())),
        command_argv=module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
        seed=123,
        started_at_utc="2026-07-17T09:00:00Z",
        completed_at_utc="2026-07-17T09:01:00Z",
        case_results=cases,
        **fields_a,
    )
    transplanted = deepcopy(observation.to_dict())
    transplanted["case_worker_lifecycle_evidence"] = json.loads(
        fields_b["case_worker_lifecycle_evidence_bytes"].decode("ascii")
    )
    transplanted["case_worker_execution_provenance"] = json.loads(
        fields_b["case_worker_execution_provenance_bytes"].decode("ascii")
    )

    with pytest.raises(ReferenceValidationRunnerError, match="provenance"):
        module.require_reference_validation_run_observation_document(
            _resign_run_observation(transplanted)
        )


def test_incomplete_worker_provenance_retains_timeout_prefix_and_discards_payload(
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    protocol, manifest, cases = frozen_worker_matrix

    def communicate(process: object, request: Mapping[str, Any], *, deadline: float):
        frames = _valid_case_worker_frames(request, cases)
        partial = _worker_frames_bytes(frames[:2]) + b'{"truncated"'
        return partial, True, False, False

    rows, lifecycle, provenance = _call_supervised_case_worker(
        monkeypatch,
        protocol=protocol,
        manifest=manifest,
        communicate=communicate,
    )
    _assert_supervisor_failure_complete(
        rows,
        lifecycle,
        expected_status="time_budget_exhausted",
        expected_error_code="runner_time_budget_exhausted",
    )
    assert provenance["timed_out"] is True
    assert provenance["parsed_prefix_frame_count"] == 2
    assert provenance["discarded_payload_frame_count"] == 1
    assert provenance["accepted_payload_frame_count"] == 0
    assert provenance["discarded_suffix_byte_count"] == len(b'{"truncated"')
    assert provenance["raw_partial_not_independently_replayable"] is True


def test_incomplete_worker_provenance_records_exact_output_cap_overflow(
    monkeypatch: pytest.MonkeyPatch,
    frozen_worker_matrix: tuple[
        Any,
        dict[str, Any],
        tuple[module.ReferenceValidationCaseObservation, ...],
    ],
) -> None:
    protocol, manifest, _cases = frozen_worker_matrix
    monkeypatch.setattr(module, "REFERENCE_VALIDATION_CASE_WORKER_MAX_OUTPUT_BYTES", 64)

    def communicate(process: object, request: Mapping[str, Any], *, deadline: float):
        return b"x" * 64, False, False, True

    rows, lifecycle, provenance = _call_supervised_case_worker(
        monkeypatch,
        protocol=protocol,
        manifest=manifest,
        communicate=communicate,
    )
    _assert_supervisor_failure_complete(
        rows,
        lifecycle,
        expected_status="unexpected_error",
        expected_error_code="case_worker_protocol_invalid",
    )
    assert provenance["output_overflow"] is True
    assert provenance["transcript_byte_count"] == 64
    assert provenance["accepted_payload_frame_count"] == 0
    assert provenance["failure_stage"] == "worker_output_overflow"
