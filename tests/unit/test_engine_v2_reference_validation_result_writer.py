from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from betelgeuze_engine_v2.physics.reference_validation_run_start import (
    reference_validation_artifact_output_root_identity_sha256,
)
from betelgeuze_engine_v2.physics.reference_validation_runner import (
    REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
    REFERENCE_VALIDATION_RUNNER_MAX_CASES,
    REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
    ReferenceValidationRunnerError,
    reference_validation_runner_source_sha256,
    require_reference_validation_run_observation_document,
    run_bounded_cpu_reference_validation,
)
from betelgeuze_engine_v2.physics.reference_validation_result_writer import (
    FROZEN_REFERENCE_VALIDATION_RESULT_WRITER_CONTRACT_SHA256,
    REFERENCE_VALIDATION_RESULT_WRITER_CONTRACT_SCHEMA_ID,
    ReferenceValidationResultReceiptAlreadyExistsError,
    ReferenceValidationResultWriterError,
    read_reference_validation_result_receipt,
    reference_validation_result_writer_contract_decision,
    reference_validation_result_writer_contract_document,
    require_reference_validation_result_writer_contract_document,
    verify_reference_validation_result_receipt,
    write_reference_validation_result_receipt,
)
import betelgeuze_engine_v2.physics.reference_validation_result_writer as module
import betelgeuze_engine_v2.physics.reference_validation_runner as runner_module
import betelgeuze_engine_v2.physics.validation_native_runtime_identity as native_identity


RUN_NOW = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
FINAL_NOW = RUN_NOW + timedelta(minutes=1)
REVIEWED_AT = RUN_NOW - timedelta(hours=1)
AUTHORIZATION_NONCE = "e" * 64
ENVIRONMENT_RECEIPT_SHA256 = "1" * 64
ENVIRONMENT_FINGERPRINT_SHA256 = "2" * 64
AUTHORIZATION_RECEIPT_SHA256 = "3" * 64
CODE_COMMIT_SHA = "4" * 40
SOURCE_MANIFEST_SHA256 = "f" * 64
REVIEW_ATTESTATION_SHA256 = "5" * 64
AUTHOR_IDENTITY_SHA256 = "6" * 64
REVIEWER_IDENTITY_SHA256 = "7" * 64
OPERATOR_IDENTITY_SHA256 = "8" * 64
DEPENDENCY_ROWS = {
    "cryptography-distribution": "9" * 64,
    "numpy-distribution": "a" * 64,
    "openssl-executable": "b" * 64,
    "python-runtime-executable": "c" * 64,
    "python-standard-library": "d" * 64,
    "torch-distribution": "e" * 64,
}
RAW_REVIEW = {"raw_signed_review": True}
RAW_AUTHORIZATION = {"raw_signed_authorization": True}


def _synthetic_native_runtime_snapshot() -> dict[str, object]:
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
    return {
        **projection,
        "snapshot_sha256": runner_module._sha256(projection),
    }


def _worker_request(
    *,
    worker_kind: str,
    environment: SimpleNamespace,
    materialization_manifest_sha256: str | None,
    runner_start_record_sha256: str | None,
) -> dict[str, object]:
    worker_environment = runner_module._case_worker_environment(
        environment.environment_variable_rows,
        dependency_python_path="/trusted",
    )
    return runner_module._fixed_worker_request(
        worker_kind=worker_kind,
        expected_materialization_manifest_sha256=materialization_manifest_sha256,
        expected_code_commit_sha=environment.code_commit_sha,
        expected_runner_source_sha256=environment.runner_source_sha256,
        expected_source_manifest_sha256=environment.source_manifest_sha256,
        expected_authorization_nonce_sha256=environment.authorization_nonce_sha256,
        expected_runner_start_record_sha256=runner_start_record_sha256,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        dependency_roots=(Path("/trusted"),),
        environment_receipt=environment,
        worker_environment=worker_environment,
    )


def _worker_transcript(
    *,
    worker_kind: str,
    request: dict[str, object],
    lifecycle: dict[str, object],
    payload_rows: list[dict[str, object]],
) -> bytes:
    request_sha256 = runner_module._worker_request_sha256(request)
    frames = [
        runner_module._worker_frame(
            frame_type="pre",
            worker_kind=worker_kind,
            worker_request_sha256=request_sha256,
            payload=lifecycle["pre"],
        ),
        *[
            runner_module._worker_frame(
                frame_type="payload",
                worker_kind=worker_kind,
                worker_request_sha256=request_sha256,
                payload=row,
                ordinal=ordinal,
            )
            for ordinal, row in enumerate(payload_rows)
        ],
        runner_module._worker_frame(
            frame_type="completion",
            worker_kind=worker_kind,
            worker_request_sha256=request_sha256,
            payload=lifecycle,
        ),
    ]
    return b"".join(runner_module._canonical_bytes(row) + b"\n" for row in frames)


def _complete_manifest_supervised_result(environment: SimpleNamespace):
    protocol, manifest = runner_module._load_frozen_case_manifest_document()
    request = _worker_request(
        worker_kind="manifest",
        environment=environment,
        materialization_manifest_sha256=None,
        runner_start_record_sha256=None,
    )
    request_sha256 = runner_module._worker_request_sha256(request)
    snapshot = _synthetic_native_runtime_snapshot()
    pre_evidence = native_identity.build_worker_runtime_pre_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    payload_rows = [runner_module._manifest_worker_payload(manifest)]
    lifecycle = native_identity.build_complete_worker_runtime_lifecycle_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=request_sha256,
        pre_evidence=pre_evidence,
        payload_rows=payload_rows,
        post_snapshot=snapshot,
    )
    transcript = _worker_transcript(
        worker_kind="manifest",
        request=request,
        lifecycle=lifecycle,
        payload_rows=payload_rows,
    )
    provenance = runner_module._build_worker_execution_provenance(
        worker_kind="manifest",
        request=request,
        supervisor_launched_child_process_id=1,
        transcript=transcript,
        lifecycle=lifecycle,
        accepted_payload_rows=payload_rows,
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


def _complete_case_supervised_result(
    protocol: object,
    manifest_cases: object,
    *,
    deadline: float,
    environment: SimpleNamespace,
    runner_start_record_sha256: str,
):
    rows = runner_module._run_case_matrix_in_process(
        protocol,
        manifest_cases,
        deadline=deadline,
    )
    _, manifest = runner_module._load_frozen_case_manifest_document()
    request = _worker_request(
        worker_kind="case",
        environment=environment,
        materialization_manifest_sha256=manifest["materialization_manifest_sha256"],
        runner_start_record_sha256=runner_start_record_sha256,
    )
    request_sha256 = runner_module._worker_request_sha256(request)
    snapshot = _synthetic_native_runtime_snapshot()
    pre_evidence = native_identity.build_worker_runtime_pre_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    lifecycle = native_identity.build_complete_worker_runtime_lifecycle_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE,
        worker_request_sha256=request_sha256,
        pre_evidence=pre_evidence,
        payload_rows=[row.to_dict() for row in rows],
        post_snapshot=snapshot,
    )
    payload_rows = [row.to_dict() for row in rows]
    transcript = _worker_transcript(
        worker_kind="case",
        request=request,
        lifecycle=lifecycle,
        payload_rows=payload_rows,
    )
    provenance = runner_module._build_worker_execution_provenance(
        worker_kind="case",
        request=request,
        supervisor_launched_child_process_id=1,
        transcript=transcript,
        lifecycle=lifecycle,
        accepted_payload_rows=payload_rows,
        failure_stage=None,
        child_exit_code=0,
        timed_out=False,
        output_overflow=False,
        communication_failed=False,
        request_fully_written=True,
    )
    return rows, lifecycle, provenance


def _environment_rows() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            {
                runner_module.REFERENCE_VALIDATION_APPLICATION_SEED_ENV: "456",
                "CUDA_VISIBLE_DEVICES": "",
                "HIP_VISIBLE_DEVICES": "",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "MKL_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "123",
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


def _environment(root: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "started_at_utc": RUN_NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "receipt_sha256": ENVIRONMENT_RECEIPT_SHA256,
        "environment_fingerprint_sha256": ENVIRONMENT_FINGERPRINT_SHA256,
        "authorization_receipt_sha256": AUTHORIZATION_RECEIPT_SHA256,
        "review_attestation_sha256": REVIEW_ATTESTATION_SHA256,
        "implementation_author_identity_sha256": AUTHOR_IDENTITY_SHA256,
        "independent_reviewer_identity_sha256": REVIEWER_IDENTITY_SHA256,
        "authorization_operator_identity_sha256": OPERATOR_IDENTITY_SHA256,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "code_commit_sha": CODE_COMMIT_SHA,
        "runner_source_sha256": reference_validation_runner_source_sha256(),
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "dependency_artifact_sha256_rows": tuple(sorted(DEPENDENCY_ROWS.items())),
        "environment_variable_rows": _environment_rows(),
        "python_hash_seed": 123,
        "application_seed": 456,
        "command_argv": REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
        "artifact_output_root_identity_sha256": (
            reference_validation_artifact_output_root_identity_sha256(root)
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _observation(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    environment: SimpleNamespace | None = None,
    worker_failure_code: str | None = None,
):
    selected = environment or _environment(root)
    monkeypatch.setattr(runner_module, "_utc_now", lambda: RUN_NOW)
    monkeypatch.setattr(
        runner_module,
        "require_reference_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: selected,
    )
    monkeypatch.setattr(
        runner_module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: selected.code_commit_sha,
    )
    monkeypatch.setattr(
        runner_module,
        "_require_clean_checked_out_code_commit",
        lambda _expected_commit: None,
    )
    monkeypatch.setattr(
        runner_module,
        "_require_isolated_python_bootstrap_runtime",
        lambda **_kwargs: (Path("/trusted"),),
    )
    monkeypatch.setattr(
        runner_module,
        "_observe_dependency_artifact_sha256_rows",
        lambda _roots, **kwargs: dict(DEPENDENCY_ROWS),
    )
    monkeypatch.setattr(
        runner_module,
        "_require_source_only_python_runtime",
        lambda: None,
    )

    def run_in_process(
        protocol: object,
        manifest_cases: object,
        **kwargs: object,
    ):
        request = _worker_request(
            worker_kind="case",
            environment=selected,
            materialization_manifest_sha256=kwargs["materialization_manifest_sha256"],
            runner_start_record_sha256=kwargs["expected_runner_start_record_sha256"],
        )
        if worker_failure_code is not None:
            return runner_module._incomplete_case_worker_result(
                protocol,
                manifest_cases,
                request=request,
                failure_code=worker_failure_code,
                observed_status="unexpected_error",
                pre_evidence=None,
                supervisor_launched_child_process_id=1,
                transcript=b"",
                failure_stage="worker_exit",
                child_exit_code=2,
                timed_out=False,
                output_overflow=False,
                communication_failed=False,
                request_fully_written=True,
            )
        return _complete_case_supervised_result(
            protocol,
            manifest_cases,
            deadline=kwargs["deadline"],
            environment=selected,
            runner_start_record_sha256=kwargs["expected_runner_start_record_sha256"],
        )

    monkeypatch.setattr(
        runner_module,
        "_run_supervised_case_matrix",
        run_in_process,
    )
    monkeypatch.setattr(
        runner_module,
        "_run_supervised_frozen_case_matrix",
        lambda **_kwargs: _complete_manifest_supervised_result(selected),
    )
    return run_bounded_cpu_reference_validation(
        root,
        AUTHORIZATION_NONCE,
        expected_environment_receipt_sha256=ENVIRONMENT_RECEIPT_SHA256,
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
    )


def _review(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "attestation_sha256": REVIEW_ATTESTATION_SHA256,
        "implementation_author_identity_sha256": AUTHOR_IDENTITY_SHA256,
        "independent_reviewer_identity_sha256": REVIEWER_IDENTITY_SHA256,
        "reviewed_at_utc": REVIEWED_AT.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _authorization(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "receipt_sha256": AUTHORIZATION_RECEIPT_SHA256,
        "review_attestation_sha256": REVIEW_ATTESTATION_SHA256,
        "implementation_author_identity_sha256": AUTHOR_IDENTITY_SHA256,
        "independent_reviewer_identity_sha256": REVIEWER_IDENTITY_SHA256,
        "authorization_operator_identity_sha256": OPERATOR_IDENTITY_SHA256,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "code_commit_sha": CODE_COMMIT_SHA,
        "runner_source_sha256": reference_validation_runner_source_sha256(),
        "dependency_artifact_sha256_rows": tuple(sorted(DEPENDENCY_ROWS.items())),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _install_verified_chain(
    monkeypatch: pytest.MonkeyPatch,
    environment: SimpleNamespace,
    *,
    review: SimpleNamespace | None = None,
    authorization: SimpleNamespace | None = None,
    seen: dict[str, object] | None = None,
) -> None:
    selected_review = review or _review()
    selected_authorization = authorization or _authorization()
    monkeypatch.setattr(module, "_utc_now", lambda: FINAL_NOW)

    def verify_review(raw: object, **kwargs: object) -> SimpleNamespace:
        if seen is not None:
            seen["review_raw"] = raw
            seen["review_kwargs"] = kwargs
        return selected_review

    def verify_authorization(raw: object, **kwargs: object) -> SimpleNamespace:
        if seen is not None:
            seen["authorization_raw"] = raw
            seen["authorization_kwargs"] = kwargs
        return selected_authorization

    monkeypatch.setattr(
        module,
        "verify_signed_reference_validation_review_attestation",
        verify_review,
    )
    monkeypatch.setattr(
        module,
        "verify_signed_reference_validation_authorization_receipt",
        verify_authorization,
    )
    monkeypatch.setattr(
        module,
        "require_reference_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: environment,
    )


def _write(root: Path, observation: object):
    return write_reference_validation_result_receipt(
        root,
        AUTHORIZATION_NONCE,
        observation,  # type: ignore[arg-type]
        review_attestation=RAW_REVIEW,
        authorization_receipt=RAW_AUTHORIZATION,
        trusted_reviewer_keys={},
        expected_implementation_author_identity_sha256=(AUTHOR_IDENTITY_SHA256),
        trusted_operator_keys={},
        revoked_authorization_receipt_sha256s=("c" * 64,),
        revoked_review_attestation_sha256s=("d" * 64,),
        externally_conflicting_nonce_sha256s=("f" * 64,),
    )


def test_result_writer_contract_is_frozen_and_current_decision_is_closed() -> None:
    first = reference_validation_result_writer_contract_document()
    second = reference_validation_result_writer_contract_document()
    decision = reference_validation_result_writer_contract_decision()

    assert first == second
    assert first["schema_id"] == REFERENCE_VALIDATION_RESULT_WRITER_CONTRACT_SCHEMA_ID
    assert first["frozen_at_utc"] == "2026-07-22T12:00:00Z"
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_RESULT_WRITER_CONTRACT_SHA256
    )
    assert first["coverage"]["case_count"] == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert first["coverage"]["variant_count"] == (
        REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    )
    assert first["coverage"]["failed_cases_variants_and_metrics_retained"] is True
    assert first["verification"]["receipt_signature_implemented"] is False
    assert (
        first["verification"][
            "worker_request_environment_cross_checked_against_persisted_receipt_and_live_process"
        ]
        is True
    )
    assert (
        first["verification"][
            "manifest_worker_lifecycle_reverified_against_frozen_manifest"
        ]
        is True
    )
    assert (
        first["verification"][
            "case_worker_lifecycle_reverified_against_exact_receipt_case_rows"
        ]
        is True
    )
    assert (
        first["verification"][
            "retained_case_payload_aggregate_recomputed_from_exact_case_rows"
        ]
        is True
    )
    assert (
        first["verification"]["native_mapping_lifetime_closure_claim_remains_false"]
        is True
    )
    assert (
        first["coverage"][
            "incomplete_worker_lifecycle_eligible_for_accepted_result_review"
        ]
        is False
    )
    assert first["claim_policy"]["claim_safe"] is False
    assert require_reference_validation_result_writer_contract_document(first) == first

    assert decision["result_receipt_writer_implemented"] is True
    assert decision["production_result_receipt_present"] is False
    assert decision["production_validation_results_collected"] is False
    assert decision["independent_result_review_complete"] is False
    assert (
        "worker_request_observation_identity_binding_missing"
        not in decision["blockers"]
    )
    assert "external_worker_launch_identity_not_established" in decision["blockers"]
    assert decision["parameter_fitting_authorized"] is False
    assert decision["claim_safe"] is False


def test_result_writer_contract_rejects_tamper() -> None:
    tampered = deepcopy(reference_validation_result_writer_contract_document())
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="does not match the frozen record",
    ):
        require_reference_validation_result_writer_contract_document(tampered)


def test_writer_reverifies_chain_and_persists_every_failure_in_one_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    seen: dict[str, object] = {}
    _install_verified_chain(monkeypatch, environment, seen=seen)

    receipt = _write(root, observation)
    payload = receipt.to_dict()
    result_path = root / f"{AUTHORIZATION_NONCE}.result.json"

    assert seen["review_raw"] == RAW_REVIEW
    assert seen["authorization_raw"] == RAW_AUTHORIZATION
    authorization_kwargs = seen["authorization_kwargs"]
    assert isinstance(authorization_kwargs, dict)
    assert authorization_kwargs["revoked_receipt_sha256s"] == ("c" * 64,)
    assert authorization_kwargs["revoked_review_attestation_sha256s"] == ("d" * 64,)
    assert authorization_kwargs["consumed_nonce_sha256s"] == ("f" * 64,)

    assert result_path.is_file()
    assert stat.S_IMODE(result_path.stat().st_mode) == 0o600
    assert result_path.stat().st_nlink == 1
    assert sorted(path.name for path in root.iterdir()) == [
        f"{AUTHORIZATION_NONCE}.result.json",
        f"{AUTHORIZATION_NONCE}.runner-start.json",
    ]
    assert payload["run_observation"] == observation.to_dict()
    assert payload["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256
    assert (
        payload["run_observation"]["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256
    )
    assert (
        payload["run_observation"]["manifest_worker_lifecycle_evidence"][
            "completion_state"
        ]
        == "complete"
    )
    assert (
        payload["run_observation"]["case_worker_lifecycle_evidence"]["completion_state"]
        == "complete"
    )
    assert payload["run_observation"][
        "retained_case_payload_aggregate_sha256"
    ] == runner_module._sha256(payload["case_results"])
    assert payload["case_results"] == observation.to_dict()["case_results"]
    assert payload["coverage_summary"] == {
        **observation.to_dict()["coverage_summary"],
    }
    assert len(payload["case_results"]) == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert sum(len(row["variant_results"]) for row in payload["case_results"]) == (
        REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    )
    assert any(not row["case_passed"] for row in payload["case_results"])
    assert any(
        not metric["passed"]
        for row in payload["case_results"]
        for metric in row["metric_values"]
    )
    assert payload["independent_result_review_state"] == "pending_independent_review"
    assert payload["review_scope"] == (
        "implementation_and_artifact_review_pre_execution"
    )
    assert payload["validation_results_collected"] is True
    assert payload["production_validation_results_collected"] is False
    assert payload["parameter_fitting_authorized"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert payload["artifact_path_confinement_verification"]["path_disclosed"] is False
    assert (
        payload["artifact_path_confinement_verification"][
            "same_uid_replacement_resistance_established"
        ]
        is False
    )
    assert "test-only-32-bytes" not in json.dumps(payload, sort_keys=True)

    assert (
        read_reference_validation_result_receipt(root, AUTHORIZATION_NONCE) == receipt
    )
    assert (
        verify_reference_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256=receipt.receipt_sha256,
            revoked_review_attestation_sha256s=(),
            revoked_authorization_receipt_sha256s=(),
            revoked_result_receipt_sha256s=(),
            superseded_result_receipt_sha256s=(),
        )
        == receipt
    )
    assert (
        require_reference_validation_run_observation_document(
            payload["run_observation"]
        )
        == observation
    )

    with pytest.raises(ReferenceValidationResultReceiptAlreadyExistsError):
        _write(root, observation)


def test_incomplete_worker_lifecycle_is_retained_but_never_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(
        root,
        monkeypatch,
        environment=environment,
        worker_failure_code="case_worker_nonzero_exit",
    )
    _install_verified_chain(monkeypatch, environment)

    receipt = _write(root, observation)
    payload = receipt.to_dict()
    run_document = payload["run_observation"]
    lifecycle = run_document["case_worker_lifecycle_evidence"]
    provenance = run_document["case_worker_execution_provenance"]
    assert lifecycle["completion_state"] == "incomplete"
    assert lifecycle["failure_code"] == "case_worker_nonzero_exit"
    assert lifecycle["payload"] is None
    assert lifecycle["post"] is None
    assert provenance["completion_state"] == "incomplete"
    assert provenance["partial_worker_payload_accepted"] is False
    assert provenance["accepted_payload_frame_count"] == 0
    assert provenance["raw_partial_not_independently_replayable"] is True
    assert all(
        row["observation_origin"] == "supervisor"
        and row["case_passed"] is False
        and row["observed_error_code"] == "case_worker_nonzero_exit"
        for row in payload["case_results"]
    )
    assert payload["independent_result_review_state"] == "pending_independent_review"
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False

    tampered = deepcopy(payload)
    tampered["independent_result_review_state"] = "accepted"
    unsigned = dict(tampered)
    unsigned.pop("receipt_sha256")
    tampered["receipt_sha256"] = module._sha256(unsigned)
    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="constants or claim boundary drifted",
    ):
        module._validate_result_receipt_payload(tampered)


@pytest.mark.parametrize(
    "tamper_target",
    (
        "manifest_worker_lifecycle_evidence_bytes",
        "case_worker_lifecycle_evidence_bytes",
        "manifest_worker_execution_provenance_bytes",
        "case_worker_execution_provenance_bytes",
        "retained_case_payload_aggregate_sha256",
    ),
)
def test_writer_directly_revalidates_worker_lifecycles_and_retained_aggregate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper_target: str,
) -> None:
    root = _private_root(tmp_path)
    observation = _observation(root, monkeypatch, environment=_environment(root))
    tampered = deepcopy(observation)
    if tamper_target == "retained_case_payload_aggregate_sha256":
        object.__setattr__(tampered, tamper_target, "0" * 64)
        message = "retained case payload aggregate is cross-wired"
    elif "lifecycle" in tamper_target:
        lifecycle = json.loads(getattr(tampered, tamper_target).decode("ascii"))
        lifecycle["lifecycle_sha256"] = "0" * 64
        object.__setattr__(
            tampered,
            tamper_target,
            runner_module._canonical_bytes(lifecycle),
        )
        message = "worker execution provenance is invalid"
    else:
        provenance = json.loads(getattr(tampered, tamper_target).decode("ascii"))
        provenance["transcript_sha256"] = "0" * 64
        unsigned = dict(provenance)
        unsigned.pop("provenance_sha256")
        provenance["provenance_sha256"] = runner_module._sha256(unsigned)
        object.__setattr__(
            tampered,
            tamper_target,
            runner_module._canonical_bytes(provenance),
        )
        message = "worker execution provenance is invalid"

    with pytest.raises(ReferenceValidationResultWriterError, match=message):
        module._require_worker_execution_receipt_binding(tampered)


def test_writer_directly_rejects_worker_provenance_transplanted_to_outer_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    observation = _observation(root, monkeypatch, environment=_environment(root))
    tampered = deepcopy(observation)
    object.__setattr__(tampered, "environment_fingerprint_sha256", "0" * 64)

    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="worker execution provenance is invalid",
    ):
        module._require_worker_execution_receipt_binding(tampered)


def test_writer_rejects_self_consistent_worker_environment_forge_against_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    forged = deepcopy(observation)
    run_document = observation.to_dict()
    original_provenance = run_document["manifest_worker_execution_provenance"]
    request_bytes = bytes.fromhex(
        original_provenance["worker_request_canonical_jsonl_hex"]
    )
    request = runner_module._load_case_worker_request(request_bytes)
    request["expected_python_hash_seed"] = 124
    forged_environment = dict(request["expected_worker_environment"])
    forged_environment["PYTHONHASHSEED"] = "124"
    forged_environment["PYTHONPATH"] = "/forged"
    request["dependency_roots"] = ["/forged"]
    request["expected_worker_environment"] = forged_environment
    request["expected_worker_environment_sha256"] = runner_module._sha256(
        forged_environment
    )
    request["expected_python_hash_probe_sha256"] = "f" * 64
    request_sha256 = runner_module._worker_request_sha256(request)
    snapshot = run_document["manifest_worker_lifecycle_evidence"]["pre"]["snapshot"]
    pre_evidence = native_identity.build_worker_runtime_pre_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    _, manifest = runner_module._load_frozen_case_manifest_document()
    payload_rows = [runner_module._manifest_worker_payload(manifest)]
    lifecycle = native_identity.build_complete_worker_runtime_lifecycle_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
        worker_request_sha256=request_sha256,
        pre_evidence=pre_evidence,
        payload_rows=payload_rows,
        post_snapshot=snapshot,
    )
    transcript = _worker_transcript(
        worker_kind="manifest",
        request=request,
        lifecycle=lifecycle,
        payload_rows=payload_rows,
    )
    provenance = runner_module._build_worker_execution_provenance(
        worker_kind="manifest",
        request=request,
        supervisor_launched_child_process_id=original_provenance[
            "supervisor_launched_child_process_id"
        ],
        transcript=transcript,
        lifecycle=lifecycle,
        accepted_payload_rows=payload_rows,
        failure_stage=None,
        child_exit_code=0,
        timed_out=False,
        output_overflow=False,
        communication_failed=False,
        request_fully_written=True,
    )
    object.__setattr__(
        forged,
        "manifest_worker_lifecycle_evidence_bytes",
        runner_module._lifecycle_evidence_bytes(
            lifecycle,
            name="manifest-worker lifecycle evidence",
        ),
    )
    object.__setattr__(
        forged,
        "manifest_worker_execution_provenance_bytes",
        runner_module._worker_execution_provenance_bytes(
            provenance,
            name="manifest-worker execution provenance",
        ),
    )

    assert (
        require_reference_validation_run_observation_document(forged.to_dict())
        == forged
    )
    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="worker execution provenance is invalid",
    ):
        module._require_worker_execution_receipt_binding(
            forged,
            environment=environment,
        )


@pytest.mark.parametrize(
    ("review", "authorization", "environment_overrides", "message"),
    [
        (
            _review(attestation_sha256="0" * 64),
            None,
            {},
            "authorization and observation are cross-wired",
        ),
        (
            None,
            _authorization(receipt_sha256="0" * 64),
            {},
            "authorization and observation are cross-wired",
        ),
        (
            None,
            None,
            {"environment_fingerprint_sha256": "0" * 64},
            "environment and observation are cross-wired",
        ),
        (
            None,
            None,
            {"source_manifest_sha256": "0" * 64},
            "environment and observation are cross-wired",
        ),
    ],
)
def test_writer_rejects_crosswired_chain_before_result_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    review: SimpleNamespace | None,
    authorization: SimpleNamespace | None,
    environment_overrides: dict[str, object],
    message: str,
) -> None:
    root = _private_root(tmp_path)
    run_environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=run_environment)
    finalize_environment = _environment(root, **environment_overrides)
    _install_verified_chain(
        monkeypatch,
        finalize_environment,
        review=review,
        authorization=authorization,
    )

    with pytest.raises(ReferenceValidationResultWriterError, match=message):
        _write(root, observation)
    assert not (root / f"{AUTHORIZATION_NONCE}.result.json").exists()


def test_writer_rejects_tampered_runner_start_and_observation_before_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    _install_verified_chain(monkeypatch, environment)
    start_path = root / f"{AUTHORIZATION_NONCE}.runner-start.json"
    start = json.loads(start_path.read_text(encoding="ascii"))
    start["started_at_utc"] = (RUN_NOW - timedelta(seconds=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    unsigned_start = dict(start)
    unsigned_start.pop("runner_start_record_sha256")
    start["runner_start_record_sha256"] = hashlib.sha256(
        json.dumps(
            unsigned_start,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    start_path.write_text(
        json.dumps(start, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    object.__setattr__(
        observation,
        "runner_start_record_sha256",
        start["runner_start_record_sha256"],
    )

    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="run observation verification failed",
    ):
        _write(root, observation)
    assert not (root / f"{AUTHORIZATION_NONCE}.result.json").exists()

    object.__setattr__(
        observation,
        "blockers",
        ("scientific_validation_missing",),
    )
    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="run observation verification failed",
    ):
        _write(root, observation)


def test_writer_rejects_passing_case_with_failed_retained_metric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    payload = observation.to_dict()
    contradictory = next(
        row
        for row in payload["case_results"]
        if row["metric_values"]
        and any(not metric["passed"] for metric in row["metric_values"])
    )
    contradictory["observed_status"] = "metrics_passed"
    contradictory["observed_error_code"] = None
    contradictory["case_passed"] = True

    with pytest.raises(
        ReferenceValidationRunnerError,
        match="status or error contradicts",
    ):
        require_reference_validation_run_observation_document(payload)


def test_writer_refuses_a_preexisting_result_symlink_without_touching_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    _install_verified_chain(monkeypatch, environment)
    target = tmp_path / "outside-result.json"
    target.write_text("unchanged", encoding="ascii")
    result_path = root / f"{AUTHORIZATION_NONCE}.result.json"
    result_path.symlink_to(target)

    with pytest.raises(ReferenceValidationResultReceiptAlreadyExistsError):
        _write(root, observation)
    assert result_path.is_symlink()
    assert target.read_text(encoding="ascii") == "unchanged"


def test_result_reader_rejects_tamper_mode_hardlink_and_external_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    _install_verified_chain(monkeypatch, environment)
    receipt = _write(root, observation)
    path = root / f"{AUTHORIZATION_NONCE}.result.json"
    original = path.read_bytes()

    payload = json.loads(original.decode("ascii"))
    payload["claim_safe"] = True
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    with pytest.raises(ReferenceValidationResultWriterError, match="SHA-256"):
        read_reference_validation_result_receipt(root, AUTHORIZATION_NONCE)

    path.write_bytes(original)
    path.chmod(0o644)
    with pytest.raises(ReferenceValidationResultWriterError, match="securely"):
        read_reference_validation_result_receipt(root, AUTHORIZATION_NONCE)

    path.chmod(0o600)
    hardlink = tmp_path / "result-hardlink.json"
    try:
        os.link(path, hardlink)
    except OSError:
        pytest.skip("hard links unavailable")
    with pytest.raises(ReferenceValidationResultWriterError, match="securely"):
        read_reference_validation_result_receipt(root, AUTHORIZATION_NONCE)
    hardlink.unlink()

    with pytest.raises(ReferenceValidationResultWriterError, match="cross-wired"):
        verify_reference_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256="0" * 64,
            revoked_review_attestation_sha256s=(),
            revoked_authorization_receipt_sha256s=(),
            revoked_result_receipt_sha256s=(),
            superseded_result_receipt_sha256s=(),
        )
    with pytest.raises(ReferenceValidationResultWriterError, match="revoked"):
        verify_reference_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256=receipt.receipt_sha256,
            revoked_review_attestation_sha256s=(),
            revoked_authorization_receipt_sha256s=(),
            revoked_result_receipt_sha256s=(receipt.receipt_sha256,),
            superseded_result_receipt_sha256s=(),
        )
    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="review attestation is externally revoked",
    ):
        verify_reference_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256=receipt.receipt_sha256,
            revoked_review_attestation_sha256s=(REVIEW_ATTESTATION_SHA256,),
            revoked_authorization_receipt_sha256s=(),
            revoked_result_receipt_sha256s=(),
            superseded_result_receipt_sha256s=(),
        )
    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="authorization is externally revoked",
    ):
        verify_reference_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256=receipt.receipt_sha256,
            revoked_review_attestation_sha256s=(),
            revoked_authorization_receipt_sha256s=(AUTHORIZATION_RECEIPT_SHA256,),
            revoked_result_receipt_sha256s=(),
            superseded_result_receipt_sha256s=(),
        )
    with pytest.raises(ReferenceValidationResultWriterError, match="superseded"):
        verify_reference_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256=receipt.receipt_sha256,
            revoked_review_attestation_sha256s=(),
            revoked_authorization_receipt_sha256s=(),
            revoked_result_receipt_sha256s=(),
            superseded_result_receipt_sha256s=(receipt.receipt_sha256,),
        )


def test_result_reader_binds_filename_nonce_and_opens_special_files_nonblocking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    _install_verified_chain(monkeypatch, environment)
    _write(root, observation)
    original = root / f"{AUTHORIZATION_NONCE}.result.json"
    other_nonce = "0" * 64
    copied = root / f"{other_nonce}.result.json"
    copied.write_bytes(original.read_bytes())
    copied.chmod(0o600)

    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="authorization nonce is cross-wired",
    ):
        read_reference_validation_result_receipt(root, other_nonce)

    copied.unlink()
    os.mkfifo(copied, mode=0o600)
    with pytest.raises(
        ReferenceValidationResultWriterError,
        match="cannot be read securely",
    ):
        read_reference_validation_result_receipt(root, other_nonce)


def test_writer_public_surface_has_no_clock_delete_release_signature_or_cli() -> None:
    signature = inspect.signature(write_reference_validation_result_receipt)
    assert "checked_at" not in signature.parameters
    for name in (
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
    ):
        assert signature.parameters[name].default is inspect.Parameter.empty
    verify_signature = inspect.signature(verify_reference_validation_result_receipt)
    for name in (
        "expected_receipt_sha256",
        "revoked_review_attestation_sha256s",
        "revoked_authorization_receipt_sha256s",
        "revoked_result_receipt_sha256s",
        "superseded_result_receipt_sha256s",
    ):
        assert verify_signature.parameters[name].default is inspect.Parameter.empty
    public = set(module.__all__)
    assert not any(name.startswith("delete_") for name in public)
    assert not any(name.startswith("release_") for name in public)
    assert not any(name.startswith("build_signed") for name in public)
    assert "main" not in public

    source = inspect.getsource(module)
    tree = ast.parse(source)
    top_level_imports = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    imported_modules = {
        alias.name.split(".", 1)[0]
        for node in top_level_imports
        for alias in node.names
        if isinstance(node, ast.Import)
    }
    assert "subprocess" not in imported_modules
    assert "socket" not in imported_modules
    assert "requests" not in imported_modules
