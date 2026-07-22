from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
)

from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256,
    REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID,
    REFERENCE_VALIDATION_AUTHORIZATION_MAX_VALIDITY,
    REFERENCE_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID,
    REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM,
    AuthorizationOperatorTrustAnchor,
    ReferenceValidationAuthorizationError,
    build_signed_reference_validation_authorization_receipt,
    reference_validation_authorization_contract_decision,
    reference_validation_authorization_contract_document,
    require_reference_validation_authorization_contract_document,
    verify_signed_reference_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    ScientificReviewerTrustAnchor,
    build_signed_reference_validation_review_attestation,
    verify_signed_reference_validation_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)


AUTHOR_IDENTITY = "a" * 64
REVIEWER_IDENTITY = "b" * 64
OPERATOR_IDENTITY = "c" * 64
OTHER_OPERATOR_IDENTITY = "d" * 64
REVIEW_NONCE = "e" * 64
AUTHORIZATION_NONCE = "f" * 64
REVIEW_KEY_ID = "independent-reviewer-2026-07"
OPERATOR_KEY_ID = "validation-operator-2026-07"
REVIEW_PRIVATE_KEY = bytes.fromhex("21" * 32)
REVIEW_KEY = ed25519_public_key_bytes(REVIEW_PRIVATE_KEY)
OPERATOR_PRIVATE_KEY = bytes.fromhex("22" * 32)
OPERATOR_KEY = ed25519_public_key_bytes(OPERATOR_PRIVATE_KEY)
OTHER_PRIVATE_KEY = bytes.fromhex("23" * 32)
OTHER_KEY = ed25519_public_key_bytes(OTHER_PRIVATE_KEY)
REVIEWED_AT = datetime(2026, 7, 17, 4, 0, 0, tzinfo=timezone.utc)
REVIEW_EXPIRES_AT = REVIEWED_AT + timedelta(days=7)
ISSUED_AT = REVIEWED_AT + timedelta(hours=2)
EXPIRES_AT = ISSUED_AT + timedelta(hours=4)
CHECKED_AT = ISSUED_AT + timedelta(hours=1)
CODE_COMMIT_SHA = "1" * 40
RUNNER_SOURCE_SHA256 = "2" * 64
ENVIRONMENT_CONTRACT_SHA256 = (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
)
RESULT_CONTRACT_SHA256 = FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
DEPENDENCY_ROWS = {
    "cryptography-distribution": "5" * 64,
    "numpy-distribution": "6" * 64,
    "openssl-executable": "7" * 64,
    "python-runtime-executable": "8" * 64,
    "python-standard-library": "9" * 64,
    "torch-distribution": "a" * 64,
}


def _review_attestation() -> dict[str, object]:
    return build_signed_reference_validation_review_attestation(
        implementation_author_identity_sha256=AUTHOR_IDENTITY,
        independent_reviewer_identity_sha256=REVIEWER_IDENTITY,
        reviewer_key_id=REVIEW_KEY_ID,
        signing_key=REVIEW_PRIVATE_KEY,
        reviewed_at=REVIEWED_AT,
        expires_at=REVIEW_EXPIRES_AT,
        nonce_sha256=REVIEW_NONCE,
    )


def _review_verification():
    return verify_signed_reference_validation_review_attestation(
        _review_attestation(),
        trusted_reviewer_keys={
            REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                REVIEWER_IDENTITY,
                REVIEW_KEY,
            )
        },
        expected_implementation_author_identity_sha256=AUTHOR_IDENTITY,
        checked_at=REVIEWED_AT + timedelta(hours=1),
    )


def _receipt(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "review_attestation": _review_attestation(),
        "trusted_reviewer_keys": {
            REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                REVIEWER_IDENTITY,
                REVIEW_KEY,
            )
        },
        "expected_implementation_author_identity_sha256": AUTHOR_IDENTITY,
        "authorization_operator_identity_sha256": OPERATOR_IDENTITY,
        "authorization_key_id": OPERATOR_KEY_ID,
        "signing_key": OPERATOR_PRIVATE_KEY,
        "issued_at": ISSUED_AT,
        "expires_at": EXPIRES_AT,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "code_commit_sha": CODE_COMMIT_SHA,
        "runner_source_sha256": RUNNER_SOURCE_SHA256,
        "execution_environment_contract_sha256": ENVIRONMENT_CONTRACT_SHA256,
        "result_receipt_contract_sha256": RESULT_CONTRACT_SHA256,
        "dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
    }
    values.update(overrides)
    return build_signed_reference_validation_authorization_receipt(**values)  # type: ignore[arg-type]


def _verify(
    source: object,
    *,
    review_attestation=None,
    anchor: AuthorizationOperatorTrustAnchor | None = None,
    checked_at: datetime = CHECKED_AT,
    **overrides: object,
):
    values: dict[str, object] = {
        "source": source,
        "review_attestation": review_attestation or _review_attestation(),
        "trusted_reviewer_keys": {
            REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                REVIEWER_IDENTITY,
                REVIEW_KEY,
            )
        },
        "expected_implementation_author_identity_sha256": AUTHOR_IDENTITY,
        "trusted_operator_keys": {
            OPERATOR_KEY_ID: anchor
            or AuthorizationOperatorTrustAnchor(
                OPERATOR_IDENTITY,
                OPERATOR_KEY,
            )
        },
        "checked_at": checked_at,
        "expected_code_commit_sha": CODE_COMMIT_SHA,
        "expected_runner_source_sha256": RUNNER_SOURCE_SHA256,
        "expected_execution_environment_contract_sha256": (ENVIRONMENT_CONTRACT_SHA256),
        "expected_result_receipt_contract_sha256": RESULT_CONTRACT_SHA256,
        "expected_dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
    }
    values.update(overrides)
    return verify_signed_reference_validation_authorization_receipt(**values)  # type: ignore[arg-type]


def test_authorization_contract_is_frozen_and_current_decision_is_closed() -> None:
    first = reference_validation_authorization_contract_document()
    second = reference_validation_authorization_contract_document()
    decision = reference_validation_authorization_contract_decision()

    assert first == second
    assert first["schema_id"] == REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SCHEMA_ID
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_AUTHORIZATION_CONTRACT_SHA256
    )
    assert first["receipt_schema"]["maximum_execution_count"] == 1
    assert first["receipt_schema"]["one_time_nonce_required"] is True
    assert first["receipt_schema"]["external_revocation_sets_required"] is True
    assert (
        first["receipt_schema"]["atomic_nonce_reservation_required_before_execution"]
        is True
    )
    assert first["receipt_schema"]["parameter_fitting_authorized"] is False
    assert first["current_state"]["authorization_receipt_present"] is False
    assert first["current_state"]["validation_execution_authorized"] is False
    assert first["claim_policy"]["scientifically_validated"] is False
    assert first["claim_policy"]["claim_safe"] is False
    assert require_reference_validation_authorization_contract_document(first) == first

    assert decision["authorization_receipt_present"] is False
    assert decision["trusted_operator_key_present"] is False
    assert decision["authorization_nonce_reserved"] is False
    assert decision["validation_execution_authorized"] is False
    assert decision["parameter_fitting_authorized"] is False
    assert "signed_execution_authorization_receipt_missing" in decision["blockers"]


def test_authorization_contract_rejects_tamper() -> None:
    tampered = deepcopy(reference_validation_authorization_contract_document())
    tampered["current_state"]["validation_execution_authorized"] = True
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="does not match the frozen record",
    ):
        require_reference_validation_authorization_contract_document(tampered)


def test_signed_authorization_receipt_verifies_but_cannot_open_execution() -> None:
    receipt = _receipt()
    verification = _verify(receipt)

    assert receipt["schema_id"] == REFERENCE_VALIDATION_AUTHORIZATION_RECEIPT_SCHEMA_ID
    assert receipt["signature"]["algorithm"] == (
        REFERENCE_VALIDATION_AUTHORIZATION_SIGNATURE_ALGORITHM
    )
    assert receipt["authorization_scope"] == {
        "lane": "synthetic_implementation_mathematics_only",
        "cpu_only": True,
        "network_access_allowed": False,
        "maximum_execution_count": 1,
        "one_time_nonce_required": True,
        "scientific_parameterized_force_field_lane_authorized": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "benchmark_publication_authorized": False,
        "customer_execution_authorized": False,
    }
    assert receipt["scientifically_validated"] is False
    assert receipt["claim_safe"] is False
    assert verification.receipt_authorization_verified is True
    assert verification.eligible_for_atomic_execution_reservation is True
    assert verification.implementation_author_identity_sha256 == AUTHOR_IDENTITY
    assert verification.independent_reviewer_identity_sha256 == REVIEWER_IDENTITY
    assert verification.authorization_key_id == OPERATOR_KEY_ID
    assert verification.code_commit_sha == CODE_COMMIT_SHA
    assert verification.runner_source_sha256 == RUNNER_SOURCE_SHA256
    assert verification.execution_environment_contract_sha256 == (
        ENVIRONMENT_CONTRACT_SHA256
    )
    assert verification.result_receipt_contract_sha256 == RESULT_CONTRACT_SHA256
    assert dict(verification.dependency_artifact_sha256_rows) == DEPENDENCY_ROWS
    assert verification.validation_execution_authorized is False
    assert verification.parameter_fitting_proposal_authorized is False
    assert verification.parameter_fitting_authorized is False
    assert "authorization_nonce_not_atomically_reserved" in verification.blockers
    assert "validation_execution_not_authorized" in verification.blockers


def test_signed_authorization_receipt_accepts_json_bytes() -> None:
    receipt = _receipt()
    encoded = json.dumps(receipt, sort_keys=True, allow_nan=False).encode("utf-8")
    assert _verify(encoded).receipt_sha256 == receipt["receipt_sha256"]


def test_signed_authorization_receipt_rejects_duplicate_json_or_signature_fields() -> (
    None
):
    with pytest.raises(
        ReferenceValidationAuthorizationError, match="duplicate JSON key"
    ):
        _verify(b'{"schema_id":"first","schema_id":"second"}')

    receipt = deepcopy(_receipt())
    signature = receipt["signature"]
    assert isinstance(signature, dict)
    signature["unexpected"] = False
    with pytest.raises(ReferenceValidationAuthorizationError, match="signature fields"):
        _verify(receipt)


def test_signed_authorization_receipt_rejects_legacy_hmac_algorithm() -> None:
    receipt = deepcopy(_receipt())
    receipt["signature"]["algorithm"] = "hmac-sha256"  # type: ignore[index]

    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="signature algorithm is unsupported",
    ):
        _verify(receipt)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("claim_safe", True),
        ("revoked", True),
        ("code_commit_sha", "8" * 40),
        ("authorization_nonce_sha256", "9" * 64),
    ),
)
def test_signed_authorization_receipt_rejects_unsigned_tamper(
    field: str,
    replacement: object,
) -> None:
    tampered = deepcopy(_receipt())
    tampered[field] = replacement
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="signature verification failed",
    ):
        _verify(tampered)


def test_signed_authorization_receipt_rejects_untrusted_or_mismatched_key() -> None:
    receipt = _receipt()
    with pytest.raises(ReferenceValidationAuthorizationError, match="not trusted"):
        verify_signed_reference_validation_authorization_receipt(
            receipt,
            review_attestation=_review_attestation(),
            trusted_reviewer_keys={
                REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                    REVIEWER_IDENTITY,
                    REVIEW_KEY,
                )
            },
            expected_implementation_author_identity_sha256=AUTHOR_IDENTITY,
            trusted_operator_keys={},
            checked_at=CHECKED_AT,
            expected_code_commit_sha=CODE_COMMIT_SHA,
            expected_runner_source_sha256=RUNNER_SOURCE_SHA256,
            expected_execution_environment_contract_sha256=(
                ENVIRONMENT_CONTRACT_SHA256
            ),
            expected_result_receipt_contract_sha256=RESULT_CONTRACT_SHA256,
            expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
        )
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="signature verification failed",
    ):
        _verify(
            receipt,
            anchor=AuthorizationOperatorTrustAnchor(OPERATOR_IDENTITY, OTHER_KEY),
        )
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="does not match the trusted key",
    ):
        _verify(
            receipt,
            anchor=AuthorizationOperatorTrustAnchor(
                OTHER_OPERATOR_IDENTITY,
                OPERATOR_KEY,
            ),
        )


def test_authorization_reverifies_signed_review_instead_of_trusting_a_decision_object() -> (
    None
):
    tampered_review = deepcopy(_review_attestation())
    tampered_review["claim_safe"] = True
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="independent review verification failed",
    ):
        _receipt(review_attestation=tampered_review)

    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="independent review verification failed",
    ):
        _receipt(review_attestation=_review_verification())

    receipt = _receipt()
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="independent review verification failed",
    ):
        _verify(
            receipt,
            trusted_reviewer_keys={
                REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                    REVIEWER_IDENTITY,
                    OTHER_KEY,
                )
            },
        )


@pytest.mark.parametrize("colliding_identity", (AUTHOR_IDENTITY, REVIEWER_IDENTITY))
def test_authorization_operator_must_differ_from_author_and_reviewer(
    colliding_identity: str,
) -> None:
    receipt = _receipt(authorization_operator_identity_sha256=colliding_identity)
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="must differ from author and reviewer",
    ):
        _verify(
            receipt,
            anchor=AuthorizationOperatorTrustAnchor(
                colliding_identity,
                OPERATOR_KEY,
            ),
        )


def test_signed_authorization_receipt_enforces_time_and_review_lifetime() -> None:
    receipt = _receipt()
    with pytest.raises(ReferenceValidationAuthorizationError, match="not yet valid"):
        _verify(receipt, checked_at=ISSUED_AT - timedelta(seconds=1))
    with pytest.raises(ReferenceValidationAuthorizationError, match="is expired"):
        _verify(receipt, checked_at=EXPIRES_AT)

    overlong = _receipt(
        expires_at=ISSUED_AT
        + REFERENCE_VALIDATION_AUTHORIZATION_MAX_VALIDITY
        + timedelta(seconds=1)
    )
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="exceeds the frozen maximum",
    ):
        _verify(overlong)

    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="independent review verification failed",
    ):
        _receipt(
            issued_at=REVIEWED_AT - timedelta(seconds=1),
            expires_at=REVIEWED_AT + timedelta(hours=1),
        )

    outlives_review = _receipt(
        issued_at=REVIEW_EXPIRES_AT - timedelta(hours=1),
        expires_at=REVIEW_EXPIRES_AT + timedelta(seconds=1),
    )
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="outlives the independent review",
    ):
        _verify(outlives_review, checked_at=REVIEW_EXPIRES_AT - timedelta(minutes=30))


def test_signed_authorization_receipt_enforces_external_revocation_sets() -> None:
    receipt = _receipt()
    verification = _verify(receipt)
    with pytest.raises(
        ReferenceValidationAuthorizationError, match="receipt is externally revoked"
    ):
        _verify(
            receipt,
            revoked_receipt_sha256s=(verification.receipt_sha256,),
        )
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="review attestation is externally revoked",
    ):
        _verify(
            receipt,
            revoked_review_attestation_sha256s=(
                verification.review_attestation_sha256,
            ),
        )


def test_signed_authorization_receipt_rejects_consumed_nonce() -> None:
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="nonce was already consumed",
    ):
        _verify(
            _receipt(),
            consumed_nonce_sha256s=(AUTHORIZATION_NONCE,),
        )


@pytest.mark.parametrize(
    ("argument", "replacement"),
    (
        ("expected_code_commit_sha", "8" * 40),
        ("expected_runner_source_sha256", "8" * 64),
        ("expected_execution_environment_contract_sha256", "8" * 64),
        ("expected_result_receipt_contract_sha256", "8" * 64),
        ("expected_dependency_artifact_sha256_rows", {"python": "8" * 64}),
    ),
)
def test_signed_authorization_receipt_rejects_expected_dependency_crosswire(
    argument: str,
    replacement: object,
) -> None:
    with pytest.raises(
        ReferenceValidationAuthorizationError,
        match="do not match",
    ):
        _verify(_receipt(), **{argument: replacement})


def test_authorization_trust_anchor_redacts_key_and_rejects_invalid_keys() -> None:
    anchor = AuthorizationOperatorTrustAnchor(OPERATOR_IDENTITY, OPERATOR_KEY)
    assert OPERATOR_KEY.hex() not in repr(anchor)
    with pytest.raises(ReferenceValidationAuthorizationError, match="exactly 32 bytes"):
        AuthorizationOperatorTrustAnchor(OPERATOR_IDENTITY, b"short")
    with pytest.raises(ReferenceValidationAuthorizationError, match="bytes or hex"):
        AuthorizationOperatorTrustAnchor(
            OPERATOR_IDENTITY,
            32,  # type: ignore[arg-type]
        )


def test_authorization_receipt_builder_rejects_invalid_commit_or_dependency_rows() -> (
    None
):
    with pytest.raises(ReferenceValidationAuthorizationError, match="Git SHA"):
        _receipt(code_commit_sha="not-a-commit")
    with pytest.raises(
        ReferenceValidationAuthorizationError, match="non-empty mapping"
    ):
        _receipt(dependency_artifact_sha256_rows={})
