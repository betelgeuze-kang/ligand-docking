from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from betelgeuze_engine_v2.physics.reference_validation_artifact_binding import (
    FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256,
    REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID,
    REFERENCE_VALIDATION_REVIEW_CONTRACT_SCHEMA_ID,
    REFERENCE_VALIDATION_REVIEW_MAX_VALIDITY,
    REFERENCE_VALIDATION_REVIEW_SIGNATURE_ALGORITHM,
    ReferenceValidationReviewError,
    ScientificReviewerTrustAnchor,
    build_signed_reference_validation_review_attestation,
    reference_validation_review_contract_authorization_decision,
    reference_validation_review_contract_document,
    require_reference_validation_review_contract_document,
    verify_signed_reference_validation_review_attestation,
)


AUTHOR_IDENTITY = "a" * 64
REVIEWER_IDENTITY = "b" * 64
OTHER_REVIEWER_IDENTITY = "c" * 64
NONCE_SHA256 = "d" * 64
KEY_ID = "independent-reviewer-2026-07"
REVIEW_KEY = b"review-key-material-is-test-only-32-bytes-minimum"
OTHER_KEY = b"other-key-material-is-test-only-32-bytes-minimum"
REVIEWED_AT = datetime(2026, 7, 17, 4, 0, 0, tzinfo=timezone.utc)
EXPIRES_AT = REVIEWED_AT + timedelta(days=7)
CHECKED_AT = REVIEWED_AT + timedelta(hours=1)


def _anchor(
    *,
    identity: str = REVIEWER_IDENTITY,
    key: bytes = REVIEW_KEY,
) -> ScientificReviewerTrustAnchor:
    return ScientificReviewerTrustAnchor(
        reviewer_identity_sha256=identity,
        verification_key=key,
    )


def _attestation(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "implementation_author_identity_sha256": AUTHOR_IDENTITY,
        "independent_reviewer_identity_sha256": REVIEWER_IDENTITY,
        "reviewer_key_id": KEY_ID,
        "signing_key": REVIEW_KEY,
        "reviewed_at": REVIEWED_AT,
        "expires_at": EXPIRES_AT,
        "nonce_sha256": NONCE_SHA256,
    }
    values.update(overrides)
    return build_signed_reference_validation_review_attestation(**values)  # type: ignore[arg-type]


def _verify(
    source: object,
    *,
    anchor: ScientificReviewerTrustAnchor | None = None,
    author_identity: str = AUTHOR_IDENTITY,
    checked_at: datetime = CHECKED_AT,
):
    return verify_signed_reference_validation_review_attestation(
        source,  # type: ignore[arg-type]
        trusted_reviewer_keys={KEY_ID: anchor or _anchor()},
        expected_implementation_author_identity_sha256=author_identity,
        checked_at=checked_at,
    )


def test_review_contract_is_frozen_dependency_bound_and_result_free() -> None:
    first = reference_validation_review_contract_document()
    second = reference_validation_review_contract_document()

    assert first == second
    assert first["schema_id"] == REFERENCE_VALIDATION_REVIEW_CONTRACT_SCHEMA_ID
    assert first["contract_sha256"] == FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256
    assert (
        first["dependencies"]["artifact_binding_sha256"]
        == FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256
    )
    assert first["purpose"] == {
        "scope": "future_independent_review_of_cpu_validation_implementation_artifacts",
        "contract_definition_only": True,
        "review_attestation_present": False,
        "authorizes_validation_execution": False,
        "authorizes_parameter_fitting_proposal": False,
        "authorizes_parameter_fitting": False,
    }
    assert first["identity_policy"]["implementation_author_and_reviewer_must_differ"] is True
    assert first["identity_policy"]["trusted_reviewer_key_supplied_out_of_band"] is True
    assert first["identity_policy"]["repository_does_not_choose_or_bundle_trusted_reviewer_keys"] is True
    assert first["authorization_gate"]["status"] == "closed"
    assert first["authorization_gate"]["independent_scientific_review_completed"] is False
    assert first["authorization_gate"]["validation_execution_authorized"] is False
    assert first["claim_policy"]["scientifically_validated"] is False
    assert first["claim_policy"]["claim_safe"] is False
    assert require_reference_validation_review_contract_document(first) == first


def test_review_contract_rejects_tamper() -> None:
    document = reference_validation_review_contract_document()
    tampered = deepcopy(document)
    tampered["authorization_gate"]["validation_execution_authorized"] = True
    with pytest.raises(
        ReferenceValidationReviewError,
        match="does not match the frozen record",
    ):
        require_reference_validation_review_contract_document(tampered)


def test_signed_review_attestation_verifies_exact_scope_and_stays_non_authorizing() -> None:
    attestation = _attestation()
    verification = _verify(attestation)

    assert attestation["schema_id"] == REFERENCE_VALIDATION_REVIEW_ATTESTATION_SCHEMA_ID
    assert attestation["artifact_binding_sha256"] == FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256
    assert attestation["signature"]["algorithm"] == REFERENCE_VALIDATION_REVIEW_SIGNATURE_ALGORITHM
    assert len(attestation["attestation_sha256"]) == 64
    assert verification.independent_scientific_review_verified is True
    assert verification.implementation_author_separation_verified is True
    assert verification.validation_execution_authorized is False
    assert verification.parameter_fitting_proposal_authorized is False
    assert verification.parameter_fitting_authorized is False
    assert "signed_execution_authorization_receipt_missing" in verification.blockers
    assert "validation_execution_not_authorized" in verification.blockers
    assert attestation["scientific_parameterized_force_field_validation_recommended"] is False
    assert attestation["parameter_fitting_proposal_recommended"] is False
    assert attestation["parameter_fitting_recommended"] is False
    assert attestation["validation_execution_authorized"] is False
    assert attestation["scientifically_validated"] is False
    assert attestation["claim_safe"] is False


def test_signed_review_attestation_accepts_canonical_json_bytes() -> None:
    import json

    attestation = _attestation()
    encoded = json.dumps(attestation, sort_keys=True, allow_nan=False).encode("utf-8")
    assert _verify(encoded).attestation_sha256 == attestation["attestation_sha256"]


def test_signed_review_attestation_rejects_duplicate_json_or_signature_fields() -> None:
    duplicate = b'{"schema_id":"first","schema_id":"second"}'
    with pytest.raises(ReferenceValidationReviewError, match="duplicate JSON key"):
        _verify(duplicate)

    attestation = deepcopy(_attestation())
    signature = attestation["signature"]
    assert isinstance(signature, dict)
    signature["unexpected"] = False
    with pytest.raises(ReferenceValidationReviewError, match="signature fields"):
        _verify(attestation)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    (
        ("artifact_binding_sha256", "e" * 64, "signature verification failed"),
        ("claim_safe", True, "signature verification failed"),
        ("revoked", True, "signature verification failed"),
        ("review_recommendation", "authorize_execution", "signature verification failed"),
    ),
)
def test_signed_review_attestation_rejects_unsigned_tamper(
    field: str,
    replacement: object,
    message: str,
) -> None:
    tampered = deepcopy(_attestation())
    tampered[field] = replacement
    with pytest.raises(ReferenceValidationReviewError, match=message):
        _verify(tampered)


def test_signed_review_attestation_rejects_untrusted_or_mismatched_keys() -> None:
    attestation = _attestation()
    with pytest.raises(ReferenceValidationReviewError, match="not trusted"):
        verify_signed_reference_validation_review_attestation(
            attestation,
            trusted_reviewer_keys={},
            expected_implementation_author_identity_sha256=AUTHOR_IDENTITY,
            checked_at=CHECKED_AT,
        )
    with pytest.raises(ReferenceValidationReviewError, match="signature verification failed"):
        _verify(attestation, anchor=_anchor(key=OTHER_KEY))
    with pytest.raises(ReferenceValidationReviewError, match="does not match the trusted key"):
        _verify(attestation, anchor=_anchor(identity=OTHER_REVIEWER_IDENTITY))


def test_signed_review_attestation_rejects_author_reviewer_identity_collision() -> None:
    attestation = _attestation(
        independent_reviewer_identity_sha256=AUTHOR_IDENTITY,
    )
    with pytest.raises(
        ReferenceValidationReviewError,
        match="implementation author and independent reviewer must differ",
    ):
        _verify(attestation, anchor=_anchor(identity=AUTHOR_IDENTITY))


def test_signed_review_attestation_rejects_author_crosswire() -> None:
    with pytest.raises(
        ReferenceValidationReviewError,
        match="implementation author identity drifted",
    ):
        _verify(_attestation(), author_identity="f" * 64)


def test_signed_review_attestation_rejects_incomplete_or_reordered_scope() -> None:
    contract = reference_validation_review_contract_document()
    required_checks = contract["attestation_schema"]["required_review_check_ids"]
    required_limitations = contract["attestation_schema"]["required_limitation_ids"]

    missing = _attestation(accepted_check_ids=required_checks[:-1])
    with pytest.raises(ReferenceValidationReviewError, match="check coverage"):
        _verify(missing)

    reordered = _attestation(acknowledged_limitation_ids=list(reversed(required_limitations)))
    with pytest.raises(ReferenceValidationReviewError, match="limitations"):
        _verify(reordered)


def test_signed_review_attestation_enforces_freshness_window() -> None:
    with pytest.raises(ReferenceValidationReviewError, match="not yet valid"):
        _verify(_attestation(), checked_at=REVIEWED_AT - timedelta(seconds=1))
    with pytest.raises(ReferenceValidationReviewError, match="expired"):
        _verify(_attestation(), checked_at=EXPIRES_AT)

    overlong = _attestation(
        expires_at=REVIEWED_AT + REFERENCE_VALIDATION_REVIEW_MAX_VALIDITY + timedelta(seconds=1),
    )
    with pytest.raises(ReferenceValidationReviewError, match="exceeds the frozen maximum"):
        _verify(overlong)

    inverted = _attestation(expires_at=REVIEWED_AT)
    with pytest.raises(ReferenceValidationReviewError, match="expiry must follow"):
        _verify(inverted, checked_at=REVIEWED_AT)


def test_review_trust_anchor_redacts_key_from_repr_and_rejects_short_key() -> None:
    anchor = _anchor()
    assert "review-key-material" not in repr(anchor)
    with pytest.raises(ReferenceValidationReviewError, match="at least 32 bytes"):
        ScientificReviewerTrustAnchor(
            reviewer_identity_sha256=REVIEWER_IDENTITY,
            verification_key=b"short",
        )
    with pytest.raises(ReferenceValidationReviewError, match="bytes or text"):
        ScientificReviewerTrustAnchor(
            reviewer_identity_sha256=REVIEWER_IDENTITY,
            verification_key=32,  # type: ignore[arg-type]
        )


def test_current_review_decision_remains_closed_without_committed_attestation() -> None:
    decision = reference_validation_review_contract_authorization_decision()
    assert decision["contract_sha256"] == FROZEN_REFERENCE_VALIDATION_REVIEW_CONTRACT_SHA256
    assert decision["review_attestation_present"] is False
    assert decision["independent_scientific_review_verified"] is False
    assert decision["implementation_author_separation_verified"] is False
    assert decision["validation_execution_authorized"] is False
    assert decision["parameter_fitting_proposal_authorized"] is False
    assert decision["parameter_fitting_authorized"] is False
    assert "signed_independent_scientific_review_attestation_missing" in decision["blockers"]
    assert "signed_execution_authorization_receipt_schema_not_frozen" in decision["blockers"]
