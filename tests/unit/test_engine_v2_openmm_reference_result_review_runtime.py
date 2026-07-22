from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Generator

import pytest


pytest.importorskip("openmm")

from betelgeuze_engine_v2.offline.openmm_reference_oracle import (  # noqa: E402
    observe_openmm_reference_runtime_identity,
)
from betelgeuze_engine_v2.offline.openmm_reference_receipts import (  # noqa: E402
    build_openmm_reference_energy_force_receipt,
    build_openmm_reference_minimization_trace_receipt,
)
from betelgeuze_engine_v2.offline.openmm_reference_result_review import (  # noqa: E402
    EnergyForceResultReviewEvidence,
    MinimizationResultReviewEvidence,
    OpenMMReferenceResultReviewError,
    OpenMMReferenceResultReviewerTrustAnchor,
    build_signed_openmm_reference_result_review_attestation,
    verify_signed_openmm_reference_result_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (  # noqa: E402
    ed25519_public_key_bytes,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_result_review import (  # noqa: E402
    MinimizationResultReviewerTrustAnchor,
)
from betelgeuze_engine_v2.physics.reference_validation_result_review import (  # noqa: E402
    ReferenceValidationResultReviewerTrustAnchor,
)
import tests.unit.test_engine_v2_reference_minimization_validation_result_review as min_review_support  # noqa: E402
import tests.unit.test_engine_v2_reference_minimization_validation_result_writer as min_writer_support  # noqa: E402
import tests.unit.test_engine_v2_reference_validation_result_review as energy_review_support  # noqa: E402
import tests.unit.test_engine_v2_reference_validation_result_writer as energy_writer_support  # noqa: E402


EXTERNAL_REVIEWER_IDENTITY = "1" * 64
EXTERNAL_REVIEWER_KEY_ID = "test-openmm-external-result-reviewer"
EXTERNAL_REVIEWER_KEY = bytes.fromhex("51" * 32)
EXTERNAL_REVIEWER_PUBLIC_KEY = ed25519_public_key_bytes(EXTERNAL_REVIEWER_KEY)
HOST_IDENTITY = "2" * 64
CPU_IDENTITY = "3" * 64
SESSION_IDENTITY = "4" * 64
CUSTODY_TERMINAL = "5" * 64
OUTER_NONCE = "0" * 64
REVIEWED_AT = datetime(2026, 7, 22, 1, 0, 0, tzinfo=timezone.utc)
EXPIRES_AT = REVIEWED_AT + timedelta(days=1)
CHECKED_AT = REVIEWED_AT + timedelta(hours=1)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _refresh_attestation(document: dict[str, Any]) -> dict[str, Any]:
    document.pop("signature", None)
    document.pop("attestation_sha256", None)
    document["attestation_sha256"] = hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


@dataclass(frozen=True)
class _ReviewBundle:
    energy_evidence: EnergyForceResultReviewEvidence
    minimization_evidence: MinimizationResultReviewEvidence
    openmm_energy_receipt: dict[str, Any]
    openmm_minimization_receipt: dict[str, Any]
    attestation: dict[str, Any]


@pytest.fixture(scope="module")
def review_bundle(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[_ReviewBundle, None, None]:
    persistent_patch = pytest.MonkeyPatch()
    minimum_generator: Generator[Any, None, None] | None = None
    try:
        energy_root = energy_writer_support._private_root(
            tmp_path_factory.mktemp("openmm-review-energy"), "accepted"
        )
        energy_receipt = energy_review_support._make_receipt(
            energy_root, mode="accepted"
        )
        energy_attestation = energy_review_support._build(
            persistent_patch,
            energy_receipt,
            expires_at=energy_review_support.REVIEWED_AT + timedelta(days=20),
        )
        energy_evidence = EnergyForceResultReviewEvidence(
            result_receipt=energy_receipt,
            result_review_attestation=energy_attestation,
            pre_execution_review_attestation={"raw_review": True},
            authorization_receipt={"raw_authorization": True},
            trusted_scientific_reviewer_keys={},
            trusted_authorization_operator_keys={},
            trusted_result_reviewer_keys={
                energy_review_support.RESULT_REVIEWER_KEY_ID: (
                    ReferenceValidationResultReviewerTrustAnchor(
                        energy_review_support.RESULT_REVIEWER_IDENTITY_SHA256,
                        energy_review_support.RESULT_REVIEW_VERIFICATION_KEY,
                    )
                )
            },
            expected_implementation_author_identity_sha256=(
                energy_writer_support.AUTHOR_IDENTITY_SHA256
            ),
            expected_independent_scientific_reviewer_identity_sha256=(
                energy_writer_support.REVIEWER_IDENTITY_SHA256
            ),
            expected_authorization_operator_identity_sha256=(
                energy_writer_support.OPERATOR_IDENTITY_SHA256
            ),
        )

        persistent_patch.setattr(min_writer_support, "AUTHORIZATION_NONCE", "d" * 64)
        persistent_patch.setattr(
            min_writer_support, "ENVIRONMENT_RECEIPT_SHA256", "c" * 64
        )
        minimum_generator = min_review_support.result_receipt.__wrapped__(
            tmp_path_factory
        )
        minimization_receipt = next(minimum_generator)
        minimization_attestation = min_review_support._attestation(minimization_receipt)
        minimization_evidence = MinimizationResultReviewEvidence(
            result_receipt=minimization_receipt,
            result_review_attestation=minimization_attestation,
            pre_execution_review_attestation=(
                minimization_receipt.pre_execution_review_attestation
            ),
            authorization_receipt=minimization_receipt.authorization_receipt,
            trusted_scientific_reviewer_keys=(
                minimization_receipt.trusted_scientific_reviewer_keys
            ),
            trusted_authorization_operator_keys=(
                minimization_receipt.trusted_authorization_operator_keys
            ),
            trusted_result_reviewer_keys={
                min_review_support.RESULT_REVIEW_KEY_ID: (
                    MinimizationResultReviewerTrustAnchor(
                        min_review_support.RESULT_REVIEWER_IDENTITY,
                        min_review_support.RESULT_REVIEW_PUBLIC_KEY,
                    )
                )
            },
            expected_implementation_author_identity_sha256=(
                min_writer_support.AUTHOR_IDENTITY_SHA256
            ),
            expected_independent_scientific_reviewer_identity_sha256=(
                min_writer_support.REVIEWER_IDENTITY_SHA256
            ),
            expected_authorization_operator_identity_sha256=(
                min_writer_support.OPERATOR_IDENTITY_SHA256
            ),
        )

        runtime_identity = observe_openmm_reference_runtime_identity()
        openmm_energy = build_openmm_reference_energy_force_receipt(
            observed_at_utc="2026-07-22T00:00:00Z",
            runtime_identity=runtime_identity,
        )
        operational_traces = tuple(
            case["coordinate_traces"][0]
            for case in minimization_receipt["case_results"]
        )
        openmm_minimization = build_openmm_reference_minimization_trace_receipt(
            operational_traces,
            observed_at_utc="2026-07-22T00:00:00Z",
            runtime_identity=runtime_identity,
        )
        attestation = build_signed_openmm_reference_result_review_attestation(
            energy_force_evidence=energy_evidence,
            minimization_evidence=minimization_evidence,
            openmm_energy_force_receipt=openmm_energy,
            openmm_minimization_trace_receipt=openmm_minimization,
            enrolled_host_identity_sha256=HOST_IDENTITY,
            cpu_identity_sha256=CPU_IDENTITY,
            production_evidence_session_sha256=SESSION_IDENTITY,
            custody_terminal_sha256=CUSTODY_TERMINAL,
            external_result_reviewer_identity_sha256=EXTERNAL_REVIEWER_IDENTITY,
            external_result_reviewer_key_id=EXTERNAL_REVIEWER_KEY_ID,
            signing_key=EXTERNAL_REVIEWER_KEY,
            reviewed_at=REVIEWED_AT,
            expires_at=EXPIRES_AT,
            nonce_sha256=OUTER_NONCE,
        )
        yield _ReviewBundle(
            energy_evidence=energy_evidence,
            minimization_evidence=minimization_evidence,
            openmm_energy_receipt=openmm_energy,
            openmm_minimization_receipt=openmm_minimization,
            attestation=attestation,
        )
    finally:
        if minimum_generator is not None:
            minimum_generator.close()
        persistent_patch.undo()


def _verify(
    bundle: _ReviewBundle,
    source: object | None = None,
    **overrides: object,
):
    values: dict[str, object] = {
        "source": bundle.attestation if source is None else source,
        "energy_force_evidence": bundle.energy_evidence,
        "minimization_evidence": bundle.minimization_evidence,
        "openmm_energy_force_receipt": bundle.openmm_energy_receipt,
        "openmm_minimization_trace_receipt": bundle.openmm_minimization_receipt,
        "expected_enrolled_host_identity_sha256": HOST_IDENTITY,
        "expected_cpu_identity_sha256": CPU_IDENTITY,
        "expected_production_evidence_session_sha256": SESSION_IDENTITY,
        "expected_custody_terminal_sha256": CUSTODY_TERMINAL,
        "trusted_external_result_reviewer_keys": {
            EXTERNAL_REVIEWER_KEY_ID: OpenMMReferenceResultReviewerTrustAnchor(
                EXTERNAL_REVIEWER_IDENTITY,
                EXTERNAL_REVIEWER_PUBLIC_KEY,
            )
        },
        "checked_at": CHECKED_AT,
        "revoked_openmm_energy_force_receipt_sha256s": (),
        "superseded_openmm_energy_force_receipt_sha256s": (),
        "revoked_openmm_minimization_trace_receipt_sha256s": (),
        "superseded_openmm_minimization_trace_receipt_sha256s": (),
        "revoked_result_review_attestation_sha256s": (),
        "superseded_result_review_attestation_sha256s": (),
    }
    values.update(overrides)
    return verify_signed_openmm_reference_result_review_attestation(  # type: ignore[arg-type]
        **values
    )


def test_signed_review_reverifies_exact_engine_and_openmm_receipts(
    review_bundle: _ReviewBundle,
) -> None:
    verification = _verify(review_bundle)
    assert verification.external_oracle_comparison_verified is True
    assert verification.result_review_outcome == "accepted"
    assert verification.enrolled_host_identity_sha256 == HOST_IDENTITY
    assert verification.cpu_identity_sha256 == CPU_IDENTITY
    assert verification.code_commit_sha == energy_writer_support.CODE_COMMIT_SHA
    assert (
        verification.energy_force_result_receipt_sha256
        == review_bundle.energy_evidence.result_receipt["receipt_sha256"]
    )
    assert (
        verification.minimization_result_receipt_sha256
        == review_bundle.minimization_evidence.result_receipt["receipt_sha256"]
    )
    assert verification.production_validation_evidence is False
    assert verification.scientifically_validated is False
    assert verification.s0_admission_authorized is False
    assert verification.s1_admission_authorized is False
    assert verification.claim_safe is False
    assert "single_host_external_review_is_not_two_host_reproducibility" in (
        verification.blockers
    )


@pytest.mark.parametrize(
    "field,wrong",
    (
        ("expected_enrolled_host_identity_sha256", "6" * 64),
        ("expected_cpu_identity_sha256", "6" * 64),
        ("expected_production_evidence_session_sha256", "6" * 64),
        ("expected_custody_terminal_sha256", "6" * 64),
    ),
)
def test_review_rejects_host_session_and_custody_crosswire(
    review_bundle: _ReviewBundle,
    field: str,
    wrong: str,
) -> None:
    with pytest.raises(OpenMMReferenceResultReviewError):
        _verify(review_bundle, **{field: wrong})


def test_review_rejects_signature_tamper_and_noncanonical_transport(
    review_bundle: _ReviewBundle,
) -> None:
    tampered = deepcopy(review_bundle.attestation)
    tampered["host_binding"]["cpu_identity_sha256"] = "6" * 64
    _refresh_attestation(tampered)
    with pytest.raises(OpenMMReferenceResultReviewError):
        _verify(review_bundle, tampered)

    pretty = json.dumps(review_bundle.attestation, indent=2).encode("utf-8")
    with pytest.raises(OpenMMReferenceResultReviewError):
        _verify(review_bundle, pretty)


def test_review_rejects_revoked_or_superseded_nested_and_outer_receipts(
    review_bundle: _ReviewBundle,
) -> None:
    with pytest.raises(OpenMMReferenceResultReviewError):
        _verify(
            review_bundle,
            revoked_openmm_energy_force_receipt_sha256s=(
                review_bundle.openmm_energy_receipt["receipt_sha256"],
            ),
        )
    with pytest.raises(OpenMMReferenceResultReviewError):
        _verify(
            review_bundle,
            superseded_openmm_minimization_trace_receipt_sha256s=(
                review_bundle.openmm_minimization_receipt["receipt_sha256"],
            ),
        )
    with pytest.raises(OpenMMReferenceResultReviewError):
        _verify(
            review_bundle,
            revoked_result_review_attestation_sha256s=(
                review_bundle.attestation["attestation_sha256"],
            ),
        )


def test_builder_rejects_external_reviewer_role_reuse(
    review_bundle: _ReviewBundle,
) -> None:
    with pytest.raises(OpenMMReferenceResultReviewError):
        build_signed_openmm_reference_result_review_attestation(
            energy_force_evidence=review_bundle.energy_evidence,
            minimization_evidence=review_bundle.minimization_evidence,
            openmm_energy_force_receipt=review_bundle.openmm_energy_receipt,
            openmm_minimization_trace_receipt=(
                review_bundle.openmm_minimization_receipt
            ),
            enrolled_host_identity_sha256=HOST_IDENTITY,
            cpu_identity_sha256=CPU_IDENTITY,
            production_evidence_session_sha256=SESSION_IDENTITY,
            custody_terminal_sha256=CUSTODY_TERMINAL,
            external_result_reviewer_identity_sha256=(
                energy_writer_support.AUTHOR_IDENTITY_SHA256
            ),
            external_result_reviewer_key_id=EXTERNAL_REVIEWER_KEY_ID,
            signing_key=EXTERNAL_REVIEWER_KEY,
            reviewed_at=REVIEWED_AT,
            expires_at=EXPIRES_AT,
            nonce_sha256=OUTER_NONCE,
        )
