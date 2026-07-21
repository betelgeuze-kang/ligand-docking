from __future__ import annotations

import base64
from copy import deepcopy

import pytest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from betelgeuze_engine_v2.evidence_contracts import (
    EXECUTION_EVIDENCE_VERIFICATION_SCHEMA_ID,
    EvidenceContractError,
    TrustedReviewer,
)
from betelgeuze_engine_v2.evidence_contracts_v3 import (
    RELEASE_REVIEW_ATTESTATION_V3_SCHEMA_ID,
    ReleaseReviewExpectationV3,
    canonical_release_review_attestation_v3_bytes,
    evidence_bound_capability_snapshot_v3,
    verify_release_review_attestation_v3,
)


def _key_pair() -> tuple[Ed25519PrivateKey, bytes]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, public


def _expectation(public_key: bytes, *, duplicate_identity: bool = False):
    numerical_identity = "4" * 64 if duplicate_identity else "5" * 64
    return ReleaseReviewExpectationV3(
        repository_full_name="betelgeuze-kang/ligand-docking",
        pull_request_number=165,
        pull_request_head_sha="a" * 40,
        pull_request_author_identity_sha256="0" * 64,
        ruleset_sha256="1" * 64,
        codeowners_sha256="2" * 64,
        required_check_names=("ci-engine-v2-main", "ci-engine-v2-top-stack"),
        required_roles=(
            "codeowner",
            "numerical_methods",
            "scientific",
            "security",
        ),
        trusted_reviewers={
            "code-owner": TrustedReviewer(
                login="code-owner",
                user_id=101,
                identity_sha256="3" * 64,
                roles=("codeowner",),
            ),
            "security-reviewer": TrustedReviewer(
                login="security-reviewer",
                user_id=102,
                identity_sha256="4" * 64,
                roles=("security",),
            ),
            "numerical-reviewer": TrustedReviewer(
                login="numerical-reviewer",
                user_id=103,
                identity_sha256=numerical_identity,
                roles=("numerical_methods",),
            ),
            "scientific-reviewer": TrustedReviewer(
                login="scientific-reviewer",
                user_id=104,
                identity_sha256="6" * 64,
                roles=("scientific",),
            ),
        },
        trusted_attestor_keys={"github-app-v3": public_key},
        maximum_attestation_age_seconds=3_600,
    )


def _signed_payload(
    private_key: Ed25519PrivateKey,
    expected: ReleaseReviewExpectationV3,
) -> dict[str, object]:
    identities = {
        login: reviewer.identity_sha256
        for login, reviewer in expected.trusted_reviewers.items()
    }
    payload: dict[str, object] = {
        "schema_id": RELEASE_REVIEW_ATTESTATION_V3_SCHEMA_ID,
        "repository_full_name": expected.repository_full_name,
        "pull_request_number": expected.pull_request_number,
        "pull_request_head_sha": expected.pull_request_head_sha,
        "pull_request_author_identity_sha256": (
            expected.pull_request_author_identity_sha256
        ),
        "ruleset_id": "engine-v2-protected",
        "ruleset_sha256": expected.ruleset_sha256,
        "ruleset_snapshot_at_utc": "2026-07-21T12:00:00Z",
        "codeowners_sha256": expected.codeowners_sha256,
        "no_admin_bypass": True,
        "stale_approval_dismissal_enabled": True,
        "code_owner_review_required": True,
        "unresolved_review_thread_count": 0,
        "head_up_to_date": True,
        "review_submissions": [
            {
                "submission_id": 11,
                "reviewer_login": "code-owner",
                "reviewer_user_id": 101,
                "reviewer_identity_sha256": identities["code-owner"],
                "role": "codeowner",
                "state": "APPROVED",
                "reviewed_head_sha": expected.pull_request_head_sha,
                "submitted_at_utc": "2026-07-21T12:01:00Z",
                "dismissed": False,
            },
            {
                "submission_id": 12,
                "reviewer_login": "numerical-reviewer",
                "reviewer_user_id": 103,
                "reviewer_identity_sha256": identities["numerical-reviewer"],
                "role": "numerical_methods",
                "state": "APPROVED",
                "reviewed_head_sha": expected.pull_request_head_sha,
                "submitted_at_utc": "2026-07-21T12:02:00Z",
                "dismissed": False,
            },
            {
                "submission_id": 13,
                "reviewer_login": "scientific-reviewer",
                "reviewer_user_id": 104,
                "reviewer_identity_sha256": identities["scientific-reviewer"],
                "role": "scientific",
                "state": "APPROVED",
                "reviewed_head_sha": expected.pull_request_head_sha,
                "submitted_at_utc": "2026-07-21T12:03:00Z",
                "dismissed": False,
            },
            {
                "submission_id": 14,
                "reviewer_login": "security-reviewer",
                "reviewer_user_id": 102,
                "reviewer_identity_sha256": identities["security-reviewer"],
                "role": "security",
                "state": "APPROVED",
                "reviewed_head_sha": expected.pull_request_head_sha,
                "submitted_at_utc": "2026-07-21T12:04:00Z",
                "dismissed": False,
            },
        ],
        "required_checks": [
            {
                "name": "ci-engine-v2-main",
                "check_run_id": 201,
                "check_suite_id": 301,
                "workflow_run_id": 401,
                "workflow_run_attempt": 1,
                "workflow_source_sha256": "7" * 64,
                "check_head_sha": expected.pull_request_head_sha,
                "event_name": "pull_request",
                "conclusion": "success",
                "completed_at_utc": "2026-07-21T12:05:00Z",
            },
            {
                "name": "ci-engine-v2-top-stack",
                "check_run_id": 202,
                "check_suite_id": 302,
                "workflow_run_id": 402,
                "workflow_run_attempt": 1,
                "workflow_source_sha256": "8" * 64,
                "check_head_sha": expected.pull_request_head_sha,
                "event_name": "pull_request",
                "conclusion": "success",
                "completed_at_utc": "2026-07-21T12:06:00Z",
            },
        ],
        "evidence_generated_at_utc": "2026-07-21T12:07:00Z",
        "attestor_key_id": "github-app-v3",
        "signature_base64": "",
    }
    payload["signature_base64"] = base64.b64encode(
        private_key.sign(canonical_release_review_attestation_v3_bytes(payload))
    ).decode("ascii")
    return payload


def test_v3_verifies_exact_head_distinct_roles_checks_and_freshness() -> None:
    private, public = _key_pair()
    expected = _expectation(public)
    result = verify_release_review_attestation_v3(
        _signed_payload(private, expected),
        expected=expected,
        verified_at_utc="2026-07-21T12:08:00Z",
    )
    assert result["verified_head_sha"] == expected.pull_request_head_sha
    assert result["distinct_reviewer_identity_count"] == 4
    assert result["timestamp_order_verified"] is True
    assert result["freshness_verified"] is True
    assert result["claim_safe"] is False


def test_v3_rejects_review_and_check_head_cross_wiring() -> None:
    private, public = _key_pair()
    expected = _expectation(public)

    review = _signed_payload(private, expected)
    review["review_submissions"][0]["reviewed_head_sha"] = "b" * 40
    with pytest.raises(EvidenceContractError, match="review submission head SHA"):
        verify_release_review_attestation_v3(
            review,
            expected=expected,
            verified_at_utc="2026-07-21T12:08:00Z",
        )

    check = _signed_payload(private, expected)
    check["required_checks"][0]["check_head_sha"] = "b" * 40
    with pytest.raises(EvidenceContractError, match="required check head SHA"):
        verify_release_review_attestation_v3(
            check,
            expected=expected,
            verified_at_utc="2026-07-21T12:08:00Z",
        )


def test_v3_rejects_shared_role_identity_without_explicit_policy() -> None:
    private, public = _key_pair()
    expected = _expectation(public, duplicate_identity=True)
    with pytest.raises(EvidenceContractError, match="distinct identities"):
        verify_release_review_attestation_v3(
            _signed_payload(private, expected),
            expected=expected,
            verified_at_utc="2026-07-21T12:08:00Z",
        )


def test_v3_rejects_timestamp_reversal_and_stale_attestation() -> None:
    private, public = _key_pair()
    expected = _expectation(public)

    reversed_time = _signed_payload(private, expected)
    reversed_time["evidence_generated_at_utc"] = "2026-07-21T12:02:30Z"
    with pytest.raises(EvidenceContractError, match="timestamp order"):
        verify_release_review_attestation_v3(
            reversed_time,
            expected=expected,
            verified_at_utc="2026-07-21T12:08:00Z",
        )

    with pytest.raises(EvidenceContractError, match="stale"):
        verify_release_review_attestation_v3(
            _signed_payload(private, expected),
            expected=expected,
            verified_at_utc="2026-07-21T14:08:00Z",
        )


def test_v3_rejects_unknown_capability_execution_receipts() -> None:
    with pytest.raises(EvidenceContractError, match="unknown capability"):
        evidence_bound_capability_snapshot_v3(
            (
                {
                    "schema_id": EXECUTION_EVIDENCE_VERIFICATION_SCHEMA_ID,
                    "capability_id": "unknown-capability",
                    "signature_verified": True,
                    "evidence_sha256": "9" * 64,
                    "component_tested": True,
                    "canonical_entrypoint_wired": True,
                },
            )
        )
