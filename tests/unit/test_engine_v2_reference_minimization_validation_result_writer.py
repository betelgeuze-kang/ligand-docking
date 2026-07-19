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

from betelgeuze_engine_v2.physics.reference_minimization_validation_run_start import (
    reference_minimization_validation_artifact_output_root_identity_sha256,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_runner import (
    REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV,
    REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES,
    ReferenceMinimizationValidationRunnerError,
    reference_minimization_validation_runner_source_sha256,
    require_reference_minimization_validation_run_observation_document,
    run_bounded_cpu_reference_minimization_validation,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_result_writer import (
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256_V4,
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256_V3,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SCHEMA_ID,
    ReferenceMinimizationValidationResultReceiptAlreadyExistsError,
    ReferenceMinimizationValidationResultWriterError,
    read_reference_minimization_validation_result_receipt,
    reference_minimization_validation_result_writer_contract_decision,
    reference_minimization_validation_result_writer_contract_document,
    require_reference_minimization_validation_result_writer_contract_document,
    verify_reference_minimization_validation_result_receipt,
    write_reference_minimization_validation_result_receipt,
)
import betelgeuze_engine_v2.physics.reference_minimization_validation_result_writer as module
import betelgeuze_engine_v2.physics.reference_minimization_validation_runner as runner_module
import betelgeuze_engine_v2.physics.validation_native_runtime_identity as native_identity


RUN_NOW = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
FINAL_NOW = RUN_NOW + timedelta(minutes=1)
REVIEWED_AT = RUN_NOW - timedelta(hours=1)
AUTHORIZATION_NONCE = "e" * 64
ENVIRONMENT_RECEIPT_SHA256 = "1" * 64
ENVIRONMENT_FINGERPRINT_SHA256 = "2" * 64
SOURCE_MANIFEST_SHA256 = "0" * 64
AUTHORIZATION_RECEIPT_SHA256 = "3" * 64
CODE_COMMIT_SHA = "4" * 40
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


def _complete_supervised_matrix_result(
    *,
    deadline: object,
    worker_preflight_request: object,
):
    assert isinstance(deadline, float)
    assert isinstance(worker_preflight_request, dict)
    rows = runner_module._run_case_matrix_in_process(deadline=deadline)
    payload_rows = [row.to_dict() for row in rows]
    request_sha256 = runner_module._sha256(worker_preflight_request)
    snapshot = _synthetic_native_runtime_snapshot()
    pre_evidence = native_identity.build_worker_runtime_pre_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    lifecycle = native_identity.build_complete_worker_runtime_lifecycle_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        pre_evidence=pre_evidence,
        payload_rows=payload_rows,
        post_snapshot=snapshot,
    )
    raw = runner_module._reconstruct_complete_matrix_worker_transcript(
        worker_request_sha256=request_sha256,
        case_results=rows,
        runtime_lifecycle_evidence=lifecycle,
    )
    return runner_module._decode_complete_matrix_worker_transcript(
        raw,
        worker_preflight_request=worker_preflight_request,
        supervisor_child_process_id=1,
    )


def _environment_rows() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            {
                runner_module.REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV: "456",
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
        "runner_source_sha256": reference_minimization_validation_runner_source_sha256(),
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "dependency_artifact_sha256_rows": tuple(sorted(DEPENDENCY_ROWS.items())),
        "environment_variable_rows": _environment_rows(),
        "python_hash_seed": 123,
        "application_seed": 456,
        "command_argv": REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV,
        "artifact_output_root_identity_sha256": (
            reference_minimization_validation_artifact_output_root_identity_sha256(root)
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
        "require_reference_minimization_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: selected,
    )
    monkeypatch.setattr(
        runner_module,
        "_require_clean_checked_out_code_commit",
        lambda _expected_commit: None,
    )
    monkeypatch.setattr(
        runner_module,
        "_require_isolated_python_bootstrap_runtime",
        lambda: (Path("/trusted"),),
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

    def run_in_process(**kwargs: object):
        if worker_failure_code is not None:
            return runner_module._supervisor_failure_complete_matrix(
                worker_failure_code,
                worker_preflight_request=kwargs["worker_preflight_request"],
            )
        return _complete_supervised_matrix_result(
            deadline=kwargs["deadline"],
            worker_preflight_request=kwargs["worker_preflight_request"],
        )

    monkeypatch.setattr(
        runner_module,
        "_run_supervised_case_matrix",
        run_in_process,
    )
    return run_bounded_cpu_reference_minimization_validation(
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
        "runner_source_sha256": reference_minimization_validation_runner_source_sha256(),
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
        "verify_signed_reference_minimization_validation_review_attestation",
        verify_review,
    )
    monkeypatch.setattr(
        module,
        "verify_signed_reference_minimization_validation_authorization_receipt",
        verify_authorization,
    )
    monkeypatch.setattr(
        module,
        "require_reference_minimization_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: environment,
    )


def _write(root: Path, observation: object):
    return write_reference_minimization_validation_result_receipt(
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
    first = reference_minimization_validation_result_writer_contract_document()
    second = reference_minimization_validation_result_writer_contract_document()
    decision = reference_minimization_validation_result_writer_contract_decision()

    assert first == second
    assert (
        first["schema_id"]
        == REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SCHEMA_ID
    )
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256
    )
    assert (
        first["coverage"]["case_count"]
        == REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES
    )
    assert first["coverage"]["failed_cases_and_metrics_retained"] is True
    assert first["verification"]["receipt_signature_implemented"] is False
    assert (
        first["verification"][
            "exact_worker_execution_evidence_reverified_by_runner_schema"
        ]
        is True
    )
    assert (
        first["verification"]["retained_case_aggregate_recomputed_from_exact_case_rows"]
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
    assert (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256_V4
        == "76bf29c96ea0d369f10d446fa5e33f6906e1adb3f6b3dba0e3a25cffdd0957c2"
    )
    assert (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_VALIDATION_RESULT_WRITER_CONTRACT_SHA256_V3
        == "a02d29c915fa56a55b22a3109cafd8a95a1397e382c85dbb0c9cacfba8b9694b"
    )
    assert first["claim_policy"]["claim_safe"] is False
    assert (
        require_reference_minimization_validation_result_writer_contract_document(first)
        == first
    )

    assert decision["result_receipt_writer_implemented"] is True
    assert decision["production_result_receipt_present"] is False
    assert decision["production_validation_results_collected"] is False
    assert decision["independent_result_review_complete"] is False
    assert (
        "worker_process_starttime_and_boot_id_binding_missing" in decision["blockers"]
    )
    assert decision["parameter_fitting_authorized"] is False
    assert decision["claim_safe"] is False


def test_result_writer_contract_rejects_tamper() -> None:
    tampered = deepcopy(
        reference_minimization_validation_result_writer_contract_document()
    )
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError,
        match="does not match the frozen record",
    ):
        require_reference_minimization_validation_result_writer_contract_document(
            tampered
        )


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
        f"reference-minimization-validation-runner-start-{AUTHORIZATION_NONCE}.json",
    ]
    assert payload["run_observation"] == observation.to_dict()
    assert payload["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256
    assert payload["case_results"] == observation.to_dict()["case_results"]
    assert payload["coverage_summary"] == {
        **observation.to_dict()["coverage_summary"],
    }
    assert (
        len(payload["case_results"])
        == REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES
    )
    assert any(
        row["observed_status"] == "fail_closed" for row in payload["case_results"]
    )
    assert all(row["case_passed"] for row in payload["case_results"])
    assert all(len(row["coordinate_traces"]) == 2 for row in payload["case_results"])
    assert all(
        trace["trace_length"] == len(trace["steps"])
        and len(trace["trace_sha256"]) == 64
        for row in payload["case_results"]
        for trace in row["coordinate_traces"]
    )
    assert (
        payload["case_results"][12]["coordinate_traces"][1]["rejected_step_count"] > 0
    )
    worker_evidence = payload["run_observation"]["worker_execution_evidence"]
    assert worker_evidence["completion_state"] == "complete"
    assert worker_evidence["failure_code"] is None
    assert len(worker_evidence["case_frame_sha256_rows"]) == 14
    assert worker_evidence["retained_case_aggregate_sha256"] == runner_module._sha256(
        payload["case_results"]
    )
    assert (
        worker_evidence["runtime_lifecycle_evidence"]["completion_state"] == "complete"
    )
    assert worker_evidence["native_pre_post_snapshot_equality_verified"] is True
    assert worker_evidence["native_mapping_lifetime_closure_claimed"] is False
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
            "same_uid_content_mutation_detected_by_out_of_band_sha256"
        ]
        is True
    )
    assert (
        payload["artifact_path_confinement_verification"][
            "same_uid_replacement_resistance_established"
        ]
        is False
    )
    assert "test-only-32-bytes" not in json.dumps(payload, sort_keys=True)

    assert (
        read_reference_minimization_validation_result_receipt(root, AUTHORIZATION_NONCE)
        == receipt
    )
    assert (
        verify_reference_minimization_validation_result_receipt(
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
        require_reference_minimization_validation_run_observation_document(
            payload["run_observation"]
        )
        == observation
    )

    crosswired_trace = deepcopy(payload)
    crosswired_trace["case_results"][0]["coordinate_traces"][0]["trace_sha256"] = (
        "0" * 64
    )
    crosswired_trace.pop("receipt_sha256")
    crosswired_trace["receipt_sha256"] = hashlib.sha256(
        module._canonical_bytes(crosswired_trace)
    ).hexdigest()
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError,
        match="run observation are cross-wired",
    ):
        module._validate_result_receipt_payload(crosswired_trace)

    with pytest.raises(ReferenceMinimizationValidationResultReceiptAlreadyExistsError):
        _write(root, observation)


def test_writer_revalidates_exact_worker_lifecycle_frames_and_retained_aggregate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    _install_verified_chain(monkeypatch, environment)
    payload = _write(root, observation).to_dict()

    def rehash(tampered: dict[str, object]) -> dict[str, object]:
        run_observation = tampered["run_observation"]
        assert isinstance(run_observation, dict)
        tampered["observation_sha256"] = runner_module._sha256(run_observation)
        tampered.pop("receipt_sha256", None)
        tampered["receipt_sha256"] = runner_module._sha256(tampered)
        return tampered

    mutations: list[dict[str, object]] = []

    aggregate_tamper = deepcopy(payload)
    aggregate_evidence = aggregate_tamper["run_observation"][
        "worker_execution_evidence"
    ]
    aggregate_evidence["retained_case_aggregate_sha256"] = "0" * 64
    mutations.append(rehash(aggregate_tamper))

    lifecycle_tamper = deepcopy(payload)
    lifecycle_evidence = lifecycle_tamper["run_observation"][
        "worker_execution_evidence"
    ]
    lifecycle_evidence["runtime_lifecycle_evidence"]["lifecycle_sha256"] = "0" * 64
    mutations.append(rehash(lifecycle_tamper))

    reordered = deepcopy(payload)
    reordered_evidence = reordered["run_observation"]["worker_execution_evidence"]
    reordered_evidence["case_frame_sha256_rows"].reverse()
    mutations.append(rehash(reordered))

    omitted = deepcopy(payload)
    omitted_evidence = omitted["run_observation"]["worker_execution_evidence"]
    omitted_evidence["case_frame_sha256_rows"].pop()
    mutations.append(rehash(omitted))

    for tampered in mutations:
        with pytest.raises(
            ReferenceMinimizationValidationResultWriterError,
            match="run observation is invalid",
        ):
            module._validate_result_receipt_payload(tampered)


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
            "cross-wired",
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
            {"source_manifest_sha256": "f" * 64},
            "cross-wired",
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

    with pytest.raises(ReferenceMinimizationValidationResultWriterError, match=message):
        _write(root, observation)
    assert not (root / f"{AUTHORIZATION_NONCE}.result.json").exists()


def _self_consistent_worker_request_replacement(
    observation: object,
    *,
    dependency_roots: list[str] | None = None,
    python_hash_seed: int | None = None,
    application_seed: int | None = None,
    python_hash_probe_sha256: str | None = None,
):
    payload = observation.to_dict()
    evidence = payload["worker_execution_evidence"]
    request = deepcopy(evidence["worker_request_document"])
    if python_hash_seed is not None:
        payload["python_hash_seed"] = python_hash_seed
        request["expected_python_hash_seed"] = python_hash_seed
        request["expected_worker_environment"]["PYTHONHASHSEED"] = str(python_hash_seed)
    if application_seed is not None:
        payload["seed"] = application_seed
        request["expected_application_seed"] = application_seed
        request["expected_worker_environment"][
            runner_module.REFERENCE_MINIMIZATION_VALIDATION_APPLICATION_SEED_ENV
        ] = str(application_seed)
    if dependency_roots is not None:
        request["dependency_roots"] = dependency_roots
        request["expected_worker_environment"]["PYTHONPATH"] = os.pathsep.join(
            dependency_roots
        )
    if python_hash_probe_sha256 is not None:
        request["expected_python_hash_probe_sha256"] = python_hash_probe_sha256
    request["expected_worker_environment_sha256"] = runner_module._sha256(
        request["expected_worker_environment"]
    )
    request_sha256 = runner_module._sha256(request)
    case_rows = tuple(
        runner_module._case_observation_from_payload(row)
        for row in payload["case_results"]
    )
    snapshot = evidence["runtime_lifecycle_evidence"]["pre"]["snapshot"]
    pre_evidence = native_identity.build_worker_runtime_pre_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        snapshot=snapshot,
    )
    lifecycle = native_identity.build_complete_worker_runtime_lifecycle_evidence(
        lane=native_identity.WORKER_RUNTIME_LANE_MINIMIZATION,
        worker_request_sha256=request_sha256,
        pre_evidence=pre_evidence,
        payload_rows=payload["case_results"],
        post_snapshot=snapshot,
    )
    transcript = runner_module._reconstruct_complete_matrix_worker_transcript(
        worker_request_sha256=request_sha256,
        case_results=case_rows,
        runtime_lifecycle_evidence=lifecycle,
    )
    payload["worker_execution_evidence"] = (
        runner_module._decode_complete_matrix_worker_transcript(
            transcript,
            worker_preflight_request=request,
            supervisor_child_process_id=evidence["supervisor_child_process_id"],
        ).worker_execution_evidence.to_dict()
    )
    return require_reference_minimization_validation_run_observation_document(payload)


def test_writer_rejects_self_consistent_worker_runtime_forgery_against_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    _install_verified_chain(monkeypatch, environment)
    forged_seed_chain = _self_consistent_worker_request_replacement(
        observation,
        python_hash_seed=124,
        application_seed=457,
    )
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError,
        match="environment and observation are cross-wired",
    ):
        _write(root, forged_seed_chain)

    forged_runtime_chain = _self_consistent_worker_request_replacement(
        observation,
        dependency_roots=["/forged-dependency-root"],
        python_hash_probe_sha256="0" * 64,
    )
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError,
        match="worker request and trusted environment are cross-wired",
    ):
        _write(root, forged_runtime_chain)

    assert not (root / f"{AUTHORIZATION_NONCE}.result.json").exists()


def test_writer_rejects_tampered_runner_start_and_observation_before_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    _install_verified_chain(monkeypatch, environment)
    start_path = root / (
        f"reference-minimization-validation-runner-start-{AUTHORIZATION_NONCE}.json"
    )
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
        ReferenceMinimizationValidationResultWriterError,
        match="run observation verification failed",
    ):
        _write(root, observation)
    assert not (root / f"{AUTHORIZATION_NONCE}.result.json").exists()

    incomplete = observation.to_dict()
    incomplete["case_results"].pop()
    with pytest.raises(ReferenceMinimizationValidationRunnerError):
        require_reference_minimization_validation_run_observation_document(incomplete)

    crosswired_source_manifest = observation.to_dict()
    crosswired_source_manifest["source_manifest_sha256"] = "not-a-digest"
    with pytest.raises(ReferenceMinimizationValidationRunnerError):
        require_reference_minimization_validation_run_observation_document(
            crosswired_source_manifest
        )


def test_writer_rejects_passing_case_with_failed_retained_metric(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    environment = _environment(root)
    observation = _observation(root, monkeypatch, environment=environment)
    payload = observation.to_dict()
    contradictory = next(row for row in payload["case_results"] if row["metric_values"])
    contradictory["metric_values"][0]["value"] = -1.0
    contradictory["case_passed"] = True
    evidence = payload["worker_execution_evidence"]
    for frame_row, case in zip(
        evidence["case_frame_sha256_rows"],
        payload["case_results"],
        strict=True,
    ):
        frame_row["case_observation_sha256"] = runner_module._sha256(case)
    evidence["retained_case_aggregate_sha256"] = runner_module._sha256(
        payload["case_results"]
    )
    lifecycle = evidence["runtime_lifecycle_evidence"]
    evidence["runtime_lifecycle_evidence"] = (
        native_identity.build_complete_worker_runtime_lifecycle_evidence(
            lane=native_identity.WORKER_RUNTIME_LANE_MINIMIZATION,
            worker_request_sha256=evidence["worker_request_sha256"],
            pre_evidence=lifecycle["pre"],
            payload_rows=payload["case_results"],
            post_snapshot=lifecycle["pre"]["snapshot"],
        )
    )

    with pytest.raises(
        ReferenceMinimizationValidationRunnerError,
        match="exact transcript-derived",
    ):
        require_reference_minimization_validation_run_observation_document(payload)


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

    with pytest.raises(ReferenceMinimizationValidationResultReceiptAlreadyExistsError):
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
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError, match="SHA-256"
    ):
        read_reference_minimization_validation_result_receipt(root, AUTHORIZATION_NONCE)

    path.write_bytes(original)
    path.chmod(0o644)
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError, match="securely"
    ):
        read_reference_minimization_validation_result_receipt(root, AUTHORIZATION_NONCE)

    path.chmod(0o600)
    hardlink = tmp_path / "result-hardlink.json"
    try:
        os.link(path, hardlink)
    except OSError:
        pytest.skip("hard links unavailable")
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError, match="securely"
    ):
        read_reference_minimization_validation_result_receipt(root, AUTHORIZATION_NONCE)
    hardlink.unlink()

    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError, match="cross-wired"
    ):
        verify_reference_minimization_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256="0" * 64,
            revoked_review_attestation_sha256s=(),
            revoked_authorization_receipt_sha256s=(),
            revoked_result_receipt_sha256s=(),
            superseded_result_receipt_sha256s=(),
        )
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError, match="revoked"
    ):
        verify_reference_minimization_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256=receipt.receipt_sha256,
            revoked_review_attestation_sha256s=(),
            revoked_authorization_receipt_sha256s=(),
            revoked_result_receipt_sha256s=(receipt.receipt_sha256,),
            superseded_result_receipt_sha256s=(),
        )
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError,
        match="review attestation is externally revoked",
    ):
        verify_reference_minimization_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256=receipt.receipt_sha256,
            revoked_review_attestation_sha256s=(REVIEW_ATTESTATION_SHA256,),
            revoked_authorization_receipt_sha256s=(),
            revoked_result_receipt_sha256s=(),
            superseded_result_receipt_sha256s=(),
        )
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError,
        match="authorization is externally revoked",
    ):
        verify_reference_minimization_validation_result_receipt(
            root,
            AUTHORIZATION_NONCE,
            expected_receipt_sha256=receipt.receipt_sha256,
            revoked_review_attestation_sha256s=(),
            revoked_authorization_receipt_sha256s=(AUTHORIZATION_RECEIPT_SHA256,),
            revoked_result_receipt_sha256s=(),
            superseded_result_receipt_sha256s=(),
        )
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError, match="superseded"
    ):
        verify_reference_minimization_validation_result_receipt(
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
        ReferenceMinimizationValidationResultWriterError,
        match="authorization nonce is cross-wired",
    ):
        read_reference_minimization_validation_result_receipt(root, other_nonce)

    copied.unlink()
    os.mkfifo(copied, mode=0o600)
    with pytest.raises(
        ReferenceMinimizationValidationResultWriterError,
        match="cannot be read securely",
    ):
        read_reference_minimization_validation_result_receipt(root, other_nonce)


def test_writer_public_surface_has_no_clock_delete_release_signature_or_cli() -> None:
    signature = inspect.signature(
        write_reference_minimization_validation_result_receipt
    )
    assert "checked_at" not in signature.parameters
    for name in (
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
    ):
        assert signature.parameters[name].default is inspect.Parameter.empty
    verify_signature = inspect.signature(
        verify_reference_minimization_validation_result_receipt
    )
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
