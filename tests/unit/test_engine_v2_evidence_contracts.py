from __future__ import annotations

import base64
from dataclasses import replace

import pytest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from betelgeuze_engine_v2.evidence_contracts import (
    EXECUTION_EVIDENCE_RECEIPT_SCHEMA_ID,
    RELEASE_REVIEW_ATTESTATION_SCHEMA_ID,
    EvidenceContractError,
    ExecutionEvidenceExpectation,
    ReviewEvidenceExpectation,
    ScopedMetricEvidenceV2,
    TrustedReviewer,
    canonical_execution_evidence_bytes,
    canonical_release_review_attestation_bytes,
    evidence_bound_capability_snapshot,
    require_scoped_metric_evidence_v2,
    verify_execution_evidence_receipt,
    verify_release_review_attestation,
)


def _key_pair() -> tuple[Ed25519PrivateKey, bytes]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, public


def _metric() -> ScopedMetricEvidenceV2:
    return ScopedMetricEvidenceV2(
        scope_id="public-redocking-contract-cohort",
        task_id="top1-pose-recovery",
        dataset_id="posebusters-packaged-fixtures",
        dataset_version="1a5f26aa7270fafba21b7fec8b3633f4c4e45ead",
        split_id="frozen-test-contract-cohort",
        target_family="mixed-public-fixtures",
        scorer_id="bounded-internal-scorer",
        scorer_version="1.0.0",
        engine_commit="a" * 40,
        metric_id="top1-rmsd",
        metric_direction="minimize",
        unit="angstrom",
        value=1.5,
        confidence_interval_low=1.0,
        confidence_interval_high=2.0,
        confidence_level=0.95,
        denominator_count=4,
        success_count=3,
        failure_count=1,
        as_of_utc="2026-07-20T12:00:00Z",
        claim_boundary="Protocol-fixture result only; no scientific or product claim.",
        source_artifact_sha256="1" * 64,
        evaluator_source_sha256="2" * 64,
        metric_implementation_sha256="3" * 64,
        protocol_sha256="4" * 64,
        environment_fingerprint_sha256="5" * 64,
        execution_receipt_sha256="6" * 64,
    )


def test_scoped_metric_v2_round_trip_binds_counts_and_source_identities() -> None:
    row = _metric()
    payload = row.to_dict()
    assert require_scoped_metric_evidence_v2(payload) == row
    assert payload["counts"] == {"denominator": 4, "success": 3, "failure": 1}
    assert payload["metric_direction"] == "minimize"
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False


def test_scoped_metric_v2_rejects_denominator_and_identity_tampering() -> None:
    with pytest.raises(EvidenceContractError, match="must equal denominator"):
        replace(_metric(), success_count=4, failure_count=1)

    tampered = _metric().to_dict()
    tampered["source_artifact_sha256"] = "9" * 64
    with pytest.raises(EvidenceContractError, match="SHA-256"):
        require_scoped_metric_evidence_v2(tampered)


def _review_expectation(public_key: bytes) -> ReviewEvidenceExpectation:
    return ReviewEvidenceExpectation(
        repository_full_name="betelgeuze-kang/ligand-docking",
        pull_request_number=160,
        pull_request_head_sha="a" * 40,
        pull_request_author_identity_sha256="0" * 64,
        ruleset_sha256="1" * 64,
        codeowners_sha256="2" * 64,
        required_check_names=("ci-engine-v2-main", "ci-engine-v2-truthfulness"),
        required_change_categories=("claim_policy", "numerical_methods", "security"),
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
                identity_sha256="5" * 64,
                roles=("numerical_methods",),
            ),
        },
        trusted_attestor_keys={"github-app-key-1": public_key},
    )


def _signed_review_payload(
    private_key: Ed25519PrivateKey,
    expectation: ReviewEvidenceExpectation,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": RELEASE_REVIEW_ATTESTATION_SCHEMA_ID,
        "repository_full_name": expectation.repository_full_name,
        "pull_request_number": expectation.pull_request_number,
        "pull_request_head_sha": expectation.pull_request_head_sha,
        "pull_request_author_identity_sha256": expectation.pull_request_author_identity_sha256,
        "ruleset_id": "ruleset-17",
        "ruleset_sha256": expectation.ruleset_sha256,
        "codeowners_sha256": expectation.codeowners_sha256,
        "no_admin_bypass": True,
        "stale_approval_dismissal_enabled": True,
        "code_owner_review_required": True,
        "unresolved_review_thread_count": 0,
        "head_up_to_date": True,
        "change_categories": list(expectation.required_change_categories),
        "review_submissions": [
            {
                "submission_id": 11,
                "reviewer_login": "code-owner",
                "reviewer_user_id": 101,
                "reviewer_identity_sha256": "3" * 64,
                "role": "codeowner",
                "state": "APPROVED",
                "submitted_at_utc": "2026-07-20T12:01:00Z",
                "dismissed": False,
            },
            {
                "submission_id": 12,
                "reviewer_login": "security-reviewer",
                "reviewer_user_id": 102,
                "reviewer_identity_sha256": "4" * 64,
                "role": "security",
                "state": "APPROVED",
                "submitted_at_utc": "2026-07-20T12:02:00Z",
                "dismissed": False,
            },
            {
                "submission_id": 13,
                "reviewer_login": "numerical-reviewer",
                "reviewer_user_id": 103,
                "reviewer_identity_sha256": "5" * 64,
                "role": "numerical_methods",
                "state": "APPROVED",
                "submitted_at_utc": "2026-07-20T12:03:00Z",
                "dismissed": False,
            },
        ],
        "required_checks": [
            {
                "name": "ci-engine-v2-main",
                "check_run_id": 201,
                "workflow_source_sha256": "6" * 64,
                "conclusion": "success",
                "completed_at_utc": "2026-07-20T12:04:00Z",
            },
            {
                "name": "ci-engine-v2-truthfulness",
                "check_run_id": 202,
                "workflow_source_sha256": "7" * 64,
                "conclusion": "success",
                "completed_at_utc": "2026-07-20T12:05:00Z",
            },
        ],
        "evidence_generated_at_utc": "2026-07-20T12:06:00Z",
        "attestor_key_id": "github-app-key-1",
        "signature_base64": "",
    }
    payload["signature_base64"] = base64.b64encode(
        private_key.sign(canonical_release_review_attestation_bytes(payload))
    ).decode("ascii")
    return payload


def test_review_attestation_requires_expected_context_directory_and_signature() -> None:
    private, public = _key_pair()
    expectation = _review_expectation(public)
    result = verify_release_review_attestation(
        _signed_review_payload(private, expectation), expected=expectation
    )
    assert result["expected_context_verified"] is True
    assert result["signature_verified"] is True
    assert result["operational_review_evidence_verified"] is True
    assert result["scientific_validation_granted"] is False
    assert result["claim_safe"] is False


def test_review_attestation_rejects_cross_wiring_untrusted_roles_and_signature() -> None:
    private, public = _key_pair()
    expectation = _review_expectation(public)

    wrong_head = _signed_review_payload(private, expectation)
    wrong_head["pull_request_head_sha"] = "b" * 40
    with pytest.raises(EvidenceContractError, match="head SHA is cross-wired"):
        verify_release_review_attestation(wrong_head, expected=expectation)

    wrong_role = _signed_review_payload(private, expectation)
    wrong_role["review_submissions"][1]["role"] = "codeowner"
    with pytest.raises(EvidenceContractError, match="not trusted"):
        verify_release_review_attestation(wrong_role, expected=expectation)

    bad_signature = _signed_review_payload(private, expectation)
    bad_signature["signature_base64"] = base64.b64encode(b"x" * 64).decode("ascii")
    with pytest.raises(EvidenceContractError, match="signature verification"):
        verify_release_review_attestation(bad_signature, expected=expectation)


def _execution_expectation(public_key: bytes) -> ExecutionEvidenceExpectation:
    return ExecutionEvidenceExpectation(
        capability_id="v2_cpu_reference_minimization_validation_protocol",
        engine_commit="a" * 40,
        source_manifest_sha256="1" * 64,
        test_manifest_sha256="2" * 64,
        canonical_argv=("python", "-m", "betelgeuze_engine_v2.validation"),
        entrypoint_source_sha256="3" * 64,
        environment_fingerprint_sha256="4" * 64,
        trusted_attestor_keys={"ci-attestor-1": public_key},
    )


def _signed_execution_payload(
    private_key: Ed25519PrivateKey,
    expectation: ExecutionEvidenceExpectation,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": EXECUTION_EVIDENCE_RECEIPT_SCHEMA_ID,
        "capability_id": expectation.capability_id,
        "engine_commit": expectation.engine_commit,
        "source_manifest_sha256": expectation.source_manifest_sha256,
        "test_manifest_sha256": expectation.test_manifest_sha256,
        "test_count": 14,
        "failure_count": 0,
        "canonical_argv": list(expectation.canonical_argv),
        "entrypoint_source_sha256": expectation.entrypoint_source_sha256,
        "entrypoint_exit_code": 0,
        "environment_fingerprint_sha256": expectation.environment_fingerprint_sha256,
        "completed_at_utc": "2026-07-20T12:10:00Z",
        "attestor_key_id": "ci-attestor-1",
        "signature_base64": "",
    }
    payload["signature_base64"] = base64.b64encode(
        private_key.sign(canonical_execution_evidence_bytes(payload))
    ).decode("ascii")
    return payload


def test_execution_evidence_drives_tested_and_wired_state() -> None:
    private, public = _key_pair()
    expectation = _execution_expectation(public)
    verification = verify_execution_evidence_receipt(
        _signed_execution_payload(private, expectation), expected=expectation
    )
    assert verification["component_tested"] is True
    assert verification["canonical_entrypoint_wired"] is True
    assert verification["production_execution_authorized"] is False

    snapshot = evidence_bound_capability_snapshot((verification,))
    row = snapshot["capabilities"][expectation.capability_id]
    assert row["component_tested"] is True
    assert row["canonical_entrypoint_wired"] is True
    assert row["execution_evidence_sha256"] == verification["evidence_sha256"]
    assert snapshot["claim_safe"] is False


def test_execution_evidence_rejects_failures_cross_wiring_and_bad_signature() -> None:
    private, public = _key_pair()
    expectation = _execution_expectation(public)

    failed = _signed_execution_payload(private, expectation)
    failed["failure_count"] = 1
    with pytest.raises(EvidenceContractError, match="test failures"):
        verify_execution_evidence_receipt(failed, expected=expectation)

    wrong_commit = _signed_execution_payload(private, expectation)
    wrong_commit["engine_commit"] = "b" * 40
    with pytest.raises(EvidenceContractError, match="engine commit is cross-wired"):
        verify_execution_evidence_receipt(wrong_commit, expected=expectation)

    bad_signature = _signed_execution_payload(private, expectation)
    bad_signature["signature_base64"] = base64.b64encode(b"z" * 64).decode("ascii")
    with pytest.raises(EvidenceContractError, match="signature verification"):
        verify_execution_evidence_receipt(bad_signature, expected=expectation)


def test_evidence_bound_snapshot_does_not_trust_source_declarations_without_receipt() -> None:
    snapshot = evidence_bound_capability_snapshot(())
    assert snapshot["verified_execution_evidence_count"] == 0
    assert all(
        row["component_tested"] is False
        and row["canonical_entrypoint_wired"] is False
        and row["execution_evidence_sha256"] == ""
        for row in snapshot["capabilities"].values()
    )
