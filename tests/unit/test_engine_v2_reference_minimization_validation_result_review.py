from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_authorization import (
    MinimizationAuthorizationOperatorTrustAnchor,
    build_signed_reference_minimization_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_result_review import (
    EXPECTED_FAIL_CLOSED_OUTCOME_ACCEPTED,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID,
    REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID,
    RESULT_REVIEW_OUTCOME_ACCEPTED,
    RESULT_REVIEW_OUTCOME_REJECTED,
    REQUIRED_RESULT_EVIDENCE_REJECTED,
    RETAINED_METRIC_VALUE_REJECTED,
    MinimizationResultReviewerTrustAnchor,
    ReferenceMinimizationValidationResultReviewError,
    build_signed_reference_minimization_validation_result_review_attestation,
    reference_minimization_validation_result_review_contract_decision,
    reference_minimization_validation_result_review_contract_document,
    require_reference_minimization_validation_result_review_contract_document,
    verify_signed_reference_minimization_validation_result_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_review import (
    MinimizationScientificReviewerTrustAnchor,
    build_signed_reference_minimization_validation_review_attestation,
)
from tests.unit import (
    test_engine_v2_reference_minimization_validation_result_writer as writer_helpers,
)


RESULT_REVIEWER_IDENTITY = "f" * 64
OTHER_RESULT_REVIEWER_IDENTITY = "0" * 64
RESULT_REVIEW_KEY_ID = "independent-result-reviewer-2026-07"
RESULT_REVIEW_KEY = bytes.fromhex("21" * 32)
OTHER_RESULT_REVIEW_KEY = bytes.fromhex("22" * 32)
RESULT_REVIEW_PUBLIC_KEY = ed25519_public_key_bytes(RESULT_REVIEW_KEY)
OTHER_RESULT_REVIEW_PUBLIC_KEY = ed25519_public_key_bytes(OTHER_RESULT_REVIEW_KEY)
RESULT_REVIEW_NONCE = "a" * 64
UPSTREAM_REVIEW_NONCE = "b" * 64
UPSTREAM_REVIEW_KEY_ID = "scientific-reviewer-2026-07"
UPSTREAM_OPERATOR_KEY_ID = "authorization-operator-2026-07"
UPSTREAM_REVIEW_KEY = bytes.fromhex("31" * 32)
UPSTREAM_OPERATOR_KEY = bytes.fromhex("41" * 32)
UPSTREAM_REVIEW_PUBLIC_KEY = ed25519_public_key_bytes(UPSTREAM_REVIEW_KEY)
UPSTREAM_OPERATOR_PUBLIC_KEY = ed25519_public_key_bytes(UPSTREAM_OPERATOR_KEY)
REVIEWED_AT = writer_helpers.FINAL_NOW + timedelta(minutes=1)
EXPIRES_AT = REVIEWED_AT + timedelta(days=7)
CHECKED_AT = REVIEWED_AT + timedelta(hours=1)


class _ResultEvidence(dict[str, object]):
    def __init__(
        self,
        result_receipt: dict[str, object],
        *,
        pre_execution_review_attestation: dict[str, object],
        authorization_receipt: dict[str, object],
    ) -> None:
        super().__init__(result_receipt)
        self.pre_execution_review_attestation = pre_execution_review_attestation
        self.authorization_receipt = authorization_receipt

    @property
    def trusted_scientific_reviewer_keys(
        self,
    ) -> dict[str, MinimizationScientificReviewerTrustAnchor]:
        return {
            UPSTREAM_REVIEW_KEY_ID: MinimizationScientificReviewerTrustAnchor(
                writer_helpers.REVIEWER_IDENTITY_SHA256,
                UPSTREAM_REVIEW_PUBLIC_KEY,
            )
        }

    @property
    def trusted_authorization_operator_keys(
        self,
    ) -> dict[str, MinimizationAuthorizationOperatorTrustAnchor]:
        return {
            UPSTREAM_OPERATOR_KEY_ID: MinimizationAuthorizationOperatorTrustAnchor(
                writer_helpers.OPERATOR_IDENTITY_SHA256,
                UPSTREAM_OPERATOR_PUBLIC_KEY,
            )
        }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _rehash_receipt(payload: dict[str, object]) -> dict[str, object]:
    payload.pop("receipt_sha256", None)
    payload["receipt_sha256"] = _sha256(payload)
    return payload


def _tampered_first_case_receipt(
    result_receipt: _ResultEvidence,
    **updates: object,
) -> _ResultEvidence:
    tampered = deepcopy(result_receipt)
    run_observation = tampered["run_observation"]
    assert isinstance(run_observation, dict)
    observed_cases = run_observation["case_results"]
    assert isinstance(observed_cases, list)
    first_case = observed_cases[0]
    assert isinstance(first_case, dict)
    first_case.update(updates)
    tampered["case_results"] = deepcopy(observed_cases)
    tampered["observation_sha256"] = _sha256(run_observation)
    return _rehash_receipt(tampered)  # type: ignore[return-value]


@pytest.fixture(scope="module")
def result_receipt(tmp_path_factory: pytest.TempPathFactory) -> _ResultEvidence:
    monkeypatch = pytest.MonkeyPatch()
    try:
        upstream_reviewed_at = writer_helpers.RUN_NOW - timedelta(hours=2)
        upstream_review_expires_at = writer_helpers.RUN_NOW + timedelta(days=7)
        pre_execution_review = (
            build_signed_reference_minimization_validation_review_attestation(
                implementation_author_identity_sha256=(
                    writer_helpers.AUTHOR_IDENTITY_SHA256
                ),
                independent_reviewer_identity_sha256=(
                    writer_helpers.REVIEWER_IDENTITY_SHA256
                ),
                reviewer_key_id=UPSTREAM_REVIEW_KEY_ID,
                signing_key=UPSTREAM_REVIEW_KEY,
                reviewed_at=upstream_reviewed_at,
                expires_at=upstream_review_expires_at,
                nonce_sha256=UPSTREAM_REVIEW_NONCE,
            )
        )
        authorization = build_signed_reference_minimization_validation_authorization_receipt(
            review_attestation=pre_execution_review,
            trusted_reviewer_keys={
                UPSTREAM_REVIEW_KEY_ID: MinimizationScientificReviewerTrustAnchor(
                    writer_helpers.REVIEWER_IDENTITY_SHA256,
                    UPSTREAM_REVIEW_PUBLIC_KEY,
                )
            },
            expected_implementation_author_identity_sha256=(
                writer_helpers.AUTHOR_IDENTITY_SHA256
            ),
            authorization_operator_identity_sha256=(
                writer_helpers.OPERATOR_IDENTITY_SHA256
            ),
            authorization_key_id=UPSTREAM_OPERATOR_KEY_ID,
            signing_key=UPSTREAM_OPERATOR_KEY,
            issued_at=writer_helpers.RUN_NOW - timedelta(hours=1),
            expires_at=writer_helpers.RUN_NOW + timedelta(hours=4),
            authorization_nonce_sha256=writer_helpers.AUTHORIZATION_NONCE,
            code_commit_sha=writer_helpers.CODE_COMMIT_SHA,
            runner_source_sha256=(
                writer_helpers.reference_minimization_validation_runner_source_sha256()
            ),
            dependency_artifact_sha256_rows=writer_helpers.DEPENDENCY_ROWS,
        )
        parent = tmp_path_factory.mktemp("minimization-result-review")
        root = writer_helpers._private_root(Path(parent))
        environment = writer_helpers._environment(
            root,
            review_attestation_sha256=pre_execution_review["attestation_sha256"],
            authorization_receipt_sha256=authorization["receipt_sha256"],
        )
        observation = writer_helpers._observation(
            root,
            monkeypatch,
            environment=environment,
        )
        writer_helpers._install_verified_chain(
            monkeypatch,
            environment,
            review=writer_helpers._review(
                attestation_sha256=pre_execution_review["attestation_sha256"],
                reviewed_at_utc=upstream_reviewed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
            authorization=writer_helpers._authorization(
                receipt_sha256=authorization["receipt_sha256"],
                review_attestation_sha256=pre_execution_review["attestation_sha256"],
            ),
        )
        yield _ResultEvidence(
            writer_helpers._write(root, observation).to_dict(),
            pre_execution_review_attestation=pre_execution_review,
            authorization_receipt=authorization,
        )
    finally:
        monkeypatch.undo()


def _anchor(
    *,
    identity: str = RESULT_REVIEWER_IDENTITY,
    public_key: bytes = RESULT_REVIEW_PUBLIC_KEY,
) -> MinimizationResultReviewerTrustAnchor:
    return MinimizationResultReviewerTrustAnchor(
        result_reviewer_identity_sha256=identity,
        verification_key=public_key,
    )


def _attestation(
    result_receipt: _ResultEvidence,
    **overrides: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "result_receipt": result_receipt,
        "pre_execution_review_attestation": (
            result_receipt.pre_execution_review_attestation
        ),
        "authorization_receipt": result_receipt.authorization_receipt,
        "trusted_scientific_reviewer_keys": (
            result_receipt.trusted_scientific_reviewer_keys
        ),
        "trusted_authorization_operator_keys": (
            result_receipt.trusted_authorization_operator_keys
        ),
        "implementation_author_identity_sha256": (
            writer_helpers.AUTHOR_IDENTITY_SHA256
        ),
        "independent_scientific_reviewer_identity_sha256": (
            writer_helpers.REVIEWER_IDENTITY_SHA256
        ),
        "authorization_operator_identity_sha256": (
            writer_helpers.OPERATOR_IDENTITY_SHA256
        ),
        "independent_result_reviewer_identity_sha256": RESULT_REVIEWER_IDENTITY,
        "result_reviewer_key_id": RESULT_REVIEW_KEY_ID,
        "signing_key": RESULT_REVIEW_KEY,
        "reviewed_at": REVIEWED_AT,
        "expires_at": EXPIRES_AT,
        "nonce_sha256": RESULT_REVIEW_NONCE,
        "revoked_pre_execution_review_attestation_sha256s": (),
        "revoked_authorization_receipt_sha256s": (),
        "revoked_execution_environment_receipt_sha256s": (),
        "revoked_result_receipt_sha256s": (),
        "superseded_result_receipt_sha256s": (),
    }
    values.update(overrides)
    return build_signed_reference_minimization_validation_result_review_attestation(  # type: ignore[arg-type]
        **values
    )


def _verify(
    source: object,
    result_receipt: _ResultEvidence,
    **overrides: object,
):
    values: dict[str, object] = {
        "result_receipt": result_receipt,
        "pre_execution_review_attestation": (
            result_receipt.pre_execution_review_attestation
        ),
        "authorization_receipt": result_receipt.authorization_receipt,
        "trusted_scientific_reviewer_keys": (
            result_receipt.trusted_scientific_reviewer_keys
        ),
        "trusted_authorization_operator_keys": (
            result_receipt.trusted_authorization_operator_keys
        ),
        "expected_result_receipt_sha256": result_receipt["receipt_sha256"],
        "trusted_result_reviewer_keys": {
            RESULT_REVIEW_KEY_ID: _anchor(),
        },
        "expected_implementation_author_identity_sha256": (
            writer_helpers.AUTHOR_IDENTITY_SHA256
        ),
        "expected_independent_scientific_reviewer_identity_sha256": (
            writer_helpers.REVIEWER_IDENTITY_SHA256
        ),
        "expected_authorization_operator_identity_sha256": (
            writer_helpers.OPERATOR_IDENTITY_SHA256
        ),
        "checked_at": CHECKED_AT,
        "revoked_pre_execution_review_attestation_sha256s": (),
        "revoked_authorization_receipt_sha256s": (),
        "revoked_execution_environment_receipt_sha256s": (),
        "revoked_result_receipt_sha256s": (),
        "superseded_result_receipt_sha256s": (),
        "revoked_result_review_attestation_sha256s": (),
        "superseded_result_review_attestation_sha256s": (),
    }
    values.update(overrides)
    return verify_signed_reference_minimization_validation_result_review_attestation(  # type: ignore[arg-type]
        source,
        **values,
    )


def _rejected_result_receipt(
    result_receipt: dict[str, object],
) -> dict[str, object]:
    rejected = deepcopy(result_receipt)
    run_observation = rejected["run_observation"]
    assert isinstance(run_observation, dict)
    case_results = run_observation["case_results"]
    assert isinstance(case_results, list)
    first_case = case_results[0]
    assert isinstance(first_case, dict)
    metric_values = first_case["metric_values"]
    assert isinstance(metric_values, list)
    first_metric = metric_values[0]
    assert isinstance(first_metric, dict)
    first_metric["value"] = -1.0
    first_case["case_passed"] = False
    coverage = run_observation["coverage_summary"]
    assert isinstance(coverage, dict)
    coverage["all_cases_passed"] = False
    coverage["failed_case_count"] = 1
    rejected["case_results"] = deepcopy(case_results)
    rejected["coverage_summary"] = deepcopy(coverage)
    rejected["observation_sha256"] = _sha256(run_observation)
    return _rehash_receipt(rejected)


def test_result_review_contract_is_frozen_complete_and_closed() -> None:
    first = reference_minimization_validation_result_review_contract_document()
    second = reference_minimization_validation_result_review_contract_document()
    decision = reference_minimization_validation_result_review_contract_decision()

    assert first == second
    assert first["schema_id"] == (
        REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SCHEMA_ID
    )
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_CONTRACT_SHA256
    )
    assert (
        first["dependencies"]["full_result_writer_receipt_validation_required"] is True
    )
    assert first["attestation_schema"]["review_outcomes"] == [
        RESULT_REVIEW_OUTCOME_ACCEPTED,
        RESULT_REVIEW_OUTCOME_REJECTED,
    ]
    assert (
        first["attestation_schema"]["verified_review_does_not_imply_result_acceptance"]
        is True
    )
    assert len(first["case_review_template"]) == 14
    assert (
        sum(
            row["expected_outcome"] == "fail_closed"
            for row in first["case_review_template"]
        )
        == 6
    )
    assert (
        require_reference_minimization_validation_result_review_contract_document(first)
        == first
    )
    assert decision["result_review_attestation_present"] is False
    assert decision["independent_result_review_verified"] is False
    assert decision["result_receipt_review_outcome"] is None
    assert decision["result_receipt_accepted"] is False
    assert "production_result_receipt_missing" in decision["blockers"]
    assert "two_cpu_host_reproducibility_missing" in decision["blockers"]


def test_signed_accepted_review_verifies_exact_receipt_and_all_rows(
    result_receipt: dict[str, object],
) -> None:
    attestation = _attestation(result_receipt)
    verification = _verify(attestation, result_receipt)

    assert attestation["schema_id"] == (
        REFERENCE_MINIMIZATION_VALIDATION_RESULT_REVIEW_ATTESTATION_SCHEMA_ID
    )
    assert attestation["result_receipt_sha256"] == result_receipt["receipt_sha256"]
    assert (
        attestation["result_receipt_review_outcome"] == RESULT_REVIEW_OUTCOME_ACCEPTED
    )
    assert attestation["result_receipt_accepted"] is True
    rows = attestation["case_review_rows"]
    assert isinstance(rows, list)
    assert len(rows) == 14
    assert rows[0]["observed_status"] == "max_iterations_reached"
    assert rows[0]["metric_dispositions"][0]["value"] == 1.0
    assert rows[0]["metric_dispositions"][0]["threshold_value"] == 1.0
    assert rows[0]["accepted_energy_ledger_length"] > 1
    assert len(rows[0]["accepted_energy_ledger_sha256"]) == 64
    assert rows[0]["result_evidence_rejection_reasons"] == []
    assert len(rows[0]["runtime_input_sha256"]) == 64
    assert len(rows[0]["independent_oracle_input_sha256"]) == 64
    assert all(
        row["failure_disposition"] == EXPECTED_FAIL_CLOSED_OUTCOME_ACCEPTED
        for row in rows
        if row["expected_outcome"] == "fail_closed"
    )
    assert verification.independent_result_review_verified is True
    assert verification.implementation_author_separation_verified is True
    assert verification.result_receipt_review_outcome == RESULT_REVIEW_OUTCOME_ACCEPTED
    assert verification.result_receipt_accepted is True
    assert verification.scientifically_validated is False
    assert verification.parameter_fitting_authorized is False
    assert "independent_result_review_missing" in verification.blockers
    assert "coordinate_trace_not_retained_in_result_receipt" in verification.blockers
    assert verification.to_dict()["result_receipt_accepted"] is True


def test_signed_rejected_review_is_verified_without_accepting_the_result(
    result_receipt: dict[str, object],
) -> None:
    rejected_receipt = _rejected_result_receipt(result_receipt)
    attestation = _attestation(rejected_receipt)
    verification = _verify(attestation, rejected_receipt)

    assert (
        attestation["result_receipt_review_outcome"] == RESULT_REVIEW_OUTCOME_REJECTED
    )
    assert attestation["result_receipt_accepted"] is False
    rows = attestation["case_review_rows"]
    assert isinstance(rows, list)
    assert rows[0]["case_passed"] is False
    assert rows[0]["metric_dispositions"][0]["disposition"] == (
        RETAINED_METRIC_VALUE_REJECTED
    )
    assert verification.independent_result_review_verified is True
    assert verification.result_receipt_review_outcome == RESULT_REVIEW_OUTCOME_REJECTED
    assert verification.result_receipt_accepted is False
    assert "result_receipt_review_rejected" in verification.blockers
    assert "scientific_validation_missing" in verification.blockers


def test_builder_rejects_digest_valid_receipt_that_violates_writer_claim_policy(
    result_receipt: dict[str, object],
) -> None:
    tampered = deepcopy(result_receipt)
    tampered["claim_safe"] = True
    _rehash_receipt(tampered)

    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="full result-writer contract validation",
    ):
        _attestation(tampered)


def test_builder_rejects_caller_authored_disposition_and_role_crosswiring(
    result_receipt: dict[str, object],
) -> None:
    rows = deepcopy(_attestation(result_receipt)["case_review_rows"])
    assert isinstance(rows, list)
    rows[0]["metric_dispositions"][0]["disposition"] = RETAINED_METRIC_VALUE_REJECTED
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="contradict the result receipt",
    ):
        _attestation(result_receipt, case_review_rows=rows)

    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="upstream signed-chain roles or identities are cross-wired",
    ):
        _attestation(
            result_receipt,
            independent_scientific_reviewer_identity_sha256="1" * 64,
        )

    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="pairwise distinct",
    ):
        _attestation(
            result_receipt,
            independent_result_reviewer_identity_sha256=(
                writer_helpers.AUTHOR_IDENTITY_SHA256
            ),
        )


def test_builder_rejects_incomplete_checks_and_impossible_lifecycle(
    result_receipt: dict[str, object],
) -> None:
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="check coverage",
    ):
        _attestation(result_receipt, accepted_check_ids=())

    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="predates the result receipt",
    ):
        _attestation(
            result_receipt,
            reviewed_at=writer_helpers.RUN_NOW,
            expires_at=writer_helpers.RUN_NOW + timedelta(days=1),
        )

    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="frozen maximum",
    ):
        _attestation(
            result_receipt,
            expires_at=REVIEWED_AT + timedelta(days=31),
        )


def test_verifier_accepts_canonical_bytes_and_rejects_signature_or_trust_drift(
    result_receipt: dict[str, object],
) -> None:
    attestation = _attestation(result_receipt)
    verification = _verify(_canonical_bytes(attestation), result_receipt)
    assert verification.result_receipt_accepted is True

    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="transport is not canonical JSON",
    ):
        _verify(
            json.dumps(attestation, indent=2, sort_keys=True).encode("utf-8"),
            result_receipt,
        )

    tampered = deepcopy(attestation)
    tampered["result_receipt_accepted"] = False
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="signature verification failed",
    ):
        _verify(tampered, result_receipt)

    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="does not match the trusted key",
    ):
        _verify(
            attestation,
            result_receipt,
            trusted_result_reviewer_keys={
                RESULT_REVIEW_KEY_ID: _anchor(
                    identity=OTHER_RESULT_REVIEWER_IDENTITY,
                )
            },
        )

    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="signature verification failed",
    ):
        _verify(
            attestation,
            result_receipt,
            trusted_result_reviewer_keys={
                RESULT_REVIEW_KEY_ID: _anchor(
                    public_key=OTHER_RESULT_REVIEW_PUBLIC_KEY,
                )
            },
        )


def test_verifier_rejects_crosswired_receipt_and_validly_signed_false_dispositions(
    result_receipt: dict[str, object],
) -> None:
    attestation = _attestation(result_receipt)
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="result receipt identity is cross-wired",
    ):
        _verify(
            attestation,
            result_receipt,
            expected_result_receipt_sha256="1" * 64,
        )

    false_review = deepcopy(attestation)
    false_review.pop("signature")
    false_review.pop("attestation_sha256")
    rows = false_review["case_review_rows"]
    assert isinstance(rows, list)
    rows[0]["metric_dispositions"][0]["disposition"] = RETAINED_METRIC_VALUE_REJECTED
    false_review["result_receipt_review_outcome"] = RESULT_REVIEW_OUTCOME_REJECTED
    false_review["result_receipt_accepted"] = False
    false_review["attestation_sha256"] = _sha256(false_review)
    false_review["signature"] = {
        "algorithm": "ed25519",
        "key_id": RESULT_REVIEW_KEY_ID,
        "value": sign_ed25519(_canonical_bytes(false_review), RESULT_REVIEW_KEY),
    }
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="case dispositions",
    ):
        _verify(false_review, result_receipt)


@pytest.mark.parametrize(
    "updates",
    [
        {"observed_status": "arbitrary_status"},
        {"operational_result_sha256": None},
        {"independent_result_sha256": None},
        {"accepted_iteration_count": -1},
        {"accepted_energy_ledger": []},
        {"runtime_input_sha256": "0" * 64},
        {"independent_oracle_input_sha256": "0" * 64},
    ],
)
def test_result_evidence_omission_or_semantic_drift_forces_rejected_outcome(
    result_receipt: _ResultEvidence,
    updates: dict[str, object],
) -> None:
    tampered = _tampered_first_case_receipt(result_receipt, **updates)
    attestation = _attestation(tampered)
    first_row = attestation["case_review_rows"][0]

    assert first_row["result_evidence_disposition"] == (
        REQUIRED_RESULT_EVIDENCE_REJECTED
    )
    assert first_row["result_evidence_rejection_reasons"]
    assert attestation["result_receipt_review_outcome"] == (
        RESULT_REVIEW_OUTCOME_REJECTED
    )
    assert attestation["result_receipt_accepted"] is False
    assert _verify(attestation, tampered).result_receipt_accepted is False


def test_non_exact_integer_count_fails_closed_at_writer_validation(
    result_receipt: _ResultEvidence,
) -> None:
    tampered = _tampered_first_case_receipt(
        result_receipt,
        accepted_iteration_count=True,
    )
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="full result-writer contract validation",
    ):
        _attestation(tampered)


def test_energy_ledger_is_recomputed_against_monotonic_and_energy_metrics(
    result_receipt: _ResultEvidence,
) -> None:
    tampered = deepcopy(result_receipt)
    run_observation = tampered["run_observation"]
    assert isinstance(run_observation, dict)
    case_results = run_observation["case_results"]
    assert isinstance(case_results, list)
    first_case = case_results[0]
    assert isinstance(first_case, dict)
    ledger = first_case["accepted_energy_ledger"]
    assert isinstance(ledger, list)
    first_case["accepted_energy_ledger"] = list(reversed(ledger))
    tampered["case_results"] = deepcopy(case_results)
    tampered["observation_sha256"] = _sha256(run_observation)
    _rehash_receipt(tampered)

    attestation = _attestation(tampered)
    first_row = attestation["case_review_rows"][0]
    assert first_row["result_evidence_disposition"] == (
        REQUIRED_RESULT_EVIDENCE_REJECTED
    )
    assert (
        "accepted_energy_ledger_not_monotonic"
        in first_row["result_evidence_rejection_reasons"]
    )
    assert attestation["result_receipt_accepted"] is False


def test_fail_closed_energy_ledger_must_also_be_monotonic(
    result_receipt: _ResultEvidence,
) -> None:
    tampered = deepcopy(result_receipt)
    run_observation = tampered["run_observation"]
    assert isinstance(run_observation, dict)
    case_results = run_observation["case_results"]
    assert isinstance(case_results, list)
    line_search_exhausted = case_results[12]
    assert isinstance(line_search_exhausted, dict)
    ledger = line_search_exhausted["accepted_energy_ledger"]
    assert isinstance(ledger, list)
    line_search_exhausted["accepted_energy_ledger"] = list(reversed(ledger))
    tampered["case_results"] = deepcopy(case_results)
    tampered["observation_sha256"] = _sha256(run_observation)
    _rehash_receipt(tampered)

    attestation = _attestation(tampered)
    reasons = attestation["case_review_rows"][12]["result_evidence_rejection_reasons"]
    assert "accepted_energy_ledger_not_monotonic" in reasons
    assert attestation["result_receipt_accepted"] is False


def test_case_count_budget_cannot_be_extended_with_a_self_consistent_ledger(
    result_receipt: _ResultEvidence,
) -> None:
    tampered = deepcopy(result_receipt)
    run_observation = tampered["run_observation"]
    assert isinstance(run_observation, dict)
    case_results = run_observation["case_results"]
    assert isinstance(case_results, list)
    first_case = case_results[0]
    assert isinstance(first_case, dict)
    ledger = first_case["accepted_energy_ledger"]
    assert isinstance(ledger, list)
    first_case["accepted_iteration_count"] = 65
    first_case["energy_force_evaluation_count"] = 66
    first_case["accepted_energy_ledger"] = [*ledger, ledger[-1]]
    tampered["case_results"] = deepcopy(case_results)
    tampered["observation_sha256"] = _sha256(run_observation)
    _rehash_receipt(tampered)

    attestation = _attestation(tampered)
    first_row = attestation["case_review_rows"][0]
    assert (
        "accepted_iteration_count_exceeds_case_budget"
        in first_row["result_evidence_rejection_reasons"]
    )
    assert attestation["result_receipt_accepted"] is False


def test_line_search_failure_status_is_lane_specific_and_requires_full_backtracks(
    result_receipt: _ResultEvidence,
) -> None:
    tampered = deepcopy(result_receipt)
    run_observation = tampered["run_observation"]
    assert isinstance(run_observation, dict)
    case_results = run_observation["case_results"]
    assert isinstance(case_results, list)
    first_case = case_results[0]
    assert isinstance(first_case, dict)
    ledger = first_case["accepted_energy_ledger"]
    assert isinstance(ledger, list)
    first_case.update(
        {
            "observed_status": "line_search_failed",
            "observed_error_code": "bounded_projected_backtracking_exhausted",
            "accepted_iteration_count": 1,
            "rejected_step_count": 1,
            "energy_force_evaluation_count": 3,
            "accepted_energy_ledger": [ledger[0], ledger[-1]],
        }
    )
    tampered["case_results"] = deepcopy(case_results)
    tampered["observation_sha256"] = _sha256(run_observation)
    _rehash_receipt(tampered)

    attestation = _attestation(tampered)
    reasons = attestation["case_review_rows"][0]["result_evidence_rejection_reasons"]
    assert "pass_status_or_error_code_invalid" in reasons
    assert "line_search_failure_status_count_mismatch" in reasons
    assert attestation["result_receipt_accepted"] is False


def test_converged_case_rejections_are_bound_to_accepted_progress(
    result_receipt: _ResultEvidence,
) -> None:
    tampered = deepcopy(result_receipt)
    run_observation = tampered["run_observation"]
    assert isinstance(run_observation, dict)
    case_results = run_observation["case_results"]
    assert isinstance(case_results, list)
    initially_converged = case_results[3]
    assert isinstance(initially_converged, dict)
    initially_converged["rejected_step_count"] = 100
    initially_converged["energy_force_evaluation_count"] = 101
    tampered["case_results"] = deepcopy(case_results)
    tampered["observation_sha256"] = _sha256(run_observation)
    _rehash_receipt(tampered)

    attestation = _attestation(tampered)
    reasons = attestation["case_review_rows"][3]["result_evidence_rejection_reasons"]
    assert "accepted_path_rejection_count_exceeds_case_progress" in reasons
    assert attestation["result_receipt_accepted"] is False


def test_upstream_signed_role_chain_is_required_and_cannot_be_caller_crosswired(
    result_receipt: _ResultEvidence,
) -> None:
    attestation = _attestation(result_receipt)
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="upstream signed-chain verification failed",
    ):
        _verify(
            attestation,
            result_receipt,
            expected_implementation_author_identity_sha256="1" * 64,
        )
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="upstream signed-chain verification failed",
    ):
        _verify(
            attestation,
            result_receipt,
            trusted_scientific_reviewer_keys={},
        )


def test_external_lifecycle_inputs_are_required_by_builder_and_verifier() -> None:
    required_names = {
        "revoked_pre_execution_review_attestation_sha256s",
        "revoked_authorization_receipt_sha256s",
        "revoked_execution_environment_receipt_sha256s",
        "revoked_result_receipt_sha256s",
        "superseded_result_receipt_sha256s",
    }
    builder_parameters = inspect.signature(
        build_signed_reference_minimization_validation_result_review_attestation
    ).parameters
    verifier_parameters = inspect.signature(
        verify_signed_reference_minimization_validation_result_review_attestation
    ).parameters
    assert all(
        builder_parameters[name].default is inspect.Parameter.empty
        for name in required_names
    )
    assert all(
        verifier_parameters[name].default is inspect.Parameter.empty
        for name in required_names
        | {
            "revoked_result_review_attestation_sha256s",
            "superseded_result_review_attestation_sha256s",
        }
    )


@pytest.mark.parametrize(
    ("keyword", "receipt_field", "message"),
    [
        (
            "revoked_pre_execution_review_attestation_sha256s",
            "review_attestation_sha256",
            "pre-execution review attestation is externally revoked",
        ),
        (
            "revoked_authorization_receipt_sha256s",
            "authorization_receipt_sha256",
            "authorization receipt is externally revoked",
        ),
        (
            "revoked_execution_environment_receipt_sha256s",
            "execution_environment_receipt_sha256",
            "execution environment receipt is externally revoked",
        ),
        (
            "revoked_result_receipt_sha256s",
            "receipt_sha256",
            "result receipt is externally revoked",
        ),
        (
            "superseded_result_receipt_sha256s",
            "receipt_sha256",
            "result receipt is externally superseded",
        ),
    ],
)
def test_verifier_rechecks_external_receipt_chain_state(
    result_receipt: dict[str, object],
    keyword: str,
    receipt_field: str,
    message: str,
) -> None:
    attestation = _attestation(result_receipt)
    with pytest.raises(ReferenceMinimizationValidationResultReviewError, match=message):
        _verify(
            attestation,
            result_receipt,
            **{keyword: (result_receipt[receipt_field],)},
        )


def test_verifier_rejects_revoked_or_expired_result_review_attestation(
    result_receipt: dict[str, object],
) -> None:
    attestation = _attestation(result_receipt)
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="result review attestation is externally revoked",
    ):
        _verify(
            attestation,
            result_receipt,
            revoked_result_review_attestation_sha256s=(
                attestation["attestation_sha256"],
            ),
        )
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="result review attestation is externally superseded",
    ):
        _verify(
            attestation,
            result_receipt,
            superseded_result_review_attestation_sha256s=(
                attestation["attestation_sha256"],
            ),
        )
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="expired",
    ):
        _verify(attestation, result_receipt, checked_at=EXPIRES_AT)


def test_contract_document_rejects_tamper() -> None:
    tampered = deepcopy(
        reference_minimization_validation_result_review_contract_document()
    )
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ReferenceMinimizationValidationResultReviewError,
        match="does not match the frozen record",
    ):
        require_reference_minimization_validation_result_review_contract_document(
            tampered
        )
