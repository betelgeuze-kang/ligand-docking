from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    AuthorizationOperatorTrustAnchor,
    build_signed_reference_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_validation_nonce_reservation import (
    FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
    REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID,
    REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
    ReferenceValidationNonceAlreadyReservedError,
    ReferenceValidationNonceReservationError,
    read_reference_validation_nonce_reservation,
    reference_validation_nonce_reservation_contract_decision,
    reference_validation_nonce_reservation_contract_document,
    require_reference_validation_nonce_reservation_contract_document,
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
import betelgeuze_engine_v2.physics.reference_validation_nonce_reservation as module


AUTHOR_IDENTITY = "a" * 64
REVIEWER_IDENTITY = "b" * 64
OPERATOR_IDENTITY = "c" * 64
REVIEW_NONCE = "d" * 64
AUTHORIZATION_NONCE = "e" * 64
REVIEW_KEY_ID = "independent-reviewer-2026-07"
OPERATOR_KEY_ID = "validation-operator-2026-07"
REVIEW_KEY = b"review-key-material-is-test-only-32-bytes-minimum"
OPERATOR_KEY = b"operator-key-material-is-test-only-32-bytes-minimum"
REVIEWED_AT = datetime(2026, 7, 17, 5, 0, 0, tzinfo=timezone.utc)
REVIEW_EXPIRES_AT = REVIEWED_AT + timedelta(days=7)
ISSUED_AT = REVIEWED_AT + timedelta(hours=1)
EXPIRES_AT = ISSUED_AT + timedelta(hours=4)
RESERVED_AT = ISSUED_AT + timedelta(hours=1)
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
    review_attestation: dict[str, object] | None = None,
    **overrides: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "review_attestation": review_attestation or _review_attestation(),
        "trusted_reviewer_keys": {
            REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                REVIEWER_IDENTITY,
                REVIEW_KEY,
            )
        },
        "expected_implementation_author_identity_sha256": AUTHOR_IDENTITY,
        "authorization_operator_identity_sha256": OPERATOR_IDENTITY,
        "authorization_key_id": OPERATOR_KEY_ID,
        "signing_key": OPERATOR_KEY,
        "issued_at": ISSUED_AT,
        "expires_at": EXPIRES_AT,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "code_commit_sha": CODE_COMMIT_SHA,
        "runner_source_sha256": RUNNER_SOURCE_SHA256,
        "execution_environment_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        "result_receipt_contract_sha256": (
            FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        "dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
    }
    values.update(overrides)
    return build_signed_reference_validation_authorization_receipt(**values)  # type: ignore[arg-type]


def _reservation_root(tmp_path: Path, name: str = "reservations") -> Path:
    root = tmp_path / name
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def _reserve(
    root: Path,
    *,
    receipt: dict[str, object] | None = None,
    review: dict[str, object] | None = None,
    reserved_at: datetime = RESERVED_AT,
    **overrides: object,
):
    review_attestation = review or _review_attestation()
    values: dict[str, object] = {
        "reservation_root": root,
        "authorization_receipt": receipt
        or _authorization_receipt(review_attestation=review_attestation),
        "review_attestation": review_attestation,
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
        "reserved_at": reserved_at,
        "expected_code_commit_sha": CODE_COMMIT_SHA,
        "expected_runner_source_sha256": RUNNER_SOURCE_SHA256,
        "expected_dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
    }
    values.update(overrides)
    return reserve_reference_validation_authorization_nonce(**values)  # type: ignore[arg-type]


def test_nonce_reservation_contract_is_frozen_and_current_decision_is_closed() -> None:
    first = reference_validation_nonce_reservation_contract_document()
    second = reference_validation_nonce_reservation_contract_document()
    decision = reference_validation_nonce_reservation_contract_decision()

    assert first == second
    assert first["schema_id"] == (
        REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SCHEMA_ID
    )
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
    )
    assert first["atomicity_and_durability"]["duplicate_or_preexisting_path_fails_closed"]
    assert first["atomicity_and_durability"]["release_or_delete_api_provided"] is False
    assert (
        first["atomicity_and_durability"]
        ["same_uid_unlink_or_replacement_resistance_established"]
        is False
    )
    assert first["current_state"]["atomic_nonce_reservation_primitive_implemented"]
    assert first["current_state"]["authorization_nonce_reserved"] is False
    assert first["claim_policy"]["claim_safe"] is False
    assert require_reference_validation_nonce_reservation_contract_document(first) == first

    assert decision["atomic_nonce_reservation_primitive_implemented"] is True
    assert decision["authorization_receipt_present"] is False
    assert decision["authorization_nonce_reserved"] is False
    assert decision["validation_execution_authorized"] is False
    assert decision["validation_results_collected"] is False


def test_nonce_reservation_contract_rejects_tamper() -> None:
    tampered = deepcopy(reference_validation_nonce_reservation_contract_document())
    tampered["current_state"]["validation_execution_authorized"] = True
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="does not match the frozen record",
    ):
        require_reference_validation_nonce_reservation_contract_document(tampered)


def test_valid_raw_artifacts_reserve_once_and_round_trip_durable_record(
    tmp_path: Path,
) -> None:
    root = _reservation_root(tmp_path)
    reservation = _reserve(root)
    path = root / f"{AUTHORIZATION_NONCE}.json"

    assert reservation.authorization_nonce_sha256 == AUTHORIZATION_NONCE
    assert reservation.code_commit_sha == CODE_COMMIT_SHA
    assert reservation.runner_source_sha256 == RUNNER_SOURCE_SHA256
    assert reservation.execution_environment_contract_sha256 == (
        FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
    )
    assert reservation.result_receipt_contract_sha256 == (
        FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
    )
    assert dict(reservation.dependency_artifact_sha256_rows) == DEPENDENCY_ROWS
    assert reservation.reservation_persisted is True
    assert reservation.validation_execution_authorized is False
    assert reservation.validation_results_collected is False
    assert reservation.parameter_fitting_authorized is False
    assert "authorization_nonce_not_atomically_reserved" not in reservation.blockers
    assert "execution_environment_not_reverified_at_run_start" in reservation.blockers
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.stat().st_nlink == 1
    assert read_reference_validation_nonce_reservation(root, AUTHORIZATION_NONCE) == (
        reservation
    )

    payload = json.loads(path.read_text(encoding="ascii"))
    assert payload["schema_id"] == REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID
    assert payload["validation_execution_authorized"] is False
    assert payload["validation_results_collected"] is False


def test_duplicate_reservation_always_fails_closed(tmp_path: Path) -> None:
    root = _reservation_root(tmp_path)
    first = _reserve(root)
    original = (root / f"{AUTHORIZATION_NONCE}.json").read_bytes()

    with pytest.raises(
        ReferenceValidationNonceAlreadyReservedError,
        match="already reserved",
    ):
        _reserve(root)
    assert (root / f"{AUTHORIZATION_NONCE}.json").read_bytes() == original
    assert first.validation_execution_authorized is False


def test_concurrent_reservation_has_exactly_one_winner(tmp_path: Path) -> None:
    root = _reservation_root(tmp_path)
    review = _review_attestation()
    receipt = _authorization_receipt(review_attestation=review)

    def attempt() -> str:
        try:
            _reserve(root, receipt=receipt, review=review)
        except ReferenceValidationNonceAlreadyReservedError:
            return "already_reserved"
        return "reserved"

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(lambda _: attempt(), range(8)))
    assert outcomes.count("reserved") == 1
    assert outcomes.count("already_reserved") == 7
    assert read_reference_validation_nonce_reservation(
        root,
        AUTHORIZATION_NONCE,
    ).reservation_persisted is True


def test_invalid_raw_receipt_is_rejected_before_filesystem_mutation(
    tmp_path: Path,
) -> None:
    root = _reservation_root(tmp_path)
    receipt = _authorization_receipt()
    receipt["runner_source_sha256"] = "9" * 64

    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="authorization verification failed",
    ):
        _reserve(root, receipt=receipt)
    assert list(root.iterdir()) == []


def test_externally_consumed_or_expired_nonce_is_rejected_without_record(
    tmp_path: Path,
) -> None:
    consumed_root = _reservation_root(tmp_path, "consumed")
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="authorization verification failed",
    ):
        _reserve(
            consumed_root,
            externally_consumed_nonce_sha256s=(AUTHORIZATION_NONCE,),
        )
    assert list(consumed_root.iterdir()) == []

    expired_root = _reservation_root(tmp_path, "expired")
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="authorization verification failed",
    ):
        _reserve(expired_root, reserved_at=EXPIRES_AT)
    assert list(expired_root.iterdir()) == []


def test_reservation_root_must_be_absolute_private_owned_and_symlink_free(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="absolute path",
    ):
        _reserve(Path("relative-reservations"))

    permissive = _reservation_root(tmp_path, "permissive")
    permissive.chmod(0o755)
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="mode must be 0700",
    ):
        _reserve(permissive)

    real = _reservation_root(tmp_path, "real")
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="symlink",
    ):
        _reserve(alias)
    assert list(real.iterdir()) == []


def test_preexisting_symlink_consumes_nonce_without_touching_target(
    tmp_path: Path,
) -> None:
    root = _reservation_root(tmp_path)
    victim = tmp_path / "victim.txt"
    victim.write_text("unchanged", encoding="utf-8")
    reservation_path = root / f"{AUTHORIZATION_NONCE}.json"
    try:
        reservation_path.symlink_to(victim)
    except OSError:
        pytest.skip("symlinks unavailable")

    with pytest.raises(ReferenceValidationNonceAlreadyReservedError):
        _reserve(root)
    assert victim.read_text(encoding="utf-8") == "unchanged"


def test_read_rejects_tamper_unsafe_mode_and_hardlink(tmp_path: Path) -> None:
    tamper_root = _reservation_root(tmp_path, "tamper")
    _reserve(tamper_root)
    tamper_path = tamper_root / f"{AUTHORIZATION_NONCE}.json"
    payload = json.loads(tamper_path.read_text(encoding="ascii"))
    payload["reserved_at_utc"] = "2026-07-17T07:30:00Z"
    tamper_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="SHA-256 verification failed",
    ):
        read_reference_validation_nonce_reservation(
            tamper_root,
            AUTHORIZATION_NONCE,
        )

    mode_root = _reservation_root(tmp_path, "mode")
    _reserve(mode_root)
    mode_path = mode_root / f"{AUTHORIZATION_NONCE}.json"
    mode_path.chmod(0o644)
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="mode must be 0600",
    ):
        read_reference_validation_nonce_reservation(mode_root, AUTHORIZATION_NONCE)

    link_root = _reservation_root(tmp_path, "hardlink")
    _reserve(link_root)
    link_path = link_root / f"{AUTHORIZATION_NONCE}.json"
    os.link(link_path, tmp_path / "reservation-hardlink.json")
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="link count must equal one",
    ):
        read_reference_validation_nonce_reservation(link_root, AUTHORIZATION_NONCE)


def test_persistence_failure_poison_consumes_nonce_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _reservation_root(tmp_path)
    original_write_all = module._write_all

    def fail_write(_descriptor: int, _payload: bytes) -> None:
        raise OSError("simulated durable write failure")

    monkeypatch.setattr(module, "_write_all", fail_write)
    with pytest.raises(
        ReferenceValidationNonceReservationError,
        match="path remains consumed",
    ):
        _reserve(root)
    poison = root / f"{AUTHORIZATION_NONCE}.json"
    assert poison.exists()

    monkeypatch.setattr(module, "_write_all", original_write_all)
    with pytest.raises(ReferenceValidationNonceAlreadyReservedError):
        _reserve(root)


def test_module_exposes_no_release_delete_runner_or_result_writer_api() -> None:
    public = set(module.__all__)
    assert not any(name.startswith("release_") for name in public)
    assert not any(name.startswith("delete_") for name in public)
    assert not any(name.startswith("run_") for name in public)
    assert not any(name.startswith("write_result") for name in public)
