from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_authorization import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID,
    REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_MAX_VALIDITY,
    REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
    REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
    MinimizationAuthorizationOperatorTrustAnchor,
    ReferenceMinimizationValidationAuthorizationError,
    build_signed_reference_minimization_validation_authorization_receipt,
    reference_minimization_validation_authorization_contract_decision,
    reference_minimization_validation_authorization_contract_document,
    require_reference_minimization_validation_authorization_contract_document,
    verify_signed_reference_minimization_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_receipts import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_review import (
    MinimizationScientificReviewerTrustAnchor,
    build_signed_reference_minimization_validation_review_attestation,
)


AUTHOR = "a" * 64
REVIEWER = "b" * 64
OPERATOR = "c" * 64
OTHER_OPERATOR = "d" * 64
REVIEW_NONCE = "e" * 64
AUTH_NONCE = "f" * 64
REVIEW_KEY_ID = "minimization-reviewer-2026-07"
OPERATOR_KEY_ID = "minimization-operator-2026-07"
REVIEW_KEY = bytes.fromhex("11" * 32)
OPERATOR_KEY = bytes.fromhex("21" * 32)
OTHER_KEY = bytes.fromhex("22" * 32)
REVIEW_PUBLIC_KEY = ed25519_public_key_bytes(REVIEW_KEY)
OPERATOR_PUBLIC_KEY = ed25519_public_key_bytes(OPERATOR_KEY)
OTHER_PUBLIC_KEY = ed25519_public_key_bytes(OTHER_KEY)
REVIEWED_AT = datetime(2026, 7, 18, 1, 0, tzinfo=timezone.utc)
REVIEW_EXPIRES = REVIEWED_AT + timedelta(days=7)
ISSUED_AT = REVIEWED_AT + timedelta(hours=2)
EXPIRES_AT = ISSUED_AT + timedelta(hours=4)
CHECKED_AT = ISSUED_AT + timedelta(hours=1)
CODE_COMMIT = "1" * 40
RUNNER_SOURCE = "2" * 64
DEPENDENCIES = {
    "numpy-1.26.4-wheel": "3" * 64,
    "python-3.11-runtime": "4" * 64,
    "torch-2.6.0-cpu-wheel": "5" * 64,
}


def _review() -> dict[str, object]:
    return build_signed_reference_minimization_validation_review_attestation(
        implementation_author_identity_sha256=AUTHOR,
        independent_reviewer_identity_sha256=REVIEWER,
        reviewer_key_id=REVIEW_KEY_ID,
        signing_key=REVIEW_KEY,
        reviewed_at=REVIEWED_AT,
        expires_at=REVIEW_EXPIRES,
        nonce_sha256=REVIEW_NONCE,
    )


def _receipt(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "review_attestation": _review(),
        "trusted_reviewer_keys": {REVIEW_KEY_ID: MinimizationScientificReviewerTrustAnchor(REVIEWER, REVIEW_PUBLIC_KEY)},
        "expected_implementation_author_identity_sha256": AUTHOR,
        "authorization_operator_identity_sha256": OPERATOR,
        "authorization_key_id": OPERATOR_KEY_ID,
        "signing_key": OPERATOR_KEY,
        "issued_at": ISSUED_AT,
        "expires_at": EXPIRES_AT,
        "authorization_nonce_sha256": AUTH_NONCE,
        "code_commit_sha": CODE_COMMIT,
        "runner_source_sha256": RUNNER_SOURCE,
        "dependency_artifact_sha256_rows": DEPENDENCIES,
    }
    values.update(overrides)
    return build_signed_reference_minimization_validation_authorization_receipt(  # type: ignore[arg-type]
        **values
    )


def _verify(source: object, **overrides: object):
    values: dict[str, object] = {
        "source": source,
        "review_attestation": _review(),
        "trusted_reviewer_keys": {REVIEW_KEY_ID: MinimizationScientificReviewerTrustAnchor(REVIEWER, REVIEW_PUBLIC_KEY)},
        "expected_implementation_author_identity_sha256": AUTHOR,
        "trusted_operator_keys": {
            OPERATOR_KEY_ID: MinimizationAuthorizationOperatorTrustAnchor(OPERATOR, OPERATOR_PUBLIC_KEY)
        },
        "checked_at": CHECKED_AT,
        "expected_code_commit_sha": CODE_COMMIT,
        "expected_runner_source_sha256": RUNNER_SOURCE,
        "expected_dependency_artifact_sha256_rows": DEPENDENCIES,
    }
    values.update(overrides)
    return verify_signed_reference_minimization_validation_authorization_receipt(  # type: ignore[arg-type]
        **values
    )


def test_contract_is_frozen_receipt_free_and_binds_receipt_contracts() -> None:
    contract = reference_minimization_validation_authorization_contract_document()
    decision = reference_minimization_validation_authorization_contract_decision()

    assert contract["schema_id"] == REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID
    assert contract["contract_sha256"] == FROZEN_REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
    assert contract["dependencies"]["execution_environment_contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
    )
    assert contract["dependencies"]["result_receipt_contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
    )
    assert contract["identity_policy"]["all_three_identities_must_be_pairwise_distinct"] is True
    assert contract["identity_policy"]["verifier_trust_anchor_contains_public_key_only"] is True
    assert REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM == "ed25519"
    assert contract["receipt_schema"]["signature_algorithm"] == "ed25519"
    assert contract["receipt_schema"]["maximum_execution_count"] == 1
    assert contract["receipt_schema"]["one_time_nonce_required"] is True
    assert contract["receipt_schema"]["external_revocation_sets_required"] is True
    assert contract["current_state"]["authorization_receipt_present"] is False
    assert contract["claim_policy"]["minimization_validated"] is False
    assert contract["claim_policy"]["claim_safe"] is False
    assert require_reference_minimization_validation_authorization_contract_document(contract) == contract
    assert decision["authorization_receipt_present"] is False
    assert decision["validation_execution_authorized"] is False


def test_contract_rejects_tamper() -> None:
    contract = deepcopy(reference_minimization_validation_authorization_contract_document())
    contract["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="does not match the frozen record",
    ):
        require_reference_minimization_validation_authorization_contract_document(contract)


def test_signed_receipt_verifies_eligibility_but_cannot_open_execution() -> None:
    receipt = _receipt()
    verified = _verify(receipt)

    assert receipt["schema_id"] == REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
    assert receipt["authorization_scope"]["maximum_execution_count"] == 1
    assert receipt["authorization_scope"]["network_access_allowed"] is False
    assert receipt["execution_environment_contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
    )
    assert verified.receipt_authorization_verified is True
    assert verified.eligible_for_atomic_execution_reservation is True
    assert verified.authorization_operator_identity_sha256 == OPERATOR
    assert dict(verified.dependency_artifact_sha256_rows) == DEPENDENCIES
    assert verified.validation_execution_authorized is False
    assert verified.parameter_fitting_proposal_authorized is False
    assert verified.parameter_fitting_authorized is False
    assert "authorization_nonce_not_atomically_reserved" in verified.blockers


def test_receipt_accepts_canonical_json_bytes() -> None:
    receipt = _receipt()
    encoded = json.dumps(receipt, sort_keys=True, allow_nan=False).encode("utf-8")
    assert _verify(encoded).receipt_sha256 == receipt["receipt_sha256"]


def test_receipt_rejects_duplicate_json_and_unsigned_tamper() -> None:
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="duplicate JSON key",
    ):
        _verify(b'{"schema_id":"first","schema_id":"second"}')
    receipt = deepcopy(_receipt())
    receipt["claim_safe"] = True
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="signature verification failed",
    ):
        _verify(receipt)


def test_receipt_requires_trusted_matching_operator_key() -> None:
    receipt = _receipt()
    with pytest.raises(ReferenceMinimizationValidationAuthorizationError, match="not trusted"):
        _verify(receipt, trusted_operator_keys={})
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="signature verification failed",
    ):
        _verify(
            receipt,
            trusted_operator_keys={OPERATOR_KEY_ID: MinimizationAuthorizationOperatorTrustAnchor(OPERATOR, OTHER_PUBLIC_KEY)},
        )
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="does not match the trusted key",
    ):
        _verify(
            receipt,
            trusted_operator_keys={
                OPERATOR_KEY_ID: MinimizationAuthorizationOperatorTrustAnchor(OTHER_OPERATOR, OPERATOR_PUBLIC_KEY)
            },
        )


@pytest.mark.parametrize("identity", (AUTHOR, REVIEWER))
def test_operator_must_differ_from_author_and_reviewer(identity: str) -> None:
    receipt = _receipt(authorization_operator_identity_sha256=identity)
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="must differ from author and reviewer",
    ):
        _verify(
            receipt,
            trusted_operator_keys={
                OPERATOR_KEY_ID: MinimizationAuthorizationOperatorTrustAnchor(identity, OPERATOR_PUBLIC_KEY)
            },
        )


def test_receipt_enforces_24_hour_and_review_lifetimes() -> None:
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="exceeds the frozen maximum",
    ):
        _verify(
            _receipt(
                expires_at=ISSUED_AT
                + REFERENCE_MINIMIZATION_VALIDATION_AUTHORIZATION_MAX_VALIDITY
                + timedelta(seconds=1)
            )
        )
    with pytest.raises(ReferenceMinimizationValidationAuthorizationError, match="not yet valid"):
        _verify(_receipt(), checked_at=ISSUED_AT - timedelta(seconds=1))
    with pytest.raises(ReferenceMinimizationValidationAuthorizationError, match="is expired"):
        _verify(_receipt(), checked_at=EXPIRES_AT)


def test_receipt_enforces_revocation_and_nonce_consumption() -> None:
    receipt = _receipt()
    verified = _verify(receipt)
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="receipt is externally revoked",
    ):
        _verify(receipt, revoked_receipt_sha256s=(verified.receipt_sha256,))
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="review attestation is externally revoked",
    ):
        _verify(
            receipt,
            revoked_review_attestation_sha256s=(verified.review_attestation_sha256,),
        )
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="nonce was already consumed",
    ):
        _verify(receipt, consumed_nonce_sha256s=(AUTH_NONCE,))


@pytest.mark.parametrize(
    ("argument", "replacement"),
    (
        ("expected_code_commit_sha", "8" * 40),
        ("expected_runner_source_sha256", "8" * 64),
        ("expected_dependency_artifact_sha256_rows", {"python": "8" * 64}),
    ),
)
def test_receipt_rejects_expected_dependency_crosswire(argument: str, replacement: object) -> None:
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="do not match the frozen schema or expected dependencies",
    ):
        _verify(_receipt(), **{argument: replacement})


def test_trust_anchor_redacts_key_and_rejects_short_key() -> None:
    anchor = MinimizationAuthorizationOperatorTrustAnchor(OPERATOR, OPERATOR_PUBLIC_KEY)
    assert "operator-key-material" not in repr(anchor)
    with pytest.raises(
        ReferenceMinimizationValidationAuthorizationError,
        match="exactly 32 bytes",
    ):
        MinimizationAuthorizationOperatorTrustAnchor(OPERATOR, b"short")
