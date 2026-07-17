from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import inspect
import json
import os
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    AuthorizationOperatorTrustAnchor,
    build_signed_reference_validation_authorization_receipt,
    verify_signed_reference_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_validation_nonce_reservation import (
    reserve_reference_validation_authorization_nonce,
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
    FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256,
    REFERENCE_VALIDATION_APPLICATION_SEED_ENV,
    REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID,
    REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
    REFERENCE_VALIDATION_RUN_START_CONTRACT_SCHEMA_ID,
    ReferenceValidationEnvironmentReceiptAlreadyExistsError,
    ReferenceValidationRunStartError,
    build_signed_reference_validation_network_isolation_attestation,
    create_reference_validation_execution_environment_receipt,
    read_reference_validation_execution_environment_receipt,
    reference_validation_artifact_output_root_identity_sha256,
    reference_validation_run_start_contract_decision,
    reference_validation_run_start_contract_document,
    require_reference_validation_run_start_contract_document,
    verify_signed_reference_validation_network_isolation_attestation,
)
import betelgeuze_engine_v2.physics.reference_validation_run_start as module


AUTHOR_IDENTITY = "a" * 64
REVIEWER_IDENTITY = "b" * 64
OPERATOR_IDENTITY = "c" * 64
REVIEW_NONCE = "d" * 64
AUTHORIZATION_NONCE = "e" * 64
NETWORK_NAMESPACE_IDENTITY = "f" * 64
REVIEW_KEY_ID = "independent-reviewer-2026-07"
OPERATOR_KEY_ID = "validation-operator-2026-07"
REVIEW_KEY = b"review-key-material-is-test-only-32-bytes-minimum"
OPERATOR_KEY = b"operator-key-material-is-test-only-32-bytes-minimum"
REVIEWED_AT = datetime(2026, 7, 17, 5, 0, 0, tzinfo=timezone.utc)
REVIEW_EXPIRES_AT = REVIEWED_AT + timedelta(days=7)
ISSUED_AT = REVIEWED_AT + timedelta(hours=1)
EXPIRES_AT = ISSUED_AT + timedelta(hours=4)
RESERVED_AT = ISSUED_AT + timedelta(hours=1)
NOW = ISSUED_AT + timedelta(hours=2)
NETWORK_OBSERVED_AT = NOW - timedelta(minutes=1)
NETWORK_EXPIRES_AT = NOW + timedelta(minutes=4)
CODE_COMMIT_SHA = "1" * 40
RUNNER_SOURCE_SHA256 = "2" * 64
DEPENDENCY_ROWS = {
    "numpy-1.26.4-wheel": "3" * 64,
    "python-3.11-runtime": "4" * 64,
    "torch-2.6.0-cpu-wheel": "5" * 64,
}


def _review_attestation() -> dict[str, object]:
    return build_signed_reference_validation_review_attestation(
        implementation_author_identity_sha256=AUTHOR_IDENTITY,
        independent_reviewer_identity_sha256=REVIEWER_IDENTITY,
        reviewer_key_id=REVIEW_KEY_ID,
        signing_key=REVIEW_KEY,
        reviewed_at=REVIEWED_AT,
        expires_at=REVIEW_EXPIRES_AT,
        nonce_sha256=REVIEW_NONCE,
    )


def _authorization_receipt(
    *,
    review: dict[str, object] | None = None,
    issued_at: datetime = ISSUED_AT,
) -> dict[str, object]:
    selected_review = review or _review_attestation()
    return build_signed_reference_validation_authorization_receipt(
        review_attestation=selected_review,
        trusted_reviewer_keys={
            REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                REVIEWER_IDENTITY,
                REVIEW_KEY,
            )
        },
        expected_implementation_author_identity_sha256=AUTHOR_IDENTITY,
        authorization_operator_identity_sha256=OPERATOR_IDENTITY,
        authorization_key_id=OPERATOR_KEY_ID,
        signing_key=OPERATOR_KEY,
        issued_at=issued_at,
        expires_at=EXPIRES_AT,
        authorization_nonce_sha256=AUTHORIZATION_NONCE,
        code_commit_sha=CODE_COMMIT_SHA,
        runner_source_sha256=RUNNER_SOURCE_SHA256,
        execution_environment_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        result_receipt_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
    )


def _private_root(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def _trust_inputs() -> dict[str, object]:
    return {
        "trusted_reviewer_keys": {
            REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                REVIEWER_IDENTITY,
                REVIEW_KEY,
            )
        },
        "expected_implementation_author_identity_sha256": AUTHOR_IDENTITY,
        "trusted_operator_keys": {
            OPERATOR_KEY_ID: AuthorizationOperatorTrustAnchor(
                OPERATOR_IDENTITY,
                OPERATOR_KEY,
            )
        },
        "expected_code_commit_sha": CODE_COMMIT_SHA,
        "expected_runner_source_sha256": RUNNER_SOURCE_SHA256,
        "expected_dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
    }


def _reserve_nonce(
    root: Path,
    *,
    review: dict[str, object],
    receipt: dict[str, object],
) -> None:
    reserve_reference_validation_authorization_nonce(
        root,
        authorization_receipt=receipt,
        review_attestation=review,
        reserved_at=RESERVED_AT,
        **_trust_inputs(),  # type: ignore[arg-type]
    )


def _runtime_observation() -> module._RuntimeObservation:
    environment_rows = tuple(
        sorted(
            (
                ("CUDA_VISIBLE_DEVICES", ""),
                ("HIP_VISIBLE_DEVICES", ""),
                ("ROCR_VISIBLE_DEVICES", ""),
                ("LANG", "C.UTF-8"),
                ("LC_ALL", "C.UTF-8"),
                ("MKL_NUM_THREADS", "1"),
                ("OMP_NUM_THREADS", "1"),
                ("OPENBLAS_NUM_THREADS", "1"),
                ("TZ", "UTC"),
                ("PYTHONHASHSEED", "123"),
                (REFERENCE_VALIDATION_APPLICATION_SEED_ENV, "456"),
            )
        )
    )
    return module._RuntimeObservation(
        operating_system="linux",
        operating_system_release="6.8.0-test",
        machine_architecture="x86_64",
        cpu_identity_sha256="6" * 64,
        python_version="3.11.9",
        torch_version="2.6.0",
        numpy_version="1.26.4",
        environment_variable_rows=environment_rows,
        network_namespace_identity_sha256=NETWORK_NAMESPACE_IDENTITY,
        command_argv=REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
        python_hash_seed=123,
        application_seed=456,
        thread_count_rows=(
            ("mkl_num_threads", 1),
            ("omp_num_threads", 1),
            ("openblas_num_threads", 1),
            ("torch_num_interop_threads", 1),
            ("torch_num_threads", 1),
        ),
        torch_deterministic_algorithms_enabled=True,
    )


def _network_attestation(
    receipt: dict[str, object],
    output_root: Path,
    *,
    namespace_sha256: str = NETWORK_NAMESPACE_IDENTITY,
    observed_at: datetime = NETWORK_OBSERVED_AT,
    expires_at: datetime = NETWORK_EXPIRES_AT,
) -> dict[str, object]:
    return build_signed_reference_validation_network_isolation_attestation(
        authorization_receipt_sha256=receipt["receipt_sha256"],  # type: ignore[arg-type]
        authorization_nonce_sha256=AUTHORIZATION_NONCE,
        authorization_operator_identity_sha256=OPERATOR_IDENTITY,
        authorization_key_id=OPERATOR_KEY_ID,
        signing_key=OPERATOR_KEY,
        code_commit_sha=CODE_COMMIT_SHA,
        runner_source_sha256=RUNNER_SOURCE_SHA256,
        artifact_output_root_identity_sha256=(
            reference_validation_artifact_output_root_identity_sha256(output_root)
        ),
        network_namespace_identity_sha256=namespace_sha256,
        observed_at=observed_at,
        expires_at=expires_at,
    )


def _verified_authorization(
    review: dict[str, object],
    receipt: dict[str, object],
):
    return verify_signed_reference_validation_authorization_receipt(
        receipt,
        review_attestation=review,
        checked_at=NOW,
        expected_execution_environment_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        expected_result_receipt_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        **_trust_inputs(),  # type: ignore[arg-type]
    )


def _create(
    reservation_root: Path,
    output_root: Path,
    *,
    review: dict[str, object],
    receipt: dict[str, object],
    network: dict[str, object],
    **overrides: object,
):
    values: dict[str, object] = {
        "reservation_root": reservation_root,
        "artifact_output_root": output_root,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "authorization_receipt": receipt,
        "review_attestation": review,
        "network_isolation_attestation": network,
        **_trust_inputs(),
    }
    values.update(overrides)
    return create_reference_validation_execution_environment_receipt(  # type: ignore[arg-type]
        **values
    )


def test_run_start_contract_is_frozen_and_current_decision_is_closed() -> None:
    first = reference_validation_run_start_contract_document()
    second = reference_validation_run_start_contract_document()
    decision = reference_validation_run_start_contract_decision()

    assert first == second
    assert first["schema_id"] == REFERENCE_VALIDATION_RUN_START_CONTRACT_SCHEMA_ID
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256
    )
    assert first["runtime_observation"]["arbitrary_or_secret_bearing_argv_allowed"] is False
    assert first["network_isolation"]["kernel_network_isolation_enforced_by_this_library"] is False
    assert first["persistence"]["release_or_delete_api_provided"] is False
    assert require_reference_validation_run_start_contract_document(first) == first

    assert decision["run_start_environment_primitive_implemented"] is True
    assert decision["production_environment_receipt_present"] is False
    assert decision["validation_runner_implemented"] is False
    assert decision["validation_execution_authorized"] is False
    assert decision["validation_results_collected"] is False


def test_run_start_contract_rejects_tamper() -> None:
    tampered = deepcopy(reference_validation_run_start_contract_document())
    tampered["current_state"]["validation_execution_authorized"] = True
    with pytest.raises(
        ReferenceValidationRunStartError,
        match="does not match the frozen record",
    ):
        require_reference_validation_run_start_contract_document(tampered)


def test_signed_network_attestation_verifies_exact_authorization_and_namespace(
    tmp_path: Path,
) -> None:
    review = _review_attestation()
    receipt = _authorization_receipt(review=review)
    output_root = _private_root(tmp_path, "outputs")
    attestation = _network_attestation(receipt, output_root)
    verification = verify_signed_reference_validation_network_isolation_attestation(
        attestation,
        trusted_operator_keys=_trust_inputs()["trusted_operator_keys"],  # type: ignore[arg-type]
        checked_at=NOW,
        expected_authorization=_verified_authorization(review, receipt),
        expected_artifact_output_root_identity_sha256=(
            reference_validation_artifact_output_root_identity_sha256(output_root)
        ),
        expected_network_namespace_identity_sha256=NETWORK_NAMESPACE_IDENTITY,
    )

    assert verification.attestation_sha256 == attestation["attestation_sha256"]
    assert verification.authorization_operator_identity_sha256 == OPERATOR_IDENTITY
    assert verification.network_namespace_identity_sha256 == NETWORK_NAMESPACE_IDENTITY


def test_network_attestation_rejects_tamper_crosswire_expiry_and_revocation(
    tmp_path: Path,
) -> None:
    review = _review_attestation()
    receipt = _authorization_receipt(review=review)
    output_root = _private_root(tmp_path, "outputs")
    expected_authorization = _verified_authorization(review, receipt)
    attestation = _network_attestation(receipt, output_root)
    kwargs = {
        "trusted_operator_keys": _trust_inputs()["trusted_operator_keys"],
        "checked_at": NOW,
        "expected_authorization": expected_authorization,
        "expected_artifact_output_root_identity_sha256": (
            reference_validation_artifact_output_root_identity_sha256(output_root)
        ),
        "expected_network_namespace_identity_sha256": NETWORK_NAMESPACE_IDENTITY,
    }

    tampered = deepcopy(attestation)
    tampered["network_access_disabled"] = False
    with pytest.raises(ReferenceValidationRunStartError, match="signature verification"):
        verify_signed_reference_validation_network_isolation_attestation(  # type: ignore[arg-type]
            tampered,
            **kwargs,
        )

    crosswired = _network_attestation(receipt, output_root, namespace_sha256="9" * 64)
    with pytest.raises(ReferenceValidationRunStartError, match="cross-wired"):
        verify_signed_reference_validation_network_isolation_attestation(  # type: ignore[arg-type]
            crosswired,
            **kwargs,
        )

    with pytest.raises(ReferenceValidationRunStartError, match="not currently valid"):
        verify_signed_reference_validation_network_isolation_attestation(
            attestation,
            checked_at=NETWORK_EXPIRES_AT,
            trusted_operator_keys=kwargs["trusted_operator_keys"],  # type: ignore[arg-type]
            expected_authorization=expected_authorization,
            expected_artifact_output_root_identity_sha256=kwargs[
                "expected_artifact_output_root_identity_sha256"
            ],  # type: ignore[arg-type]
            expected_network_namespace_identity_sha256=NETWORK_NAMESPACE_IDENTITY,
        )

    with pytest.raises(ReferenceValidationRunStartError, match="externally revoked"):
        verify_signed_reference_validation_network_isolation_attestation(
            attestation,
            revoked_attestation_sha256s=(attestation["attestation_sha256"],),  # type: ignore[arg-type]
            **kwargs,  # type: ignore[arg-type]
        )


def test_valid_chain_persists_environment_receipt_without_opening_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_attestation()
    receipt = _authorization_receipt(review=review)
    reservation_root = _private_root(tmp_path, "reservations")
    output_root = _private_root(tmp_path, "outputs")
    _reserve_nonce(reservation_root, review=review, receipt=receipt)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(module, "_observe_current_runtime", _runtime_observation)

    created = _create(
        reservation_root,
        output_root,
        review=review,
        receipt=receipt,
        network=_network_attestation(receipt, output_root),
    )
    path = output_root / f"{AUTHORIZATION_NONCE}.environment.json"

    assert created.eligible_for_bounded_validation_runner is True
    assert created.authorization_receipt_sha256 == receipt["receipt_sha256"]
    assert created.authorization_nonce_sha256 == AUTHORIZATION_NONCE
    assert created.network_namespace_identity_sha256 == NETWORK_NAMESPACE_IDENTITY
    assert created.command_argv == REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV
    assert created.python_hash_seed == 123
    assert created.application_seed == 456
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.stat().st_nlink == 1
    assert read_reference_validation_execution_environment_receipt(
        output_root,
        AUTHORIZATION_NONCE,
    ) == created

    payload = json.loads(path.read_text(encoding="ascii"))
    assert payload["schema_id"] == (
        REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_RECEIPT_SCHEMA_ID
    )
    assert payload["run_start_dependencies_reverified"] is True
    assert payload["validation_execution_authorized"] is False
    assert payload["validation_results_collected"] is False
    assert payload["artifact_output_root"]["path_disclosed"] is False
    encoded = json.dumps(payload, sort_keys=True)
    assert "total_energy" not in encoded
    assert "force_array" not in encoded
    assert "metric_values" not in encoded


def test_raw_authorization_is_reverified_before_output_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_attestation()
    receipt = _authorization_receipt(review=review)
    reservation_root = _private_root(tmp_path, "reservations")
    output_root = _private_root(tmp_path, "outputs")
    _reserve_nonce(reservation_root, review=review, receipt=receipt)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(module, "_observe_current_runtime", _runtime_observation)
    tampered = deepcopy(receipt)
    tampered["runner_source_sha256"] = "9" * 64

    with pytest.raises(
        ReferenceValidationRunStartError,
        match="authorization re-verification failed",
    ):
        _create(
            reservation_root,
            output_root,
            review=review,
            receipt=tampered,
            network=_network_attestation(receipt, output_root),
        )
    assert list(output_root.iterdir()) == []


def test_run_start_rejects_authorization_reservation_crosswire(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_attestation()
    original_receipt = _authorization_receipt(review=review)
    changed_receipt = _authorization_receipt(
        review=review,
        issued_at=ISSUED_AT + timedelta(minutes=1),
    )
    reservation_root = _private_root(tmp_path, "reservations")
    output_root = _private_root(tmp_path, "outputs")
    _reserve_nonce(reservation_root, review=review, receipt=original_receipt)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(module, "_observe_current_runtime", _runtime_observation)

    with pytest.raises(ReferenceValidationRunStartError, match="cross-wired"):
        _create(
            reservation_root,
            output_root,
            review=review,
            receipt=changed_receipt,
            network=_network_attestation(changed_receipt, output_root),
        )
    assert list(output_root.iterdir()) == []


def _mutate_gpu_environment(observation: module._RuntimeObservation):
    rows = dict(observation.environment_variable_rows)
    rows["CUDA_VISIBLE_DEVICES"] = "0"
    return replace(observation, environment_variable_rows=tuple(sorted(rows.items())))


@pytest.mark.parametrize(
    ("mutator", "message"),
    (
        (lambda row: replace(row, operating_system="darwin"), "must be Linux"),
        (lambda row: replace(row, machine_architecture="aarch64"), "x86_64"),
        (lambda row: replace(row, python_version="3.13.0"), "Python patch"),
        (lambda row: replace(row, torch_version="2.7.0"), "Torch version"),
        (lambda row: replace(row, numpy_version="2.0.0"), "NumPy version"),
        (_mutate_gpu_environment, "CUDA_VISIBLE_DEVICES"),
        (
            lambda row: replace(
                row,
                thread_count_rows=(*row.thread_count_rows[:-1], ("torch_num_threads", 2)),
            ),
            "thread counts",
        ),
        (
            lambda row: replace(row, torch_deterministic_algorithms_enabled=False),
            "deterministic algorithms",
        ),
        (lambda row: replace(row, command_argv=("python", "--secret", "x")), "argv"),
    ),
)
def test_runtime_mismatch_fails_before_environment_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator,
    message: str,
) -> None:
    review = _review_attestation()
    receipt = _authorization_receipt(review=review)
    reservation_root = _private_root(tmp_path, "reservations")
    output_root = _private_root(tmp_path, "outputs")
    _reserve_nonce(reservation_root, review=review, receipt=receipt)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(
        module,
        "_observe_current_runtime",
        lambda: mutator(_runtime_observation()),
    )

    with pytest.raises(ReferenceValidationRunStartError, match=message):
        _create(
            reservation_root,
            output_root,
            review=review,
            receipt=receipt,
            network=_network_attestation(receipt, output_root),
        )
    assert list(output_root.iterdir()) == []


def test_duplicate_environment_receipt_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_attestation()
    receipt = _authorization_receipt(review=review)
    reservation_root = _private_root(tmp_path, "reservations")
    output_root = _private_root(tmp_path, "outputs")
    _reserve_nonce(reservation_root, review=review, receipt=receipt)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(module, "_observe_current_runtime", _runtime_observation)
    network = _network_attestation(receipt, output_root)
    first = _create(
        reservation_root,
        output_root,
        review=review,
        receipt=receipt,
        network=network,
    )
    original = (output_root / f"{AUTHORIZATION_NONCE}.environment.json").read_bytes()

    with pytest.raises(ReferenceValidationEnvironmentReceiptAlreadyExistsError):
        _create(
            reservation_root,
            output_root,
            review=review,
            receipt=receipt,
            network=network,
        )
    assert (output_root / f"{AUTHORIZATION_NONCE}.environment.json").read_bytes() == original
    assert first.to_dict()["validation_execution_authorized"] is False


def test_artifact_root_policy_and_persisted_receipt_tamper_are_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_attestation()
    receipt = _authorization_receipt(review=review)
    reservation_root = _private_root(tmp_path, "reservations")
    output_root = _private_root(tmp_path, "outputs")
    _reserve_nonce(reservation_root, review=review, receipt=receipt)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(module, "_observe_current_runtime", _runtime_observation)
    output_root.chmod(0o755)

    with pytest.raises(ReferenceValidationRunStartError, match="private POSIX policy"):
        _create(
            reservation_root,
            output_root,
            review=review,
            receipt=receipt,
            network=_network_attestation(receipt, output_root),
        )
    assert list(output_root.iterdir()) == []

    output_root.chmod(0o700)
    created = _create(
        reservation_root,
        output_root,
        review=review,
        receipt=receipt,
        network=_network_attestation(receipt, output_root),
    )
    path = output_root / f"{AUTHORIZATION_NONCE}.environment.json"
    payload = json.loads(path.read_text(encoding="ascii"))
    payload["started_at_utc"] = "2026-07-17T08:01:00Z"
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    with pytest.raises(ReferenceValidationRunStartError, match="SHA-256 verification"):
        read_reference_validation_execution_environment_receipt(
            output_root,
            AUTHORIZATION_NONCE,
        )
    assert created.to_dict()["claim_safe"] is False


def test_read_rejects_unsafe_mode_and_hardlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    review = _review_attestation()
    receipt = _authorization_receipt(review=review)
    reservation_root = _private_root(tmp_path, "reservations")
    output_root = _private_root(tmp_path, "outputs")
    _reserve_nonce(reservation_root, review=review, receipt=receipt)
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(module, "_observe_current_runtime", _runtime_observation)
    network = _network_attestation(receipt, output_root)
    _create(
        reservation_root,
        output_root,
        review=review,
        receipt=receipt,
        network=network,
    )
    path = output_root / f"{AUTHORIZATION_NONCE}.environment.json"
    path.chmod(0o644)
    with pytest.raises(ReferenceValidationRunStartError, match="file policy"):
        read_reference_validation_execution_environment_receipt(
            output_root,
            AUTHORIZATION_NONCE,
        )

    path.chmod(0o600)
    try:
        os.link(path, tmp_path / "environment-receipt-hardlink.json")
    except OSError:
        pytest.skip("hard links unavailable")
    with pytest.raises(ReferenceValidationRunStartError, match="file policy"):
        read_reference_validation_execution_environment_receipt(
            output_root,
            AUTHORIZATION_NONCE,
        )


def test_module_has_no_clock_override_runner_evaluator_writer_or_delete_api() -> None:
    create_signature = inspect.signature(
        create_reference_validation_execution_environment_receipt
    )
    assert "checked_at" not in create_signature.parameters
    public = set(module.__all__)
    assert not any(name.startswith("delete_") for name in public)
    assert not any(name.startswith("release_") for name in public)
    assert not any(name.startswith("run_reference") for name in public)
    assert not any(name.startswith("write_result") for name in public)

    source = inspect.getsource(module)
    assert "reference_forcefield" not in source
    assert "evaluate_reference_force_field" not in source
    assert "evaluate_independent_analytic_oracle" not in source
    assert "subprocess" not in source
