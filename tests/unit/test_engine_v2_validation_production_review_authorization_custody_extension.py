from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_authorization import (
    MinimizationAuthorizationOperatorTrustAnchor,
    build_signed_reference_minimization_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_receipts import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_review import (
    MinimizationScientificReviewerTrustAnchor,
    build_signed_reference_minimization_validation_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    ScientificReviewerTrustAnchor,
    build_signed_reference_validation_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    AuthorizationOperatorTrustAnchor,
    build_signed_reference_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
    PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
    CustodyRoleTrustAnchor,
    EvidenceAuthorityTrustAnchor,
    build_signed_production_custody_event,
    build_signed_production_evidence_permit,
    build_signed_production_evidence_status_snapshot,
)
from betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension import (
    FROZEN_LEGACY_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V6,
    FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
    PRODUCTION_AUTHORIZATION_CARRIER_SCHEMA_ID,
    PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_SCHEMA_ID,
    PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_SCHEMA_ID,
    ProductionAuthorizationCarrierTrustAnchor,
    ProductionReviewAuthorizationCustodyExtensionEventVerification,
    ProductionReviewCarrierTrustAnchor,
    VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_ID,
    ValidationProductionReviewAuthorizationCustodyExtensionError,
    build_signed_production_authorization_custody_extension_event,
    build_signed_production_authorization_carrier,
    build_signed_production_pre_execution_review_custody_extension_event,
    build_signed_production_pre_execution_review_carrier,
    require_validation_production_review_authorization_custody_extension_contract_document,
    validation_production_review_authorization_custody_extension_contract_document,
    validation_production_review_authorization_custody_extension_decision,
    verify_signed_production_authorization_custody_extension_event,
    verify_signed_production_authorization_carrier,
    verify_signed_production_pre_execution_review_custody_extension_event,
    verify_signed_production_pre_execution_review_carrier,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
    VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_ID,
)


UTC = timezone.utc
REVIEWED_AT = datetime(2026, 7, 19, 1, tzinfo=UTC)
REVIEW_EXPIRES_AT = REVIEWED_AT + timedelta(days=1)
SIGNED_AT = REVIEWED_AT + timedelta(hours=1)
CARRIER_EXPIRES_AT = SIGNED_AT + timedelta(hours=3)
CHECKED_AT = SIGNED_AT + timedelta(hours=1)
AUTHOR_IDENTITY = "1" * 64
UPSTREAM_REVIEWER_IDENTITY = "2" * 64
PRODUCTION_REVIEWER_IDENTITY = "3" * 64
CUSTODIAN_IDENTITY = "4" * 64
HOST_IDENTITY = "5" * 64
EVIDENCE_AUTHORITY_IDENTITY = "6" * 64
STATUS_AUTHORITY_IDENTITY = "7" * 64
PERMIT_SHA256 = "8" * 64
PERMIT_ID_SHA256 = "9" * 64
STUDY_ID_SHA256 = "a" * 64
RUN_ID_SHA256 = "b" * 64
AUTHORIZATION_NONCE_SHA256 = "c" * 64
REVIEW_NONCE_SHA256 = "d" * 64
CURRENT_STATUS_SHA256 = "e" * 64
PROCESS_LAUNCH_IDENTITY_SHA256 = "f" * 64
PRIOR_CUSTODY_EVENT_SHA256 = "0" * 64
ENERGY_REVIEW_KEY_ID = "energy-upstream-reviewer-2026-07"
MINIMIZATION_REVIEW_KEY_ID = "minimization-upstream-reviewer-2026-07"
PRODUCTION_REVIEW_KEY_ID = "production-reviewer-2026-07"
EVIDENCE_AUTHORITY_KEY_ID = "evidence-authority-2026-07"
STATUS_AUTHORITY_KEY_ID = "status-authority-2026-07"
ENERGY_REVIEW_KEY = bytes.fromhex("01" * 32)
ENERGY_REVIEW_PUBLIC_KEY = ed25519_public_key_bytes(ENERGY_REVIEW_KEY)
MINIMIZATION_REVIEW_PRIVATE_KEY = bytes.fromhex("11" * 32)
PRODUCTION_REVIEW_PRIVATE_KEY = bytes.fromhex("22" * 32)
UPSTREAM_AUTHORIZATION_OPERATOR_IDENTITY = "81" * 32
PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY = "91" * 32
ENERGY_AUTHORIZATION_KEY_ID = "energy-upstream-authorization-2026-07"
MINIMIZATION_AUTHORIZATION_KEY_ID = "minimization-upstream-authorization-2026-07"
PRODUCTION_AUTHORIZATION_KEY_ID = "production-authorization-2026-07"
ENERGY_AUTHORIZATION_KEY = bytes.fromhex("02" * 32)
ENERGY_AUTHORIZATION_PUBLIC_KEY = ed25519_public_key_bytes(ENERGY_AUTHORIZATION_KEY)
MINIMIZATION_AUTHORIZATION_PRIVATE_KEY = bytes.fromhex("33" * 32)
PRODUCTION_AUTHORIZATION_PRIVATE_KEY = bytes.fromhex("44" * 32)
AUTHORIZATION_ISSUED_AT = SIGNED_AT + timedelta(minutes=15)
AUTHORIZATION_EXPIRES_AT = CARRIER_EXPIRES_AT
AUTHORIZATION_CARRIER_SIGNED_AT = SIGNED_AT + timedelta(minutes=30)
AUTHORIZATION_CARRIER_EXPIRES_AT = CARRIER_EXPIRES_AT - timedelta(minutes=15)
AUTHORIZATION_CHECKED_AT = AUTHORIZATION_CARRIER_SIGNED_AT + timedelta(minutes=15)
STAGE3_CUSTODY_EVENT_SHA256 = "ab" * 32
ENERGY_EXECUTION_ENVIRONMENT_SHA256 = (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
)
ENERGY_RESULT_RECEIPT_SHA256 = (
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
)
ENERGY_AUTHORIZATION_DEPENDENCY_ROWS = {
    "cryptography-distribution": "51" * 32,
    "numpy-distribution": "61" * 32,
    "openssl-executable": "71" * 32,
    "python-runtime-executable": "81" * 32,
    "python-standard-library": "91" * 32,
    "torch-distribution": "a1" * 32,
}
MINIMIZATION_AUTHORIZATION_DEPENDENCY_ROWS = {
    "cryptography-distribution": "31" * 32,
    "numpy-distribution": "41" * 32,
    "openssl-executable": "51" * 32,
    "python-runtime-executable": "61" * 32,
    "python-standard-library": "71" * 32,
    "torch-distribution": "81" * 32,
}
EVENT_PERMIT_ISSUED_AT = REVIEWED_AT - timedelta(hours=1)
EVENT_STATUS_ONE_ISSUED_AT = EVENT_PERMIT_ISSUED_AT + timedelta(minutes=30)
EVENT_SEQUENCE_ONE_HANDED_OFF_AT = EVENT_PERMIT_ISSUED_AT + timedelta(minutes=40)
EVENT_SEQUENCE_ONE_RECEIVED_AT = EVENT_PERMIT_ISSUED_AT + timedelta(minutes=41)
EVENT_SEQUENCE_TWO_HANDED_OFF_AT = EVENT_PERMIT_ISSUED_AT + timedelta(minutes=50)
EVENT_SEQUENCE_TWO_RECEIVED_AT = EVENT_PERMIT_ISSUED_AT + timedelta(minutes=51)
EVENT_STATUS_TWO_ISSUED_AT = EVENT_PERMIT_ISSUED_AT + timedelta(minutes=90)
EVENT_SEQUENCE_THREE_HANDED_OFF_AT = SIGNED_AT + timedelta(minutes=5)
EVENT_SEQUENCE_THREE_RECEIVED_AT = SIGNED_AT + timedelta(minutes=6)
EVENT_SEQUENCE_FOUR_HANDED_OFF_AT = AUTHORIZATION_CARRIER_SIGNED_AT + timedelta(
    minutes=5
)
EVENT_SEQUENCE_FOUR_RECEIVED_AT = AUTHORIZATION_CARRIER_SIGNED_AT + timedelta(minutes=6)
EVENT_STATUS_THREE_ISSUED_AT = AUTHORIZATION_CARRIER_SIGNED_AT + timedelta(minutes=10)
EVENT_PERMIT_AUTHORITY_PRIVATE_KEY = bytes.fromhex("a3" * 32)
EVENT_STATUS_AUTHORITY_PRIVATE_KEY = bytes.fromhex("b3" * 32)
EVENT_RUN_CUSTODIAN_PRIVATE_KEY = bytes.fromhex("55" * 32)
EVENT_ARTIFACT_STORE_PRIVATE_KEY = bytes.fromhex("66" * 32)
EVENT_REVIEW_STORE_PRIVATE_KEY = bytes.fromhex("77" * 32)
EVENT_AUTHORIZATION_STORE_PRIVATE_KEY = bytes.fromhex("88" * 32)
EVENT_RESERVATION_STORE_PRIVATE_KEY = bytes.fromhex("99" * 32)
EVENT_UNUSED_CUSTODY_PRIVATE_KEY = bytes.fromhex("aa" * 32)
EVENT_ARTIFACT_STORE_IDENTITY = "a2" * 32
EVENT_REVIEW_STORE_IDENTITY = "b2" * 32
EVENT_AUTHORIZATION_STORE_IDENTITY = "c2" * 32
EVENT_RESERVATION_STORE_IDENTITY = "d2" * 32
EVENT_UNUSED_CUSTODY_IDENTITY = "e2" * 32
EVENT_RUN_CUSTODIAN_KEY_ID = "event-run-custodian-2026-07"
EVENT_ARTIFACT_STORE_KEY_ID = "event-artifact-store-2026-07"
EVENT_REVIEW_STORE_KEY_ID = "event-review-store-2026-07"
EVENT_AUTHORIZATION_STORE_KEY_ID = "event-authorization-store-2026-07"
EVENT_RESERVATION_STORE_KEY_ID = "event-reservation-store-2026-07"
EVENT_UNUSED_CUSTODY_KEY_ID = "event-unused-audit-store-2026-07"
EVENT_PERMIT_CHECKPOINT_SHA256 = "10" * 32
EVENT_STATUS_ONE_CHECKPOINT_SHA256 = "20" * 32
EVENT_STATUS_TWO_CHECKPOINT_SHA256 = "30" * 32
EVENT_STATUS_THREE_CHECKPOINT_SHA256 = "40" * 32


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _run_context() -> dict[str, object]:
    return {
        "permit_sha256": PERMIT_SHA256,
        "permit_id_sha256": PERMIT_ID_SHA256,
        "study_id_sha256": STUDY_ID_SHA256,
        "run_id_sha256": RUN_ID_SHA256,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE_SHA256,
        "contract_bundle_sha256_rows": {
            VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_ID: (
                FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
            ),
            VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_ID: (
                FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
            ),
            "engine-v2-lane-contract/1.0.0": "1" * 64,
        },
        "code_commit_sha": "1" * 40,
        "source_sha256": "2" * 64,
        "source_manifest_sha256": "3" * 64,
        "dependency_manifest_sha256": "4" * 64,
        "runtime_manifest_sha256": "5" * 64,
        "seed": 1729,
        "command_argv": ["python3", "-m", "production_validation"],
        "artifact_output_root_identity_sha256": "6" * 64,
        "custodian_identity_sha256": CUSTODIAN_IDENTITY,
        "enrolled_host_identity_sha256": HOST_IDENTITY,
        "evidence_authority_identity_sha256": EVIDENCE_AUTHORITY_IDENTITY,
        "evidence_authority_key_id": EVIDENCE_AUTHORITY_KEY_ID,
        "current_status_snapshot_sha256": CURRENT_STATUS_SHA256,
        "current_status_authority_identity_sha256": STATUS_AUTHORITY_IDENTITY,
        "current_status_authority_key_id": STATUS_AUTHORITY_KEY_ID,
        "process_launch_identity_sha256": PROCESS_LAUNCH_IDENTITY_SHA256,
    }


def _raw_review(lane: str) -> bytes:
    if lane == "energy_force":
        review = build_signed_reference_validation_review_attestation(
            implementation_author_identity_sha256=AUTHOR_IDENTITY,
            independent_reviewer_identity_sha256=UPSTREAM_REVIEWER_IDENTITY,
            reviewer_key_id=ENERGY_REVIEW_KEY_ID,
            signing_key=ENERGY_REVIEW_KEY,
            reviewed_at=REVIEWED_AT,
            expires_at=REVIEW_EXPIRES_AT,
            nonce_sha256=REVIEW_NONCE_SHA256,
        )
    else:
        review = build_signed_reference_minimization_validation_review_attestation(
            implementation_author_identity_sha256=AUTHOR_IDENTITY,
            independent_reviewer_identity_sha256=UPSTREAM_REVIEWER_IDENTITY,
            reviewer_key_id=MINIMIZATION_REVIEW_KEY_ID,
            signing_key=MINIMIZATION_REVIEW_PRIVATE_KEY,
            reviewed_at=REVIEWED_AT,
            expires_at=REVIEW_EXPIRES_AT,
            nonce_sha256=REVIEW_NONCE_SHA256,
        )
    return _canonical(review)


def _upstream_arguments(lane: str) -> dict[str, object]:
    if lane == "energy_force":
        trust = {
            ENERGY_REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
                UPSTREAM_REVIEWER_IDENTITY,
                ENERGY_REVIEW_PUBLIC_KEY,
            )
        }
    else:
        trust = {
            MINIMIZATION_REVIEW_KEY_ID: MinimizationScientificReviewerTrustAnchor(
                UPSTREAM_REVIEWER_IDENTITY,
                ed25519_public_key_bytes(MINIMIZATION_REVIEW_PRIVATE_KEY),
            )
        }
    return {
        "trusted_reviewer_keys": trust,
        "expected_implementation_author_identity_sha256": AUTHOR_IDENTITY,
    }


def _carrier(lane: str = "energy_force") -> tuple[bytes, bytes]:
    raw_review = _raw_review(lane)
    carrier = build_signed_production_pre_execution_review_carrier(
        raw_review_attestation_bytes=raw_review,
        lane=lane,
        run_context=_run_context(),
        upstream_review_verification_arguments=_upstream_arguments(lane),
        prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
        production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
        production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
        signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
        signed_at=SIGNED_AT,
        expires_at=CARRIER_EXPIRES_AT,
    )
    return _canonical(carrier), raw_review


def _verify(
    carrier_bytes: bytes,
    raw_review: bytes,
    *,
    lane: str = "energy_force",
    **overrides: object,
):
    carrier = json.loads(carrier_bytes.decode("ascii"))
    values: dict[str, object] = {
        "source": carrier_bytes,
        "raw_review_attestation_bytes": raw_review,
        "expected_carrier_sha256": carrier["carrier_sha256"],
        "expected_lane": lane,
        "expected_run_context": _run_context(),
        "expected_prior_custody_event_sha256": PRIOR_CUSTODY_EVENT_SHA256,
        "upstream_review_verification_arguments": _upstream_arguments(lane),
        "trusted_production_reviewer_keys": {
            PRODUCTION_REVIEW_KEY_ID: ProductionReviewCarrierTrustAnchor(
                PRODUCTION_REVIEWER_IDENTITY,
                ed25519_public_key_bytes(PRODUCTION_REVIEW_PRIVATE_KEY),
            )
        },
        "checked_at": CHECKED_AT,
    }
    values.update(overrides)
    return verify_signed_production_pre_execution_review_carrier(  # type: ignore[arg-type]
        **values
    )


def _raw_authorization(
    lane: str,
    raw_review: bytes,
    **overrides: object,
) -> bytes:
    values: dict[str, object] = {
        "review_attestation": raw_review,
        "trusted_reviewer_keys": _upstream_arguments(lane)["trusted_reviewer_keys"],
        "expected_implementation_author_identity_sha256": AUTHOR_IDENTITY,
        "authorization_operator_identity_sha256": (
            UPSTREAM_AUTHORIZATION_OPERATOR_IDENTITY
        ),
        "authorization_key_id": (
            ENERGY_AUTHORIZATION_KEY_ID
            if lane == "energy_force"
            else MINIMIZATION_AUTHORIZATION_KEY_ID
        ),
        "signing_key": (
            ENERGY_AUTHORIZATION_KEY
            if lane == "energy_force"
            else MINIMIZATION_AUTHORIZATION_PRIVATE_KEY
        ),
        "issued_at": AUTHORIZATION_ISSUED_AT,
        "expires_at": AUTHORIZATION_EXPIRES_AT,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE_SHA256,
        "code_commit_sha": _run_context()["code_commit_sha"],
        "runner_source_sha256": _run_context()["source_sha256"],
        "dependency_artifact_sha256_rows": (
            ENERGY_AUTHORIZATION_DEPENDENCY_ROWS
            if lane == "energy_force"
            else MINIMIZATION_AUTHORIZATION_DEPENDENCY_ROWS
        ),
    }
    if lane == "energy_force":
        values.update(
            {
                "execution_environment_contract_sha256": (
                    ENERGY_EXECUTION_ENVIRONMENT_SHA256
                ),
                "result_receipt_contract_sha256": ENERGY_RESULT_RECEIPT_SHA256,
            }
        )
    values.update(overrides)
    if lane == "energy_force":
        receipt = build_signed_reference_validation_authorization_receipt(
            **values  # type: ignore[arg-type]
        )
    else:
        receipt = build_signed_reference_minimization_validation_authorization_receipt(
            **values  # type: ignore[arg-type]
        )
    return _canonical(receipt)


def _authorization_arguments(lane: str, **overrides: object) -> dict[str, object]:
    reviewer_arguments = _upstream_arguments(lane)
    if lane == "energy_force":
        operator_trust: dict[str, object] = {
            ENERGY_AUTHORIZATION_KEY_ID: AuthorizationOperatorTrustAnchor(
                UPSTREAM_AUTHORIZATION_OPERATOR_IDENTITY,
                ENERGY_AUTHORIZATION_PUBLIC_KEY,
            )
        }
        environment_sha256 = ENERGY_EXECUTION_ENVIRONMENT_SHA256
        result_sha256 = ENERGY_RESULT_RECEIPT_SHA256
    else:
        operator_trust = {
            MINIMIZATION_AUTHORIZATION_KEY_ID: (
                MinimizationAuthorizationOperatorTrustAnchor(
                    UPSTREAM_AUTHORIZATION_OPERATOR_IDENTITY,
                    ed25519_public_key_bytes(MINIMIZATION_AUTHORIZATION_PRIVATE_KEY),
                )
            )
        }
        environment_sha256 = FROZEN_REFERENCE_MINIMIZATION_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        result_sha256 = (
            FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        )
    values: dict[str, object] = {
        "trusted_reviewer_keys": reviewer_arguments["trusted_reviewer_keys"],
        "expected_implementation_author_identity_sha256": AUTHOR_IDENTITY,
        "trusted_operator_keys": operator_trust,
        "expected_code_commit_sha": _run_context()["code_commit_sha"],
        "expected_runner_source_sha256": _run_context()["source_sha256"],
        "expected_execution_environment_contract_sha256": environment_sha256,
        "expected_result_receipt_contract_sha256": result_sha256,
        "expected_dependency_artifact_sha256_rows": (
            ENERGY_AUTHORIZATION_DEPENDENCY_ROWS
            if lane == "energy_force"
            else MINIMIZATION_AUTHORIZATION_DEPENDENCY_ROWS
        ),
        "revoked_receipt_sha256s": (),
        "revoked_review_attestation_sha256s": (),
        "consumed_nonce_sha256s": (),
    }
    values.update(overrides)
    return values


def _stage3_reverification_arguments(
    lane: str,
    raw_stage3: bytes,
    **overrides: object,
) -> dict[str, object]:
    stage3 = json.loads(raw_stage3.decode("ascii"))
    values: dict[str, object] = {
        "expected_carrier_sha256": stage3["carrier_sha256"],
        "expected_prior_custody_event_sha256": PRIOR_CUSTODY_EVENT_SHA256,
        "upstream_review_verification_arguments": _upstream_arguments(lane),
        "trusted_production_reviewer_keys": {
            PRODUCTION_REVIEW_KEY_ID: ProductionReviewCarrierTrustAnchor(
                PRODUCTION_REVIEWER_IDENTITY,
                ed25519_public_key_bytes(PRODUCTION_REVIEW_PRIVATE_KEY),
            )
        },
        "revoked_production_reviewer_key_ids": (),
        "revoked_upstream_reviewer_key_ids": (),
        "revoked_carrier_sha256s": (),
        "superseded_carrier_sha256s": (),
        "revoked_upstream_review_sha256s": (),
        "superseded_upstream_review_sha256s": (),
    }
    values.update(overrides)
    return values


def _authorization_carrier(
    lane: str = "energy_force",
    *,
    raw_authorization_overrides: dict[str, object] | None = None,
    authorization_argument_overrides: dict[str, object] | None = None,
) -> tuple[bytes, bytes, bytes, bytes]:
    raw_stage3, raw_review = _carrier(lane)
    raw_authorization = _raw_authorization(
        lane,
        raw_review,
        **(raw_authorization_overrides or {}),
    )
    carrier = build_signed_production_authorization_carrier(
        raw_authorization_receipt_bytes=raw_authorization,
        raw_review_attestation_bytes=raw_review,
        raw_pre_execution_review_carrier_bytes=raw_stage3,
        lane=lane,
        run_context=_run_context(),
        upstream_authorization_verification_arguments=_authorization_arguments(
            lane,
            **(authorization_argument_overrides or {}),
        ),
        pre_execution_review_reverification_arguments=(
            _stage3_reverification_arguments(lane, raw_stage3)
        ),
        prior_custody_event_sha256=STAGE3_CUSTODY_EVENT_SHA256,
        production_authorization_operator_identity_sha256=(
            PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY
        ),
        production_authorization_key_id=PRODUCTION_AUTHORIZATION_KEY_ID,
        signing_key=PRODUCTION_AUTHORIZATION_PRIVATE_KEY,
        signed_at=AUTHORIZATION_CARRIER_SIGNED_AT,
        expires_at=AUTHORIZATION_CARRIER_EXPIRES_AT,
    )
    return _canonical(carrier), raw_authorization, raw_review, raw_stage3


def _verify_authorization(
    carrier_bytes: bytes,
    raw_authorization: bytes,
    raw_review: bytes,
    raw_stage3: bytes,
    *,
    lane: str = "energy_force",
    **overrides: object,
):
    carrier = json.loads(carrier_bytes.decode("ascii"))
    values: dict[str, object] = {
        "source": carrier_bytes,
        "raw_authorization_receipt_bytes": raw_authorization,
        "raw_review_attestation_bytes": raw_review,
        "raw_pre_execution_review_carrier_bytes": raw_stage3,
        "expected_carrier_sha256": carrier.get("carrier_sha256", "0" * 64),
        "expected_lane": lane,
        "expected_run_context": _run_context(),
        "expected_prior_custody_event_sha256": STAGE3_CUSTODY_EVENT_SHA256,
        "upstream_authorization_verification_arguments": (
            _authorization_arguments(lane)
        ),
        "pre_execution_review_reverification_arguments": (
            _stage3_reverification_arguments(lane, raw_stage3)
        ),
        "trusted_production_authorization_keys": {
            PRODUCTION_AUTHORIZATION_KEY_ID: (
                ProductionAuthorizationCarrierTrustAnchor(
                    PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY,
                    ed25519_public_key_bytes(PRODUCTION_AUTHORIZATION_PRIVATE_KEY),
                )
            )
        },
        "checked_at": AUTHORIZATION_CHECKED_AT,
    }
    values.update(overrides)
    return verify_signed_production_authorization_carrier(  # type: ignore[arg-type]
        **values
    )


def _event_utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_authority_trust() -> dict[str, EvidenceAuthorityTrustAnchor]:
    return {
        EVIDENCE_AUTHORITY_KEY_ID: EvidenceAuthorityTrustAnchor(
            EVIDENCE_AUTHORITY_IDENTITY,
            ed25519_public_key_bytes(EVENT_PERMIT_AUTHORITY_PRIVATE_KEY),
        ),
        STATUS_AUTHORITY_KEY_ID: EvidenceAuthorityTrustAnchor(
            STATUS_AUTHORITY_IDENTITY,
            ed25519_public_key_bytes(EVENT_STATUS_AUTHORITY_PRIVATE_KEY),
        ),
    }


def _event_custody_trust() -> dict[str, CustodyRoleTrustAnchor]:
    return {
        EVENT_RUN_CUSTODIAN_KEY_ID: CustodyRoleTrustAnchor(
            "run_custodian",
            CUSTODIAN_IDENTITY,
            ed25519_public_key_bytes(EVENT_RUN_CUSTODIAN_PRIVATE_KEY),
        ),
        EVENT_ARTIFACT_STORE_KEY_ID: CustodyRoleTrustAnchor(
            "artifact_store",
            EVENT_ARTIFACT_STORE_IDENTITY,
            ed25519_public_key_bytes(EVENT_ARTIFACT_STORE_PRIVATE_KEY),
        ),
        EVENT_REVIEW_STORE_KEY_ID: CustodyRoleTrustAnchor(
            "review_store",
            EVENT_REVIEW_STORE_IDENTITY,
            ed25519_public_key_bytes(EVENT_REVIEW_STORE_PRIVATE_KEY),
        ),
        EVENT_AUTHORIZATION_STORE_KEY_ID: CustodyRoleTrustAnchor(
            "authorization_store",
            EVENT_AUTHORIZATION_STORE_IDENTITY,
            ed25519_public_key_bytes(EVENT_AUTHORIZATION_STORE_PRIVATE_KEY),
        ),
        EVENT_RESERVATION_STORE_KEY_ID: CustodyRoleTrustAnchor(
            "reservation_store",
            EVENT_RESERVATION_STORE_IDENTITY,
            ed25519_public_key_bytes(EVENT_RESERVATION_STORE_PRIVATE_KEY),
        ),
        EVENT_UNUSED_CUSTODY_KEY_ID: CustodyRoleTrustAnchor(
            "audit_store",
            EVENT_UNUSED_CUSTODY_IDENTITY,
            ed25519_public_key_bytes(EVENT_UNUSED_CUSTODY_PRIVATE_KEY),
        ),
    }


def _event_production_review_trust() -> dict[str, ProductionReviewCarrierTrustAnchor]:
    return {
        PRODUCTION_REVIEW_KEY_ID: ProductionReviewCarrierTrustAnchor(
            PRODUCTION_REVIEWER_IDENTITY,
            ed25519_public_key_bytes(PRODUCTION_REVIEW_PRIVATE_KEY),
        )
    }


def _event_production_authorization_trust() -> dict[
    str, ProductionAuthorizationCarrierTrustAnchor
]:
    return {
        PRODUCTION_AUTHORIZATION_KEY_ID: ProductionAuthorizationCarrierTrustAnchor(
            PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY,
            ed25519_public_key_bytes(PRODUCTION_AUTHORIZATION_PRIVATE_KEY),
        )
    }


def _event_permit_verification_arguments(
    context: dict[str, object],
    *,
    revoked_authority_key_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "expected_permit_id_sha256": context["permit_id_sha256"],
        "expected_study_id_sha256": context["study_id_sha256"],
        "expected_authorization_nonce_sha256": context["authorization_nonce_sha256"],
        "expected_contract_bundle_sha256_rows": context["contract_bundle_sha256_rows"],
        "expected_code_commit_sha": context["code_commit_sha"],
        "expected_source_sha256": context["source_sha256"],
        "expected_source_manifest_sha256": context["source_manifest_sha256"],
        "expected_dependency_manifest_sha256": context["dependency_manifest_sha256"],
        "expected_runtime_manifest_sha256": context["runtime_manifest_sha256"],
        "expected_seed": context["seed"],
        "expected_command_argv": context["command_argv"],
        "expected_artifact_output_root_identity_sha256": context[
            "artifact_output_root_identity_sha256"
        ],
        "minimum_external_log_sequence": 17,
        "expected_external_log_checkpoint_sha256": (EVENT_PERMIT_CHECKPOINT_SHA256),
        "revoked_authority_key_ids": revoked_authority_key_ids,
        "revoked_permit_sha256s": (),
        "superseded_permit_sha256s": (),
        "consumed_permit_sha256s": (),
    }


def _event_base_reverification_arguments(
    context: dict[str, object],
    event_one: dict[str, object],
    event_two: dict[str, object],
    *,
    current_status_snapshot_sha256: str,
    current_status_checkpoint_sha256: str = EVENT_STATUS_TWO_CHECKPOINT_SHA256,
    revoked_authority_key_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "trusted_authority_keys": _event_authority_trust(),
        "trusted_custody_keys": _event_custody_trust(),
        "permit_verification_arguments": _event_permit_verification_arguments(
            context,
            revoked_authority_key_ids=revoked_authority_key_ids,
        ),
        "revoked_authority_key_ids": revoked_authority_key_ids,
        "expected_current_status_snapshot_sha256": (current_status_snapshot_sha256),
        "expected_current_status_checkpoint_sha256": (current_status_checkpoint_sha256),
        "expected_sequence_one_custody_event_sha256": event_one["custody_event_sha256"],
        "expected_sequence_one_from_role": "run_custodian",
        "expected_sequence_one_from_role_identity_sha256": CUSTODIAN_IDENTITY,
        "expected_sequence_one_from_key_id": EVENT_RUN_CUSTODIAN_KEY_ID,
        "expected_sequence_one_to_role": "artifact_store",
        "expected_sequence_one_to_role_identity_sha256": (
            EVENT_ARTIFACT_STORE_IDENTITY
        ),
        "expected_sequence_one_to_key_id": EVENT_ARTIFACT_STORE_KEY_ID,
        "expected_sequence_two_custody_event_sha256": event_two["custody_event_sha256"],
        "expected_sequence_two_from_role": "artifact_store",
        "expected_sequence_two_from_role_identity_sha256": (
            EVENT_ARTIFACT_STORE_IDENTITY
        ),
        "expected_sequence_two_from_key_id": EVENT_ARTIFACT_STORE_KEY_ID,
        "expected_sequence_two_to_role": "review_store",
        "expected_sequence_two_to_role_identity_sha256": (EVENT_REVIEW_STORE_IDENTITY),
        "expected_sequence_two_to_key_id": EVENT_REVIEW_STORE_KEY_ID,
    }


def _event_stage3_carrier_reverification_arguments(
    lane: str,
    raw_stage3: bytes,
    *,
    prior_custody_event_sha256: str,
) -> dict[str, object]:
    return {
        "expected_carrier_sha256": json.loads(raw_stage3)["carrier_sha256"],
        "expected_prior_custody_event_sha256": prior_custody_event_sha256,
        "upstream_review_verification_arguments": _upstream_arguments(lane),
        "trusted_production_reviewer_keys": _event_production_review_trust(),
        "revoked_production_reviewer_key_ids": (),
        "revoked_upstream_reviewer_key_ids": (),
        "revoked_carrier_sha256s": (),
        "superseded_carrier_sha256s": (),
        "revoked_upstream_review_sha256s": (),
        "superseded_upstream_review_sha256s": (),
    }


def _event_stage3_reverification_arguments(
    scenario: dict[str, object],
) -> dict[str, object]:
    return {
        "expected_carrier_sha256": scenario["stage3"]["carrier_sha256"],  # type: ignore[index]
        "upstream_review_verification_arguments": _upstream_arguments(
            scenario["lane"]  # type: ignore[arg-type]
        ),
        "trusted_production_reviewer_keys": _event_production_review_trust(),
    }


def _event_stage4_reverification_arguments(
    scenario: dict[str, object],
) -> dict[str, object]:
    return {
        "expected_carrier_sha256": scenario["stage4"]["carrier_sha256"],  # type: ignore[index]
        "upstream_authorization_verification_arguments": _authorization_arguments(
            scenario["lane"]  # type: ignore[arg-type]
        ),
        "trusted_production_authorization_keys": (
            _event_production_authorization_trust()
        ),
    }


def _event_reverification_arguments(
    event: dict[str, object],
) -> dict[str, object]:
    return {
        "expected_custody_event_sha256": event["custody_event_sha256"],
        "expected_from_role": event["from_role"],
        "expected_from_role_identity_sha256": event["from_role_identity_sha256"],
        "expected_from_key_id": event["from_key_id"],
        "expected_to_role": event["to_role"],
        "expected_to_role_identity_sha256": event["to_role_identity_sha256"],
        "expected_to_key_id": event["to_key_id"],
    }


def _event_scenario(
    lane: str = "energy_force",
    *,
    stage3_prior_custody_event_sha256: str | None = None,
    sequence_three_from_unused_custodian: bool = False,
    permit_expires_at: datetime | None = None,
    permit_one_use_integer: bool = False,
    status_one_issued_at: datetime | None = None,
) -> dict[str, object]:
    template_context = _run_context()
    permit = build_signed_production_evidence_permit(
        permit_id_sha256=PERMIT_ID_SHA256,
        lane=lane,
        study_id_sha256=STUDY_ID_SHA256,
        run_id_sha256=RUN_ID_SHA256,
        authorization_nonce_sha256=AUTHORIZATION_NONCE_SHA256,
        contract_bundle_sha256_rows=template_context["contract_bundle_sha256_rows"],  # type: ignore[arg-type]
        code_commit_sha=template_context["code_commit_sha"],  # type: ignore[arg-type]
        source_sha256=template_context["source_sha256"],  # type: ignore[arg-type]
        source_manifest_sha256=template_context["source_manifest_sha256"],  # type: ignore[arg-type]
        dependency_manifest_sha256=template_context["dependency_manifest_sha256"],  # type: ignore[arg-type]
        runtime_manifest_sha256=template_context["runtime_manifest_sha256"],  # type: ignore[arg-type]
        expected_custodian_identity_sha256=CUSTODIAN_IDENTITY,
        expected_enrolled_host_identity_sha256=HOST_IDENTITY,
        seed=template_context["seed"],  # type: ignore[arg-type]
        command_argv=template_context["command_argv"],  # type: ignore[arg-type]
        artifact_output_root_identity_sha256=template_context[
            "artifact_output_root_identity_sha256"
        ],  # type: ignore[arg-type]
        authority_identity_sha256=EVIDENCE_AUTHORITY_IDENTITY,
        authority_key_id=EVIDENCE_AUTHORITY_KEY_ID,
        signing_key=EVENT_PERMIT_AUTHORITY_PRIVATE_KEY,
        issued_at=EVENT_PERMIT_ISSUED_AT,
        expires_at=(
            EVENT_PERMIT_ISSUED_AT + timedelta(hours=24)
            if permit_expires_at is None
            else permit_expires_at
        ),
        external_log_sequence=17,
        external_log_checkpoint_sha256=EVENT_PERMIT_CHECKPOINT_SHA256,
    )
    if permit_one_use_integer:
        permit.pop("signature")
        permit.pop("permit_sha256")
        permit["one_use_permit"] = 1
        permit["permit_sha256"] = hashlib.sha256(_canonical(permit)).hexdigest()
        permit["signature"] = {
            "algorithm": "ed25519",
            "key_id": EVIDENCE_AUTHORITY_KEY_ID,
            "value": sign_ed25519(
                _canonical(permit),
                EVENT_PERMIT_AUTHORITY_PRIVATE_KEY,
            ),
        }
    raw_permit = _canonical(permit)
    permit_sha256 = permit["permit_sha256"]
    status_one = build_signed_production_evidence_status_snapshot(
        permit_sha256=permit_sha256,
        run_id_sha256=RUN_ID_SHA256,
        lane=lane,
        custodian_identity_sha256=CUSTODIAN_IDENTITY,
        enrolled_host_identity_sha256=HOST_IDENTITY,
        status_sequence=1,
        external_log_checkpoint_sha256=EVENT_STATUS_ONE_CHECKPOINT_SHA256,
        previous_snapshot_sha256=None,
        issued_at=(
            EVENT_STATUS_ONE_ISSUED_AT
            if status_one_issued_at is None
            else status_one_issued_at
        ),
        authority_identity_sha256=STATUS_AUTHORITY_IDENTITY,
        authority_key_id=STATUS_AUTHORITY_KEY_ID,
        signing_key=EVENT_STATUS_AUTHORITY_PRIVATE_KEY,
    )
    raw_status_one = _canonical(status_one)
    status_two = build_signed_production_evidence_status_snapshot(
        permit_sha256=permit_sha256,
        run_id_sha256=RUN_ID_SHA256,
        lane=lane,
        custodian_identity_sha256=CUSTODIAN_IDENTITY,
        enrolled_host_identity_sha256=HOST_IDENTITY,
        status_sequence=2,
        external_log_checkpoint_sha256=EVENT_STATUS_TWO_CHECKPOINT_SHA256,
        previous_snapshot_sha256=status_one["snapshot_sha256"],
        issued_at=EVENT_STATUS_TWO_ISSUED_AT,
        authority_identity_sha256=STATUS_AUTHORITY_IDENTITY,
        authority_key_id=STATUS_AUTHORITY_KEY_ID,
        signing_key=EVENT_STATUS_AUTHORITY_PRIVATE_KEY,
    )
    raw_status_two = _canonical(status_two)
    context = dict(template_context)
    context["permit_sha256"] = permit_sha256
    context["current_status_snapshot_sha256"] = status_two["snapshot_sha256"]
    event_one = build_signed_production_custody_event(
        raw_artifact_bytes=raw_permit,
        inner_schema_id=PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
        artifact_stage="production_permit",
        prior_custody_event_sha256=None,
        custody_sequence=1,
        permit_sha256=permit_sha256,
        run_id_sha256=RUN_ID_SHA256,
        lane=lane,
        custodian_identity_sha256=CUSTODIAN_IDENTITY,
        enrolled_host_identity_sha256=HOST_IDENTITY,
        from_role="run_custodian",
        from_role_identity_sha256=CUSTODIAN_IDENTITY,
        from_key_id=EVENT_RUN_CUSTODIAN_KEY_ID,
        from_signing_key=EVENT_RUN_CUSTODIAN_PRIVATE_KEY,
        to_role="artifact_store",
        to_role_identity_sha256=EVENT_ARTIFACT_STORE_IDENTITY,
        to_key_id=EVENT_ARTIFACT_STORE_KEY_ID,
        to_signing_key=EVENT_ARTIFACT_STORE_PRIVATE_KEY,
        handed_off_at=EVENT_SEQUENCE_ONE_HANDED_OFF_AT,
        received_at=EVENT_SEQUENCE_ONE_RECEIVED_AT,
        status_snapshot_sha256=status_one["snapshot_sha256"],
    )
    raw_event_one = _canonical(event_one)
    event_two = build_signed_production_custody_event(
        raw_artifact_bytes=raw_status_one,
        inner_schema_id=PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        artifact_stage="status_snapshot",
        prior_custody_event_sha256=event_one["custody_event_sha256"],
        custody_sequence=2,
        permit_sha256=permit_sha256,
        run_id_sha256=RUN_ID_SHA256,
        lane=lane,
        custodian_identity_sha256=CUSTODIAN_IDENTITY,
        enrolled_host_identity_sha256=HOST_IDENTITY,
        from_role="artifact_store",
        from_role_identity_sha256=EVENT_ARTIFACT_STORE_IDENTITY,
        from_key_id=EVENT_ARTIFACT_STORE_KEY_ID,
        from_signing_key=EVENT_ARTIFACT_STORE_PRIVATE_KEY,
        to_role="review_store",
        to_role_identity_sha256=EVENT_REVIEW_STORE_IDENTITY,
        to_key_id=EVENT_REVIEW_STORE_KEY_ID,
        to_signing_key=EVENT_REVIEW_STORE_PRIVATE_KEY,
        handed_off_at=EVENT_SEQUENCE_TWO_HANDED_OFF_AT,
        received_at=EVENT_SEQUENCE_TWO_RECEIVED_AT,
        status_snapshot_sha256=status_one["snapshot_sha256"],
    )
    raw_event_two = _canonical(event_two)
    actual_sequence_two_sha256 = event_two["custody_event_sha256"]
    stage3_prior = (
        actual_sequence_two_sha256
        if stage3_prior_custody_event_sha256 is None
        else stage3_prior_custody_event_sha256
    )
    raw_review = _raw_review(lane)
    stage3 = build_signed_production_pre_execution_review_carrier(
        raw_review_attestation_bytes=raw_review,
        lane=lane,
        run_context=context,
        upstream_review_verification_arguments=_upstream_arguments(lane),
        prior_custody_event_sha256=stage3_prior,
        production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
        production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
        signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
        signed_at=SIGNED_AT,
        expires_at=CARRIER_EXPIRES_AT,
    )
    raw_stage3 = _canonical(stage3)
    if sequence_three_from_unused_custodian:
        sequence_three_from = {
            "role": "audit_store",
            "identity": EVENT_UNUSED_CUSTODY_IDENTITY,
            "key_id": EVENT_UNUSED_CUSTODY_KEY_ID,
            "private_key": EVENT_UNUSED_CUSTODY_PRIVATE_KEY,
        }
    else:
        sequence_three_from = {
            "role": "review_store",
            "identity": EVENT_REVIEW_STORE_IDENTITY,
            "key_id": EVENT_REVIEW_STORE_KEY_ID,
            "private_key": EVENT_REVIEW_STORE_PRIVATE_KEY,
        }
    event_three = build_signed_production_pre_execution_review_custody_extension_event(
        raw_pre_execution_review_carrier_bytes=raw_stage3,
        raw_review_attestation_bytes=raw_review,
        lane=lane,
        run_context=context,
        upstream_review_verification_arguments=_upstream_arguments(lane),
        trusted_production_reviewer_keys=_event_production_review_trust(),
        prior_custody_event_sha256=stage3_prior,
        from_role=sequence_three_from["role"],  # type: ignore[arg-type]
        from_role_identity_sha256=sequence_three_from["identity"],  # type: ignore[arg-type]
        from_key_id=sequence_three_from["key_id"],  # type: ignore[arg-type]
        from_signing_key=sequence_three_from["private_key"],  # type: ignore[arg-type]
        to_role="authorization_store",
        to_role_identity_sha256=EVENT_AUTHORIZATION_STORE_IDENTITY,
        to_key_id=EVENT_AUTHORIZATION_STORE_KEY_ID,
        to_signing_key=EVENT_AUTHORIZATION_STORE_PRIVATE_KEY,
        handed_off_at=EVENT_SEQUENCE_THREE_HANDED_OFF_AT,
        received_at=EVENT_SEQUENCE_THREE_RECEIVED_AT,
        status_snapshot_sha256=status_two["snapshot_sha256"],
    )
    raw_event_three = _canonical(event_three)
    raw_authorization = _raw_authorization(lane, raw_review)
    stage3_carrier_reverification_arguments = (
        _event_stage3_carrier_reverification_arguments(
            lane,
            raw_stage3,
            prior_custody_event_sha256=stage3_prior,
        )
    )
    stage4 = build_signed_production_authorization_carrier(
        raw_authorization_receipt_bytes=raw_authorization,
        raw_review_attestation_bytes=raw_review,
        raw_pre_execution_review_carrier_bytes=raw_stage3,
        lane=lane,
        run_context=context,
        upstream_authorization_verification_arguments=_authorization_arguments(lane),
        pre_execution_review_reverification_arguments=(
            stage3_carrier_reverification_arguments
        ),
        prior_custody_event_sha256=event_three["custody_event_sha256"],
        production_authorization_operator_identity_sha256=(
            PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY
        ),
        production_authorization_key_id=PRODUCTION_AUTHORIZATION_KEY_ID,
        signing_key=PRODUCTION_AUTHORIZATION_PRIVATE_KEY,
        signed_at=AUTHORIZATION_CARRIER_SIGNED_AT,
        expires_at=AUTHORIZATION_CARRIER_EXPIRES_AT,
    )
    raw_stage4 = _canonical(stage4)
    event_four = build_signed_production_authorization_custody_extension_event(
        raw_authorization_carrier_bytes=raw_stage4,
        raw_authorization_receipt_bytes=raw_authorization,
        raw_review_attestation_bytes=raw_review,
        raw_pre_execution_review_carrier_bytes=raw_stage3,
        lane=lane,
        run_context=context,
        upstream_authorization_verification_arguments=_authorization_arguments(lane),
        pre_execution_review_reverification_arguments=(
            stage3_carrier_reverification_arguments
        ),
        trusted_production_authorization_keys=(_event_production_authorization_trust()),
        prior_custody_event_sha256=event_three["custody_event_sha256"],
        from_role="authorization_store",
        from_role_identity_sha256=EVENT_AUTHORIZATION_STORE_IDENTITY,
        from_key_id=EVENT_AUTHORIZATION_STORE_KEY_ID,
        from_signing_key=EVENT_AUTHORIZATION_STORE_PRIVATE_KEY,
        to_role="reservation_store",
        to_role_identity_sha256=EVENT_RESERVATION_STORE_IDENTITY,
        to_key_id=EVENT_RESERVATION_STORE_KEY_ID,
        to_signing_key=EVENT_RESERVATION_STORE_PRIVATE_KEY,
        handed_off_at=EVENT_SEQUENCE_FOUR_HANDED_OFF_AT,
        received_at=EVENT_SEQUENCE_FOUR_RECEIVED_AT,
        status_snapshot_sha256=status_two["snapshot_sha256"],
    )
    raw_event_four = _canonical(event_four)
    base_reverification_arguments = _event_base_reverification_arguments(
        context,
        event_one,
        event_two,
        current_status_snapshot_sha256=status_two["snapshot_sha256"],
    )
    return {
        "lane": lane,
        "context": context,
        "permit": permit,
        "raw_permit": raw_permit,
        "status_lineage": [status_one, status_two],
        "raw_status_lineage": [raw_status_one, raw_status_two],
        "event_one": event_one,
        "raw_event_one": raw_event_one,
        "event_two": event_two,
        "raw_event_two": raw_event_two,
        "raw_review": raw_review,
        "stage3": stage3,
        "raw_stage3": raw_stage3,
        "event_three": event_three,
        "raw_event_three": raw_event_three,
        "raw_authorization": raw_authorization,
        "stage4": stage4,
        "raw_stage4": raw_stage4,
        "event_four": event_four,
        "raw_event_four": raw_event_four,
        "base_reverification_arguments": base_reverification_arguments,
    }


def _event_scenario_with_current_status_rows(
    scenario: dict[str, object],
    *,
    revoked_key_rows: tuple[dict[str, str], ...] = (),
    revoked_artifact_rows: tuple[dict[str, str], ...] = (),
    supersession_rows: tuple[dict[str, str], ...] = (),
) -> dict[str, object]:
    status_lineage = scenario["status_lineage"]
    status_two = status_lineage[-1]  # type: ignore[index]
    status_three = build_signed_production_evidence_status_snapshot(
        permit_sha256=scenario["permit"]["permit_sha256"],  # type: ignore[index]
        run_id_sha256=RUN_ID_SHA256,
        lane=scenario["lane"],  # type: ignore[arg-type]
        custodian_identity_sha256=CUSTODIAN_IDENTITY,
        enrolled_host_identity_sha256=HOST_IDENTITY,
        status_sequence=3,
        external_log_checkpoint_sha256=EVENT_STATUS_THREE_CHECKPOINT_SHA256,
        previous_snapshot_sha256=status_two["snapshot_sha256"],
        issued_at=EVENT_STATUS_THREE_ISSUED_AT,
        authority_identity_sha256=STATUS_AUTHORITY_IDENTITY,
        authority_key_id=STATUS_AUTHORITY_KEY_ID,
        signing_key=EVENT_STATUS_AUTHORITY_PRIVATE_KEY,
        revoked_key_rows=revoked_key_rows,
        revoked_artifact_rows=revoked_artifact_rows,
        supersession_rows=supersession_rows,
    )
    extended = dict(scenario)
    extended["status_lineage"] = [*status_lineage, status_three]  # type: ignore[misc]
    extended["raw_status_lineage"] = [
        *scenario["raw_status_lineage"],  # type: ignore[misc]
        _canonical(status_three),
    ]
    revoked_authority_key_ids = tuple(sorted(row["key_id"] for row in revoked_key_rows))
    extended["base_reverification_arguments"] = _event_base_reverification_arguments(
        scenario["context"],  # type: ignore[arg-type]
        scenario["event_one"],  # type: ignore[arg-type]
        scenario["event_two"],  # type: ignore[arg-type]
        current_status_snapshot_sha256=status_three["snapshot_sha256"],
        current_status_checkpoint_sha256=(EVENT_STATUS_THREE_CHECKPOINT_SHA256),
        revoked_authority_key_ids=revoked_authority_key_ids,
    )
    return extended


def _verify_event_three(scenario: dict[str, object], **overrides: object):
    values: dict[str, object] = {
        "source": scenario["raw_event_three"],
        "raw_pre_execution_review_carrier_bytes": scenario["raw_stage3"],
        "raw_review_attestation_bytes": scenario["raw_review"],
        "raw_permit_bytes": scenario["raw_permit"],
        "raw_status_lineage_bytes": scenario["raw_status_lineage"],
        "raw_sequence_one_custody_event_bytes": scenario["raw_event_one"],
        "raw_sequence_two_custody_event_bytes": scenario["raw_event_two"],
        "expected_run_context": scenario["context"],
        "base_reverification_arguments": scenario["base_reverification_arguments"],
        "stage3_reverification_arguments": (
            _event_stage3_reverification_arguments(scenario)
        ),
        "event_reverification_arguments": _event_reverification_arguments(
            scenario["event_three"]  # type: ignore[arg-type]
        ),
        "checked_at": AUTHORIZATION_CHECKED_AT,
    }
    values.update(overrides)
    return verify_signed_production_pre_execution_review_custody_extension_event(  # type: ignore[arg-type]
        **values
    )


def _verify_event_four(scenario: dict[str, object], **overrides: object):
    values: dict[str, object] = {
        "source": scenario["raw_event_four"],
        "raw_authorization_carrier_bytes": scenario["raw_stage4"],
        "raw_authorization_receipt_bytes": scenario["raw_authorization"],
        "raw_review_attestation_bytes": scenario["raw_review"],
        "raw_pre_execution_review_carrier_bytes": scenario["raw_stage3"],
        "raw_sequence_three_custody_event_bytes": scenario["raw_event_three"],
        "raw_permit_bytes": scenario["raw_permit"],
        "raw_status_lineage_bytes": scenario["raw_status_lineage"],
        "raw_sequence_one_custody_event_bytes": scenario["raw_event_one"],
        "raw_sequence_two_custody_event_bytes": scenario["raw_event_two"],
        "expected_run_context": scenario["context"],
        "base_reverification_arguments": scenario["base_reverification_arguments"],
        "stage3_reverification_arguments": (
            _event_stage3_reverification_arguments(scenario)
        ),
        "sequence_three_event_reverification_arguments": (
            _event_reverification_arguments(
                scenario["event_three"]  # type: ignore[arg-type]
            )
        ),
        "stage4_reverification_arguments": (
            _event_stage4_reverification_arguments(scenario)
        ),
        "event_reverification_arguments": _event_reverification_arguments(
            scenario["event_four"]  # type: ignore[arg-type]
        ),
        "checked_at": AUTHORIZATION_CHECKED_AT,
    }
    values.update(overrides)
    return verify_signed_production_authorization_custody_extension_event(  # type: ignore[arg-type]
        **values
    )


def _resign_extension_event(
    event: dict[str, object],
    *,
    from_private_key: bytes,
    to_private_key: bytes,
) -> dict[str, object]:
    payload = deepcopy(event)
    payload.pop("signatures")
    payload.pop("custody_event_sha256")
    payload["custody_event_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    message = _canonical(payload)
    payload["signatures"] = {
        "from": {
            "algorithm": "ed25519",
            "key_id": payload["from_key_id"],
            "value": sign_ed25519(message, from_private_key),
        },
        "to": {
            "algorithm": "ed25519",
            "key_id": payload["to_key_id"],
            "value": sign_ed25519(message, to_private_key),
        },
    }
    return payload


def test_contract_is_frozen_additive_and_claim_closed() -> None:
    contract = (
        validation_production_review_authorization_custody_extension_contract_document()
    )
    decision = validation_production_review_authorization_custody_extension_decision()

    assert contract["contract_sha256"] == (
        FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    assert contract["superseded_contract_sha256"] == (
        FROZEN_LEGACY_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V6
    )
    assert contract["purpose"]["base_custody_v1_modified"] is False
    assert contract["purpose"]["pre_execution_review_carrier_implemented"] is True
    assert contract["purpose"]["authorization_carrier_implemented"] is True
    assert contract["purpose"]["custody_extension_event_implemented"] is True
    assert contract["custody_scope"]["implemented_companion_carrier_stages"] == [
        "pre_execution_review",
        "authorization",
    ]
    assert contract["custody_scope"]["authorization_stage_implemented"] is True
    assert contract["custody_scope"]["verified_custody_sequence"] == [
        "production_permit",
        "status_snapshot",
        "pre_execution_review",
        "authorization",
    ]
    assert contract["custody_scope"]["custody_extension_events_implemented"] is True
    assert contract["custody_scope"]["custody_successor_uniqueness_enforced"] is False
    assert (
        contract["custody_extension_event"][
            "base_status_lineage_not_before_permit_required"
        ]
        is True
    )
    assert contract["resource_limits"][
        "ancestor_exact_json_integer_field_allowlists"
    ] == {
        "base_permit": ["external_log_sequence", "seed"],
        "base_status": ["status_sequence"],
        "base_custody_event": [
            "custody_sequence",
            "raw_artifact_byte_count",
        ],
        "upstream_review": [],
        "upstream_authorization": ["maximum_execution_count"],
    }
    assert contract["claim_policy"]["claim_safe"] is False
    assert (
        require_validation_production_review_authorization_custody_extension_contract_document(
            contract
        )
        == contract
    )
    assert decision["full_asymmetric_signature_chain_implemented"] is True
    assert decision["production_asymmetric_signature_chain_provisioned"] is False
    assert decision["authorization_carrier_implemented"] is True
    assert decision["custody_extension_event_implemented"] is True
    assert decision["energy_force_upstream_symmetric_hmac_chain"] is False
    assert decision["production_validation_execution_authorized"] is False
    assert decision["claim_safe"] is False


def test_contract_rejects_tamper_and_mapping_subclass() -> None:
    contract = deepcopy(
        validation_production_review_authorization_custody_extension_contract_document()
    )
    contract["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="does not match the frozen record",
    ):
        require_validation_production_review_authorization_custody_extension_contract_document(
            contract
        )

    class DictSubclass(dict):
        pass

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="exact built-in dict",
    ):
        require_validation_production_review_authorization_custody_extension_contract_document(
            DictSubclass(
                validation_production_review_authorization_custody_extension_contract_document()
            )
        )


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_sequence_three_and_four_events_reverify_full_raw_prefix_for_both_lanes(
    lane: str,
) -> None:
    scenario = _event_scenario(lane)
    sequence_three = _verify_event_three(scenario)
    sequence_four = _verify_event_four(scenario)

    permit_bundle = {
        row["contract_id"]: row["sha256"]
        for row in scenario["permit"]["contract_bundle_sha256_rows"]  # type: ignore[index]
    }
    assert permit_bundle[
        VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_ID
    ] == (
        FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    for carrier_name in ("stage3", "stage4"):
        carrier = scenario[carrier_name]
        for field, value in scenario["context"].items():  # type: ignore[union-attr]
            if field == "contract_bundle_sha256_rows":
                assert {
                    row["contract_id"]: row["sha256"]
                    for row in carrier[field]  # type: ignore[index]
                } == value
            else:
                assert carrier[field] == value  # type: ignore[index]
    assert scenario["event_three"]["schema_id"] == (  # type: ignore[index]
        PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_EVENT_SCHEMA_ID
    )
    assert sequence_three.artifact_stage == "pre_execution_review"
    assert sequence_three.custody_sequence == 3
    assert (
        sequence_three.prior_custody_event_sha256
        == scenario["event_two"][  # type: ignore[index]
            "custody_event_sha256"
        ]
    )
    assert sequence_three.custody_event_lineage_sha256s[-1] == (
        sequence_three.custody_event_sha256
    )
    assert sequence_four.artifact_stage == "authorization"
    assert sequence_four.custody_sequence == 4
    assert sequence_four.prior_custody_event_sha256 == (
        sequence_three.custody_event_sha256
    )
    assert sequence_four.custody_event_lineage_sha256s == (
        *sequence_three.custody_event_lineage_sha256s,
        sequence_four.custody_event_sha256,
    )
    assert sequence_four.carrier_lineage_sha256s == (
        sequence_three.carrier_sha256,
        sequence_four.carrier_sha256,
    )
    assert sequence_four.full_raw_prefix_reverified is True
    assert sequence_four.dual_custody_signatures_verified is True
    assert sequence_four.custody_successor_uniqueness_enforced is False
    assert sequence_four.eligible_for_atomic_execution_reservation is False
    assert sequence_four.production_validation_execution_authorized is False
    assert sequence_four.scientifically_validated is False
    assert sequence_four.claim_safe is False


def test_sequence_three_rejects_raw_base_prefix_tamper_and_format_transplant() -> None:
    scenario = _event_scenario()
    reformatted_permit = json.dumps(
        json.loads(scenario["raw_permit"]),  # type: ignore[arg-type]
        indent=2,
        sort_keys=True,
    ).encode("ascii")
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_event_three(scenario, raw_permit_bytes=reformatted_permit)

    tampered_sequence_two = deepcopy(scenario["event_two"])
    tampered_sequence_two["claim_safe"] = True  # type: ignore[index]
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_event_three(
            scenario,
            raw_sequence_two_custody_event_bytes=_canonical(tampered_sequence_two),
        )


def test_sequence_three_rejects_wrong_prior_and_predecessor_custody_break() -> None:
    wrong_prior = _event_scenario(stage3_prior_custody_event_sha256="0" * 64)
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_event_three(wrong_prior)

    wrong_custodian = _event_scenario(sequence_three_from_unused_custodian=True)
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="predecessor custody continuity failed",
    ):
        _verify_event_three(wrong_custodian)


def test_sequence_four_internally_reverifies_raw_sequence_three() -> None:
    scenario = _event_scenario()
    tampered = deepcopy(scenario["event_three"])
    tampered["signatures"]["from"]["value"] = "0" * 128  # type: ignore[index]
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="dual signature verification failed",
    ):
        _verify_event_four(
            scenario,
            raw_sequence_three_custody_event_bytes=_canonical(tampered),
        )


@pytest.mark.parametrize("sequence", [3, 4])
def test_extension_events_reject_signature_and_resigned_claim_tamper(
    sequence: int,
) -> None:
    scenario = _event_scenario()
    event_name = "event_three" if sequence == 3 else "event_four"
    event = scenario[event_name]
    tampered_signature = deepcopy(event)
    tampered_signature["signatures"]["to"]["value"] = "0" * 128  # type: ignore[index]
    verifier = _verify_event_three if sequence == 3 else _verify_event_four
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="dual signature verification failed",
    ):
        verifier(scenario, source=_canonical(tampered_signature))

    tampered_claim = deepcopy(event)
    tampered_claim["claim_safe"] = True  # type: ignore[index]
    resigned = _resign_extension_event(
        tampered_claim,  # type: ignore[arg-type]
        from_private_key=(
            EVENT_REVIEW_STORE_PRIVATE_KEY
            if sequence == 3
            else EVENT_AUTHORIZATION_STORE_PRIVATE_KEY
        ),
        to_private_key=(
            EVENT_AUTHORIZATION_STORE_PRIVATE_KEY
            if sequence == 3
            else EVENT_RESERVATION_STORE_PRIVATE_KEY
        ),
    )
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        verifier(
            scenario,
            source=_canonical(resigned),
            event_reverification_arguments=_event_reverification_arguments(resigned),
        )


def test_extension_event_bool_fields_reject_integer_equivalents_after_resigning() -> (
    None
):
    scenario = _event_scenario()
    cases = (
        (3, "requires_full_raw_prefix_reverification", 1),
        (3, "custody_successor_uniqueness_enforced", 0),
        (3, "production_validation_execution_authorized", 0),
        (4, "eligible_for_atomic_execution_reservation", 0),
        (4, "full_asymmetric_chain_established", 0),
        (4, "claim_safe", 0),
    )
    for sequence, field, replacement in cases:
        event = deepcopy(scenario["event_three" if sequence == 3 else "event_four"])
        event[field] = replacement  # type: ignore[index]
        resigned = _resign_extension_event(
            event,  # type: ignore[arg-type]
            from_private_key=(
                EVENT_REVIEW_STORE_PRIVATE_KEY
                if sequence == 3
                else EVENT_AUTHORIZATION_STORE_PRIVATE_KEY
            ),
            to_private_key=(
                EVENT_AUTHORIZATION_STORE_PRIVATE_KEY
                if sequence == 3
                else EVENT_RESERVATION_STORE_PRIVATE_KEY
            ),
        )
        verifier = _verify_event_three if sequence == 3 else _verify_event_four
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError
        ):
            verifier(
                scenario,
                source=_canonical(resigned),
                event_reverification_arguments=_event_reverification_arguments(
                    resigned
                ),
            )


def test_extension_full_chain_rejects_base_permit_bool_as_integer() -> None:
    scenario = _event_scenario(permit_one_use_integer=True)
    assert scenario["permit"]["one_use_permit"] == 1  # type: ignore[index]
    assert type(scenario["permit"]["one_use_permit"]) is int  # type: ignore[index]
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_event_three(scenario)


def test_extension_rejects_status_lineage_predating_permit() -> None:
    scenario = _event_scenario(
        status_one_issued_at=EVENT_PERMIT_ISSUED_AT - timedelta(seconds=1)
    )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="status lineage predates the signed production permit",
    ):
        _verify_event_three(scenario)


def test_extension_event_missing_status_after_valid_resigning_is_domain_error() -> None:
    scenario = _event_scenario()
    missing_status = deepcopy(scenario["event_three"])
    missing_status.pop("status_snapshot_sha256")  # type: ignore[union-attr]
    resigned = _resign_extension_event(
        missing_status,  # type: ignore[arg-type]
        from_private_key=EVENT_REVIEW_STORE_PRIVATE_KEY,
        to_private_key=EVENT_AUTHORIZATION_STORE_PRIVATE_KEY,
    )
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_event_three(
            scenario,
            source=_canonical(resigned),
            event_reverification_arguments=_event_reverification_arguments(resigned),
        )


def test_sequence_three_rejects_receive_at_permit_expiry() -> None:
    scenario = _event_scenario(permit_expires_at=EVENT_SEQUENCE_THREE_RECEIVED_AT)
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="prefix or handoff time is invalid",
    ):
        _verify_event_three(scenario)


def test_extension_event_builder_rejects_receive_at_carrier_expiry() -> None:
    scenario = _event_scenario()
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="handoff timestamps are invalid",
    ):
        build_signed_production_pre_execution_review_custody_extension_event(
            raw_pre_execution_review_carrier_bytes=scenario["raw_stage3"],  # type: ignore[arg-type]
            raw_review_attestation_bytes=scenario["raw_review"],  # type: ignore[arg-type]
            lane="energy_force",
            run_context=scenario["context"],  # type: ignore[arg-type]
            upstream_review_verification_arguments=_upstream_arguments("energy_force"),
            trusted_production_reviewer_keys=_event_production_review_trust(),
            prior_custody_event_sha256=scenario["event_two"][  # type: ignore[index]
                "custody_event_sha256"
            ],
            from_role="review_store",
            from_role_identity_sha256=EVENT_REVIEW_STORE_IDENTITY,
            from_key_id=EVENT_REVIEW_STORE_KEY_ID,
            from_signing_key=EVENT_REVIEW_STORE_PRIVATE_KEY,
            to_role="authorization_store",
            to_role_identity_sha256=EVENT_AUTHORIZATION_STORE_IDENTITY,
            to_key_id=EVENT_AUTHORIZATION_STORE_KEY_ID,
            to_signing_key=EVENT_AUTHORIZATION_STORE_PRIVATE_KEY,
            handed_off_at=EVENT_SEQUENCE_THREE_HANDED_OFF_AT,
            received_at=CARRIER_EXPIRES_AT,
            status_snapshot_sha256=scenario["status_lineage"][-1][  # type: ignore[index]
                "snapshot_sha256"
            ],
        )


def test_current_status_rejects_logical_and_raw_event_revoke_or_supersede() -> None:
    scenario = _event_scenario()
    logical_sha256 = scenario["event_four"]["custody_event_sha256"]  # type: ignore[index]
    raw_sha256 = hashlib.sha256(scenario["raw_event_four"]).hexdigest()  # type: ignore[arg-type]
    for action, identity in (
        ("revoke", logical_sha256),
        ("revoke", raw_sha256),
        ("supersede", logical_sha256),
        ("supersede", raw_sha256),
    ):
        if action == "revoke":
            extended = _event_scenario_with_current_status_rows(
                scenario,
                revoked_artifact_rows=(
                    {
                        "artifact_kind": "custody_extension_event",
                        "artifact_sha256": identity,
                        "revoked_at_utc": _event_utc(EVENT_STATUS_THREE_ISSUED_AT),
                        "reason_code": "compromised",
                    },
                ),
            )
        else:
            extended = _event_scenario_with_current_status_rows(
                scenario,
                supersession_rows=(
                    {
                        "artifact_kind": "custody_extension_event",
                        "superseded_sha256": identity,
                        "replacement_sha256": "de" * 32,
                        "superseded_at_utc": _event_utc(EVENT_STATUS_THREE_ISSUED_AT),
                    },
                ),
            )
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError,
            match="currently revoked or superseded",
        ):
            _verify_event_four(extended)


def test_current_status_rejects_revoked_unused_trust_anchor() -> None:
    scenario = _event_scenario()
    extended = _event_scenario_with_current_status_rows(
        scenario,
        revoked_key_rows=(
            {
                "role": "audit_store",
                "key_id": EVENT_UNUSED_CUSTODY_KEY_ID,
                "revoked_at_utc": _event_utc(EVENT_STATUS_THREE_ISSUED_AT),
                "reason_code": "rotation",
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="trust map retains a currently revoked key",
    ):
        _verify_event_four(extended)


def test_extension_event_rejects_internal_production_trust_aliases() -> None:
    scenario = _event_scenario()
    fresh_public_key = ed25519_public_key_bytes(bytes.fromhex("ab" * 32))
    production_review_public_key = ed25519_public_key_bytes(
        PRODUCTION_REVIEW_PRIVATE_KEY
    )
    production_authorization_public_key = ed25519_public_key_bytes(
        PRODUCTION_AUTHORIZATION_PRIVATE_KEY
    )
    for identity, public_key in (
        (PRODUCTION_REVIEWER_IDENTITY, fresh_public_key),
        ("f2" * 32, production_review_public_key),
    ):
        arguments = _event_stage3_reverification_arguments(scenario)
        trust = dict(arguments["trusted_production_reviewer_keys"])  # type: ignore[arg-type]
        trust["unused-production-reviewer-2026-07"] = (
            ProductionReviewCarrierTrustAnchor(identity, public_key)
        )
        arguments["trusted_production_reviewer_keys"] = trust
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError
        ):
            _verify_event_three(
                scenario,
                stage3_reverification_arguments=arguments,
            )

    for identity, public_key in (
        (PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY, fresh_public_key),
        ("f3" * 32, production_authorization_public_key),
    ):
        arguments = _event_stage4_reverification_arguments(scenario)
        trust = dict(arguments["trusted_production_authorization_keys"])  # type: ignore[arg-type]
        trust["unused-production-authorization-2026-07"] = (
            ProductionAuthorizationCarrierTrustAnchor(identity, public_key)
        )
        arguments["trusted_production_authorization_keys"] = trust
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError
        ):
            _verify_event_four(
                scenario,
                stage4_reverification_arguments=arguments,
            )


def test_extension_event_requires_exact_dicts_bytes_and_canonical_json() -> None:
    scenario = _event_scenario()

    class DictSubclass(dict):
        pass

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="event arguments are not exact",
    ):
        _verify_event_three(
            scenario,
            event_reverification_arguments=DictSubclass(
                _event_reverification_arguments(
                    scenario["event_three"]  # type: ignore[arg-type]
                )
            ),
        )
    extra_base_argument = dict(scenario["base_reverification_arguments"])  # type: ignore[arg-type]
    extra_base_argument["verified_prefix"] = object()
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="base sequence-two reverification arguments are not exact",
    ):
        _verify_event_three(
            scenario,
            base_reverification_arguments=extra_base_argument,
        )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="must be non-empty bytes",
    ):
        _verify_event_three(
            scenario,
            source=json.loads(scenario["raw_event_three"]),  # type: ignore[arg-type]
        )
    reformatted = json.dumps(
        json.loads(scenario["raw_event_three"]),  # type: ignore[arg-type]
        indent=2,
        sort_keys=True,
    ).encode("ascii")
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_event_three(scenario, source=reformatted)
    huge_integer = b'{"x":' + (b"1" * 5000) + b"}"
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_event_three(scenario, source=huge_integer)


def test_extension_event_verifiers_accept_no_caller_verification_dto() -> None:
    scenario = _event_scenario()
    fake = object.__new__(
        ProductionReviewAuthorizationCustodyExtensionEventVerification
    )
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        _verify_event_three(scenario, verified_base_prefix=fake)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        _verify_event_four(scenario, verified_sequence_three_event=fake)


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_stage3_carrier_reverifies_exact_raw_review_for_both_lanes(lane: str) -> None:
    carrier_bytes, raw_review = _carrier(lane)
    carrier = json.loads(carrier_bytes.decode("ascii"))
    verified = _verify(carrier_bytes, raw_review, lane=lane)

    assert carrier["schema_id"] == PRODUCTION_PRE_EXECUTION_REVIEW_CARRIER_SCHEMA_ID
    assert carrier["artifact_stage"] == "pre_execution_review"
    assert carrier["lane"] == lane
    assert carrier["permit_sha256"] == PERMIT_SHA256
    assert carrier["run_id_sha256"] == RUN_ID_SHA256
    assert carrier["current_status_snapshot_sha256"] == CURRENT_STATUS_SHA256
    assert carrier["process_launch_identity_sha256"] == (PROCESS_LAUNCH_IDENTITY_SHA256)
    assert carrier["prior_custody_event_sha256"] == PRIOR_CUSTODY_EVENT_SHA256
    assert carrier["upstream_review_reverified"] is True
    assert carrier["full_asymmetric_chain_established"] is True
    assert carrier["production_validation_execution_authorized"] is False
    assert carrier["scientifically_validated"] is False
    assert carrier["claim_safe"] is False
    assert verified.carrier_sha256 == carrier["carrier_sha256"]
    assert verified.lane == lane
    assert verified.pre_execution_review_carrier_verified is True
    assert verified.production_validation_execution_authorized is False
    assert verified.scientifically_validated is False
    assert verified.claim_safe is False


def test_stage3_rejects_ed25519_upstream_tamper_and_raw_transplant() -> None:
    carrier_bytes, raw_review = _carrier("energy_force")
    tampered = json.loads(raw_review.decode("ascii"))
    tampered["review_recommendation"] = "tampered"
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="re-verification failed",
    ):
        _verify(carrier_bytes, _canonical(tampered))

    changed_formatting = json.dumps(
        json.loads(raw_review.decode("ascii")),
        sort_keys=True,
        indent=2,
    ).encode("ascii")
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="fields do not match",
    ):
        _verify(carrier_bytes, changed_formatting)


def test_stage3_rejects_ed25519_upstream_tamper() -> None:
    carrier_bytes, raw_review = _carrier("minimization")
    tampered = json.loads(raw_review.decode("ascii"))
    tampered["claim_safe"] = True
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="re-verification failed",
    ):
        _verify(carrier_bytes, _canonical(tampered), lane="minimization")


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("permit_sha256", "0" * 64),
        ("run_id_sha256", "0" * 64),
        ("authorization_nonce_sha256", "0" * 64),
        ("current_status_snapshot_sha256", "0" * 64),
        ("process_launch_identity_sha256", "0" * 64),
    ],
)
def test_stage3_rejects_context_crosswire(field: str, replacement: str) -> None:
    carrier_bytes, raw_review = _carrier()
    context = _run_context()
    context[field] = replacement
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="fields do not match",
    ):
        _verify(
            carrier_bytes,
            raw_review,
            expected_run_context=context,
        )


def test_stage3_rejects_missing_extension_bundle_binding() -> None:
    context = _run_context()
    context["contract_bundle_sha256_rows"] = {"engine-v2-lane-contract/1.0.0": "1" * 64}
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="omits or cross-wires",
    ):
        build_signed_production_pre_execution_review_carrier(
            raw_review_attestation_bytes=_raw_review("energy_force"),
            lane="energy_force",
            run_context=context,
            upstream_review_verification_arguments=_upstream_arguments("energy_force"),
            prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
            production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
            signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
            signed_at=SIGNED_AT,
            expires_at=CARRIER_EXPIRES_AT,
        )

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="role alias",
    ):
        build_signed_production_pre_execution_review_carrier(
            raw_review_attestation_bytes=_raw_review("energy_force"),
            lane="energy_force",
            run_context=_run_context(),
            upstream_review_verification_arguments=_upstream_arguments("energy_force"),
            prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            production_reviewer_identity_sha256=UPSTREAM_REVIEWER_IDENTITY,
            production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
            signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
            signed_at=SIGNED_AT,
            expires_at=CARRIER_EXPIRES_AT,
        )


def test_stage3_requires_bytes_only_and_rejects_duplicate_json() -> None:
    carrier_bytes, raw_review = _carrier()
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="must be non-empty bytes",
    ):
        _verify(carrier_bytes, raw_review, source=json.loads(carrier_bytes))
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="duplicate JSON key",
    ):
        verify_signed_production_pre_execution_review_carrier(
            b'{"schema_id":"one","schema_id":"two"}',
            raw_review_attestation_bytes=raw_review,
            expected_carrier_sha256="0" * 64,
            expected_lane="energy_force",
            expected_run_context=_run_context(),
            expected_prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            upstream_review_verification_arguments=_upstream_arguments("energy_force"),
            trusted_production_reviewer_keys={
                PRODUCTION_REVIEW_KEY_ID: ProductionReviewCarrierTrustAnchor(
                    PRODUCTION_REVIEWER_IDENTITY,
                    ed25519_public_key_bytes(PRODUCTION_REVIEW_PRIVATE_KEY),
                )
            },
            checked_at=CHECKED_AT,
        )


def test_stage3_rejects_signature_tamper_revocation_and_expiry() -> None:
    carrier_bytes, raw_review = _carrier()
    carrier = json.loads(carrier_bytes.decode("ascii"))
    tampered = deepcopy(carrier)
    tampered["claim_safe"] = True
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="signature verification failed",
    ):
        _verify(_canonical(tampered), raw_review)

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="reviewer key is revoked",
    ):
        _verify(
            carrier_bytes,
            raw_review,
            revoked_production_reviewer_key_ids=(PRODUCTION_REVIEW_KEY_ID,),
        )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="carrier is revoked",
    ):
        _verify(
            carrier_bytes,
            raw_review,
            revoked_carrier_sha256s=(carrier["carrier_sha256"],),
        )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="carrier is revoked",
    ):
        _verify(
            carrier_bytes,
            raw_review,
            revoked_carrier_sha256s=(hashlib.sha256(carrier_bytes).hexdigest(),),
        )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="upstream review is superseded",
    ):
        _verify(
            carrier_bytes,
            raw_review,
            superseded_upstream_review_sha256s=(
                hashlib.sha256(raw_review).hexdigest(),
            ),
        )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="upstream reviewer key is revoked",
    ):
        _verify(
            carrier_bytes,
            raw_review,
            revoked_upstream_reviewer_key_ids=(ENERGY_REVIEW_KEY_ID,),
        )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="not currently valid",
    ):
        _verify(
            carrier_bytes,
            raw_review,
            checked_at=CARRIER_EXPIRES_AT,
        )


def test_stage3_rejects_fake_run_mapping_and_role_aliases() -> None:
    class DictSubclass(dict):
        pass

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="exact built-in dict",
    ):
        build_signed_production_pre_execution_review_carrier(
            raw_review_attestation_bytes=_raw_review("energy_force"),
            lane="energy_force",
            run_context=DictSubclass(_run_context()),  # type: ignore[arg-type]
            upstream_review_verification_arguments=_upstream_arguments("energy_force"),
            prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
            production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
            signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
            signed_at=SIGNED_AT,
            expires_at=CARRIER_EXPIRES_AT,
        )


def test_stage3_requires_exact_canonical_carrier_transport() -> None:
    carrier_bytes, raw_review = _carrier()
    reformatted = json.dumps(
        json.loads(carrier_bytes.decode("ascii")),
        sort_keys=True,
        indent=2,
    ).encode("ascii")
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="exact canonical JSON",
    ):
        _verify(reformatted, raw_review)


@pytest.mark.parametrize(
    ("context_field", "production_identity", "match"),
    [
        ("custodian_identity_sha256", AUTHOR_IDENTITY, "role alias"),
        (
            "enrolled_host_identity_sha256",
            UPSTREAM_REVIEWER_IDENTITY,
            "role alias",
        ),
        (
            "enrolled_host_identity_sha256",
            PRODUCTION_REVIEWER_IDENTITY,
            "role alias",
        ),
    ],
)
def test_stage3_rejects_author_reviewer_or_production_identity_context_alias(
    context_field: str,
    production_identity: str,
    match: str,
) -> None:
    context = _run_context()
    context[context_field] = production_identity
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match=match,
    ):
        build_signed_production_pre_execution_review_carrier(
            raw_review_attestation_bytes=_raw_review("energy_force"),
            lane="energy_force",
            run_context=context,
            upstream_review_verification_arguments=_upstream_arguments("energy_force"),
            prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
            production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
            signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
            signed_at=SIGNED_AT,
            expires_at=CARRIER_EXPIRES_AT,
        )


def test_stage3_rejects_unused_cross_trust_alias_and_same_ed25519_keypair() -> None:
    carrier_bytes, raw_review = _carrier("minimization")
    production_trust = {
        PRODUCTION_REVIEW_KEY_ID: ProductionReviewCarrierTrustAnchor(
            PRODUCTION_REVIEWER_IDENTITY,
            ed25519_public_key_bytes(PRODUCTION_REVIEW_PRIVATE_KEY),
        ),
        "unused-production-reviewer-2026-07": ProductionReviewCarrierTrustAnchor(
            "0" * 64,
            ed25519_public_key_bytes(MINIMIZATION_REVIEW_PRIVATE_KEY),
        ),
    }
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="global alias",
    ):
        _verify(
            carrier_bytes,
            raw_review,
            lane="minimization",
            trusted_production_reviewer_keys=production_trust,
        )

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="key material aliases",
    ):
        build_signed_production_pre_execution_review_carrier(
            raw_review_attestation_bytes=raw_review,
            lane="minimization",
            run_context=_run_context(),
            upstream_review_verification_arguments=_upstream_arguments("minimization"),
            prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
            production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
            signing_key=MINIMIZATION_REVIEW_PRIVATE_KEY,
            signed_at=SIGNED_AT,
            expires_at=CARRIER_EXPIRES_AT,
        )

    author_alias_arguments = _upstream_arguments("energy_force")
    author_alias_arguments["trusted_reviewer_keys"] = {
        ENERGY_REVIEW_KEY_ID: ScientificReviewerTrustAnchor(
            UPSTREAM_REVIEWER_IDENTITY,
            ENERGY_REVIEW_PUBLIC_KEY,
        ),
        "unused-author-alias-2026-07": ScientificReviewerTrustAnchor(
            AUTHOR_IDENTITY,
            ed25519_public_key_bytes(bytes.fromhex("12" * 32)),
        ),
    }
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="role alias",
    ):
        build_signed_production_pre_execution_review_carrier(
            raw_review_attestation_bytes=_raw_review("energy_force"),
            lane="energy_force",
            run_context=_run_context(),
            upstream_review_verification_arguments=author_alias_arguments,
            prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
            production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
            signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
            signed_at=SIGNED_AT,
            expires_at=CARRIER_EXPIRES_AT,
        )


@pytest.mark.parametrize(
    ("target_field", "source_field"),
    [
        ("enrolled_host_identity_sha256", "custodian_identity_sha256"),
        (
            "current_status_authority_identity_sha256",
            "evidence_authority_identity_sha256",
        ),
        ("current_status_authority_key_id", "evidence_authority_key_id"),
    ],
)
def test_stage3_rejects_bound_context_internal_role_alias(
    target_field: str,
    source_field: str,
) -> None:
    context = _run_context()
    context[target_field] = context[source_field]
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="role alias",
    ):
        build_signed_production_pre_execution_review_carrier(
            raw_review_attestation_bytes=_raw_review("energy_force"),
            lane="energy_force",
            run_context=context,
            upstream_review_verification_arguments=_upstream_arguments("energy_force"),
            prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
            production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
            signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
            signed_at=SIGNED_AT,
            expires_at=CARRIER_EXPIRES_AT,
        )


def test_stage3_preflights_json_depth_and_energy_public_key_bytes() -> None:
    raw_review = _raw_review("energy_force")
    deeply_nested = b'{"x":' + (b"[" * 129) + b"0" + (b"]" * 129) + b"}"
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="JSON nesting bound",
    ):
        verify_signed_production_pre_execution_review_carrier(
            deeply_nested,
            raw_review_attestation_bytes=raw_review,
            expected_carrier_sha256="0" * 64,
            expected_lane="energy_force",
            expected_run_context=_run_context(),
            expected_prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            upstream_review_verification_arguments=_upstream_arguments("energy_force"),
            trusted_production_reviewer_keys={
                PRODUCTION_REVIEW_KEY_ID: ProductionReviewCarrierTrustAnchor(
                    PRODUCTION_REVIEWER_IDENTITY,
                    ed25519_public_key_bytes(PRODUCTION_REVIEW_PRIVATE_KEY),
                )
            },
            checked_at=CHECKED_AT,
        )

    invalid_anchor = object.__new__(ScientificReviewerTrustAnchor)
    object.__setattr__(
        invalid_anchor,
        "reviewer_identity_sha256",
        UPSTREAM_REVIEWER_IDENTITY,
    )
    object.__setattr__(invalid_anchor, "verification_key", b"x" * 31)
    oversized_arguments = _upstream_arguments("energy_force")
    oversized_arguments["trusted_reviewer_keys"] = {
        ENERGY_REVIEW_KEY_ID: invalid_anchor
    }
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="public key must contain exactly 32 bytes",
    ):
        build_signed_production_pre_execution_review_carrier(
            raw_review_attestation_bytes=raw_review,
            lane="energy_force",
            run_context=_run_context(),
            upstream_review_verification_arguments=oversized_arguments,
            prior_custody_event_sha256=PRIOR_CUSTODY_EVENT_SHA256,
            production_reviewer_identity_sha256=PRODUCTION_REVIEWER_IDENTITY,
            production_reviewer_key_id=PRODUCTION_REVIEW_KEY_ID,
            signing_key=PRODUCTION_REVIEW_PRIVATE_KEY,
            signed_at=SIGNED_AT,
            expires_at=CARRIER_EXPIRES_AT,
        )


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_stage4_authorization_carrier_reverifies_full_raw_prefix_and_is_claim_closed(
    lane: str,
) -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier(
        lane
    )
    carrier = json.loads(carrier_bytes.decode("ascii"))
    authorization = json.loads(raw_authorization.decode("ascii"))
    stage3 = json.loads(raw_stage3.decode("ascii"))
    verified = _verify_authorization(
        carrier_bytes,
        raw_authorization,
        raw_review,
        raw_stage3,
        lane=lane,
    )

    assert carrier["schema_id"] == PRODUCTION_AUTHORIZATION_CARRIER_SCHEMA_ID
    assert carrier["artifact_stage"] == "authorization"
    assert carrier["lane"] == lane
    assert carrier["permit_sha256"] == PERMIT_SHA256
    assert carrier["study_id_sha256"] == STUDY_ID_SHA256
    assert carrier["run_id_sha256"] == RUN_ID_SHA256
    assert carrier["authorization_nonce_sha256"] == AUTHORIZATION_NONCE_SHA256
    assert carrier["current_status_snapshot_sha256"] == CURRENT_STATUS_SHA256
    assert carrier["process_launch_identity_sha256"] == (PROCESS_LAUNCH_IDENTITY_SHA256)
    assert carrier["prior_custody_event_sha256"] == STAGE3_CUSTODY_EVENT_SHA256
    assert carrier["pre_execution_review_carrier_sha256"] == stage3["carrier_sha256"]
    assert (
        carrier["pre_execution_review_raw_sha256"]
        == hashlib.sha256(raw_stage3).hexdigest()
    )
    assert (
        carrier["upstream_review_raw_sha256"] == hashlib.sha256(raw_review).hexdigest()
    )
    assert (
        carrier["upstream_authorization_receipt_sha256"]
        == authorization["receipt_sha256"]
    )
    assert (
        carrier["upstream_authorization_raw_sha256"]
        == hashlib.sha256(raw_authorization).hexdigest()
    )
    assert carrier["pre_execution_review_reverified"] is True
    assert carrier["upstream_review_and_authorization_reverified"] is True
    assert carrier["eligible_for_atomic_execution_reservation"] is False
    assert carrier["full_asymmetric_chain_established"] is True
    assert carrier["production_validation_execution_authorized"] is False
    assert carrier["production_validation_results_collected"] is False
    assert carrier["scientifically_validated"] is False
    assert carrier["parameter_fitting_authorized"] is False
    assert carrier["product_qualified"] is False
    assert carrier["claim_safe"] is False

    assert verified.carrier_sha256 == carrier["carrier_sha256"]
    assert verified.raw_carrier_sha256 == hashlib.sha256(carrier_bytes).hexdigest()
    assert verified.pre_execution_review_carrier_sha256 == stage3["carrier_sha256"]
    assert (
        verified.upstream_authorization_receipt_sha256
        == authorization["receipt_sha256"]
    )
    assert verified.authorization_carrier_verified is True
    assert verified.eligible_for_atomic_execution_reservation is False
    assert verified.production_validation_execution_authorized is False
    assert verified.scientifically_validated is False
    assert verified.parameter_fitting_authorized is False
    assert verified.product_qualified is False
    assert verified.claim_safe is False


@pytest.mark.parametrize(
    ("source_lane", "expected_lane"),
    [
        ("energy_force", "minimization"),
        ("minimization", "energy_force"),
    ],
)
def test_stage4_rejects_bidirectional_lane_transplant(
    source_lane: str,
    expected_lane: str,
) -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier(
        source_lane
    )

    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            lane=expected_lane,
        )


@pytest.mark.parametrize(
    ("lane", "revoked_key_id"),
    [
        ("energy_force", ENERGY_REVIEW_KEY_ID),
        ("minimization", MINIMIZATION_REVIEW_KEY_ID),
    ],
)
def test_stage4_propagates_nested_upstream_reviewer_key_revocation(
    lane: str,
    revoked_key_id: str,
) -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier(
        lane
    )
    stage3_arguments = _stage3_reverification_arguments(
        lane,
        raw_stage3,
        revoked_upstream_reviewer_key_ids=(revoked_key_id,),
    )

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="upstream reviewer key is revoked",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            lane=lane,
            pre_execution_review_reverification_arguments=stage3_arguments,
        )


@pytest.mark.parametrize(
    "raw_name",
    ["review", "authorization", "stage3"],
)
def test_stage4_rejects_tampered_raw_review_authorization_or_stage3(
    raw_name: str,
) -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    raw_values = {
        "review": raw_review,
        "authorization": raw_authorization,
        "stage3": raw_stage3,
    }
    document = json.loads(raw_values[raw_name].decode("ascii"))
    document["claim_safe"] = True
    raw_values[raw_name] = _canonical(document)
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_authorization(
            carrier_bytes,
            raw_values["authorization"],
            raw_values["review"],
            raw_values["stage3"],
        )


@pytest.mark.parametrize(
    "raw_name",
    ["review", "authorization", "stage3"],
)
def test_stage4_rejects_raw_formatting_transplant(raw_name: str) -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    raw_values = {
        "review": raw_review,
        "authorization": raw_authorization,
        "stage3": raw_stage3,
    }
    raw_values[raw_name] = json.dumps(
        json.loads(raw_values[raw_name].decode("ascii")),
        sort_keys=True,
        indent=2,
    ).encode("ascii")
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_authorization(
            carrier_bytes,
            raw_values["authorization"],
            raw_values["review"],
            raw_values["stage3"],
        )


def test_stage4_requires_exact_canonical_carrier_bytes() -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    reformatted = json.dumps(
        json.loads(carrier_bytes.decode("ascii")),
        sort_keys=True,
        indent=2,
    ).encode("ascii")
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="exact canonical JSON",
    ):
        _verify_authorization(
            reformatted,
            raw_authorization,
            raw_review,
            raw_stage3,
        )

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="duplicate JSON key",
    ):
        verify_signed_production_authorization_carrier(
            b'{"schema_id":"one","schema_id":"two"}',
            raw_authorization_receipt_bytes=raw_authorization,
            raw_review_attestation_bytes=raw_review,
            raw_pre_execution_review_carrier_bytes=raw_stage3,
            expected_carrier_sha256="0" * 64,
            expected_lane="energy_force",
            expected_run_context=_run_context(),
            expected_prior_custody_event_sha256=STAGE3_CUSTODY_EVENT_SHA256,
            upstream_authorization_verification_arguments=(
                _authorization_arguments("energy_force")
            ),
            pre_execution_review_reverification_arguments=(
                _stage3_reverification_arguments("energy_force", raw_stage3)
            ),
            trusted_production_authorization_keys={
                PRODUCTION_AUTHORIZATION_KEY_ID: (
                    ProductionAuthorizationCarrierTrustAnchor(
                        PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY,
                        ed25519_public_key_bytes(PRODUCTION_AUTHORIZATION_PRIVATE_KEY),
                    )
                )
            },
            checked_at=AUTHORIZATION_CHECKED_AT,
        )


def test_stage4_revocation_and_supersession_cover_logical_and_raw_identities() -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    carrier = json.loads(carrier_bytes.decode("ascii"))
    authorization = json.loads(raw_authorization.decode("ascii"))
    stage3 = json.loads(raw_stage3.decode("ascii"))
    review = json.loads(raw_review.decode("ascii"))

    for argument_name in ("revoked_carrier_sha256s", "superseded_carrier_sha256s"):
        for identity in (
            carrier["carrier_sha256"],
            hashlib.sha256(carrier_bytes).hexdigest(),
        ):
            with pytest.raises(
                ValidationProductionReviewAuthorizationCustodyExtensionError
            ):
                _verify_authorization(
                    carrier_bytes,
                    raw_authorization,
                    raw_review,
                    raw_stage3,
                    **{argument_name: (identity,)},
                )

    for argument_name in (
        "revoked_upstream_authorization_sha256s",
        "superseded_upstream_authorization_sha256s",
    ):
        for identity in (
            authorization["receipt_sha256"],
            hashlib.sha256(raw_authorization).hexdigest(),
        ):
            with pytest.raises(
                ValidationProductionReviewAuthorizationCustodyExtensionError
            ):
                _verify_authorization(
                    carrier_bytes,
                    raw_authorization,
                    raw_review,
                    raw_stage3,
                    **{argument_name: (identity,)},
                )

    nested_cases = (
        (
            "revoked_carrier_sha256s",
            stage3["carrier_sha256"],
        ),
        (
            "superseded_carrier_sha256s",
            hashlib.sha256(raw_stage3).hexdigest(),
        ),
        (
            "revoked_upstream_review_sha256s",
            review["attestation_sha256"],
        ),
        (
            "superseded_upstream_review_sha256s",
            hashlib.sha256(raw_review).hexdigest(),
        ),
    )
    for argument_name, identity in nested_cases:
        stage3_arguments = _stage3_reverification_arguments(
            "energy_force",
            raw_stage3,
            **{argument_name: (identity,)},
        )
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError
        ):
            _verify_authorization(
                carrier_bytes,
                raw_authorization,
                raw_review,
                raw_stage3,
                pre_execution_review_reverification_arguments=stage3_arguments,
            )

    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="upstream authorization key is revoked",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            revoked_upstream_authorization_key_ids=(ENERGY_AUTHORIZATION_KEY_ID,),
        )


def test_stage4_rejects_run_context_and_prior_event_crosswire() -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    replacements: dict[str, object] = {
        "permit_sha256": "01" * 32,
        "study_id_sha256": "02" * 32,
        "run_id_sha256": "03" * 32,
        "authorization_nonce_sha256": "04" * 32,
        "code_commit_sha": "5" * 40,
        "source_sha256": "06" * 32,
        "dependency_manifest_sha256": "07" * 32,
        "current_status_snapshot_sha256": "08" * 32,
        "process_launch_identity_sha256": "09" * 32,
    }
    for field, replacement in replacements.items():
        context = _run_context()
        context[field] = replacement
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError
        ):
            _verify_authorization(
                carrier_bytes,
                raw_authorization,
                raw_review,
                raw_stage3,
                expected_run_context=context,
            )

    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            expected_prior_custody_event_sha256="0a" * 32,
        )


def test_stage4_rejects_dependency_environment_and_result_reverification_crosswire() -> (
    None
):
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    changed_dependencies = dict(ENERGY_AUTHORIZATION_DEPENDENCY_ROWS)
    changed_dependencies["numpy-distribution"] = "0b" * 32
    crosswires: tuple[dict[str, object], ...] = (
        {"expected_dependency_artifact_sha256_rows": changed_dependencies},
        {"expected_execution_environment_contract_sha256": "0c" * 32},
        {"expected_result_receipt_contract_sha256": "0d" * 32},
    )
    for override in crosswires:
        arguments = _authorization_arguments("energy_force", **override)
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError,
            match="re-verification failed",
        ):
            _verify_authorization(
                carrier_bytes,
                raw_authorization,
                raw_review,
                raw_stage3,
                upstream_authorization_verification_arguments=arguments,
            )


@pytest.mark.parametrize(
    ("receipt_overrides", "argument_overrides"),
    [
        ({"authorization_nonce_sha256": "0e" * 32}, {}),
        (
            {"code_commit_sha": "6" * 40},
            {"expected_code_commit_sha": "6" * 40},
        ),
        (
            {"runner_source_sha256": "0f" * 32},
            {"expected_runner_source_sha256": "0f" * 32},
        ),
    ],
)
def test_stage4_rejects_valid_upstream_nonce_code_or_source_transplant(
    receipt_overrides: dict[str, object],
    argument_overrides: dict[str, object],
) -> None:
    raw_stage3, raw_review = _carrier("energy_force")
    raw_authorization = _raw_authorization(
        "energy_force",
        raw_review,
        **receipt_overrides,
    )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="exact permit run context",
    ):
        build_signed_production_authorization_carrier(
            raw_authorization_receipt_bytes=raw_authorization,
            raw_review_attestation_bytes=raw_review,
            raw_pre_execution_review_carrier_bytes=raw_stage3,
            lane="energy_force",
            run_context=_run_context(),
            upstream_authorization_verification_arguments=_authorization_arguments(
                "energy_force",
                **argument_overrides,
            ),
            pre_execution_review_reverification_arguments=(
                _stage3_reverification_arguments("energy_force", raw_stage3)
            ),
            prior_custody_event_sha256=STAGE3_CUSTODY_EVENT_SHA256,
            production_authorization_operator_identity_sha256=(
                PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY
            ),
            production_authorization_key_id=PRODUCTION_AUTHORIZATION_KEY_ID,
            signing_key=PRODUCTION_AUTHORIZATION_PRIVATE_KEY,
            signed_at=AUTHORIZATION_CARRIER_SIGNED_AT,
            expires_at=AUTHORIZATION_CARRIER_EXPIRES_AT,
        )


def test_stage4_requires_exact_reverification_argument_dicts() -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    authorization_arguments = _authorization_arguments("energy_force")
    authorization_arguments.pop("consumed_nonce_sha256s")
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="exact frozen fields",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            upstream_authorization_verification_arguments=authorization_arguments,
        )

    authorization_arguments = _authorization_arguments("energy_force")
    authorization_arguments["unexpected"] = ()
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="exact frozen fields",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            upstream_authorization_verification_arguments=authorization_arguments,
        )

    stage3_arguments = _stage3_reverification_arguments("energy_force", raw_stage3)
    stage3_arguments.pop("superseded_upstream_review_sha256s")
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="not exact",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            pre_execution_review_reverification_arguments=stage3_arguments,
        )

    stage3_arguments = _stage3_reverification_arguments("energy_force", raw_stage3)
    stage3_arguments["unexpected"] = ()
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="not exact",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            pre_execution_review_reverification_arguments=stage3_arguments,
        )

    class DictSubclass(dict):
        pass

    for argument_name, value in (
        ("expected_run_context", DictSubclass(_run_context())),
        (
            "upstream_authorization_verification_arguments",
            DictSubclass(_authorization_arguments("energy_force")),
        ),
        (
            "pre_execution_review_reverification_arguments",
            DictSubclass(_stage3_reverification_arguments("energy_force", raw_stage3)),
        ),
    ):
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError
        ):
            _verify_authorization(
                carrier_bytes,
                raw_authorization,
                raw_review,
                raw_stage3,
                **{argument_name: value},
            )


def test_stage4_rejects_unused_cross_role_trust_aliases() -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    production_trust = {
        PRODUCTION_AUTHORIZATION_KEY_ID: ProductionAuthorizationCarrierTrustAnchor(
            PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY,
            ed25519_public_key_bytes(PRODUCTION_AUTHORIZATION_PRIVATE_KEY),
        ),
        "unused-production-authorization-2026-07": (
            ProductionAuthorizationCarrierTrustAnchor(
                "12" * 32,
                ed25519_public_key_bytes(PRODUCTION_REVIEW_PRIVATE_KEY),
            )
        ),
    }
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="global alias",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            trusted_production_authorization_keys=production_trust,
        )

    authorization_arguments = _authorization_arguments("energy_force")
    authorization_arguments["trusted_operator_keys"] = {
        **authorization_arguments["trusted_operator_keys"],  # type: ignore[dict-item]
        "unused-upstream-operator-2026-07": AuthorizationOperatorTrustAnchor(
            "13" * 32,
            ENERGY_REVIEW_PUBLIC_KEY,
        ),
    }
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="global role alias",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            upstream_authorization_verification_arguments=authorization_arguments,
        )


@pytest.mark.parametrize("alias_kind", ["identity", "key_id", "material"])
def test_stage4_rejects_unused_stage3_reviewer_anchor_aliasing_upstream_operator(
    alias_kind: str,
) -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    stage3_arguments = _stage3_reverification_arguments("energy_force", raw_stage3)
    stage3_review_arguments = _upstream_arguments("energy_force")
    key_id = (
        ENERGY_AUTHORIZATION_KEY_ID
        if alias_kind == "key_id"
        else "unused-stage3-reviewer-2026-07"
    )
    identity = (
        UPSTREAM_AUTHORIZATION_OPERATOR_IDENTITY
        if alias_kind == "identity"
        else "14" * 32
    )
    material = (
        ENERGY_AUTHORIZATION_PUBLIC_KEY
        if alias_kind == "material"
        else ed25519_public_key_bytes(bytes.fromhex("13" * 32))
    )
    stage3_review_arguments["trusted_reviewer_keys"] = {
        **stage3_review_arguments["trusted_reviewer_keys"],  # type: ignore[dict-item]
        key_id: ScientificReviewerTrustAnchor(identity, material),
    }
    stage3_arguments["upstream_review_verification_arguments"] = stage3_review_arguments
    with pytest.raises(ValidationProductionReviewAuthorizationCustodyExtensionError):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            pre_execution_review_reverification_arguments=stage3_arguments,
        )


@pytest.mark.parametrize(
    ("identity", "key_id"),
    [
        (UPSTREAM_AUTHORIZATION_OPERATOR_IDENTITY, PRODUCTION_AUTHORIZATION_KEY_ID),
        (PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY, ENERGY_AUTHORIZATION_KEY_ID),
    ],
)
def test_stage4_builder_rejects_production_authorization_role_or_key_alias(
    identity: str,
    key_id: str,
) -> None:
    raw_stage3, raw_review = _carrier("energy_force")
    raw_authorization = _raw_authorization("energy_force", raw_review)
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="global role alias",
    ):
        build_signed_production_authorization_carrier(
            raw_authorization_receipt_bytes=raw_authorization,
            raw_review_attestation_bytes=raw_review,
            raw_pre_execution_review_carrier_bytes=raw_stage3,
            lane="energy_force",
            run_context=_run_context(),
            upstream_authorization_verification_arguments=_authorization_arguments(
                "energy_force"
            ),
            pre_execution_review_reverification_arguments=(
                _stage3_reverification_arguments("energy_force", raw_stage3)
            ),
            prior_custody_event_sha256=STAGE3_CUSTODY_EVENT_SHA256,
            production_authorization_operator_identity_sha256=identity,
            production_authorization_key_id=key_id,
            signing_key=PRODUCTION_AUTHORIZATION_PRIVATE_KEY,
            signed_at=AUTHORIZATION_CARRIER_SIGNED_AT,
            expires_at=AUTHORIZATION_CARRIER_EXPIRES_AT,
        )


def test_stage4_rejects_same_ed25519_keypair_across_operator_roles() -> None:
    raw_stage3, raw_review = _carrier("minimization")
    raw_authorization = _raw_authorization("minimization", raw_review)
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="key material contains a global role alias",
    ):
        build_signed_production_authorization_carrier(
            raw_authorization_receipt_bytes=raw_authorization,
            raw_review_attestation_bytes=raw_review,
            raw_pre_execution_review_carrier_bytes=raw_stage3,
            lane="minimization",
            run_context=_run_context(),
            upstream_authorization_verification_arguments=_authorization_arguments(
                "minimization"
            ),
            pre_execution_review_reverification_arguments=(
                _stage3_reverification_arguments("minimization", raw_stage3)
            ),
            prior_custody_event_sha256=STAGE3_CUSTODY_EVENT_SHA256,
            production_authorization_operator_identity_sha256=(
                PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY
            ),
            production_authorization_key_id=PRODUCTION_AUTHORIZATION_KEY_ID,
            signing_key=MINIMIZATION_AUTHORIZATION_PRIVATE_KEY,
            signed_at=AUTHORIZATION_CARRIER_SIGNED_AT,
            expires_at=AUTHORIZATION_CARRIER_EXPIRES_AT,
        )


def test_stage4_rejects_signature_tamper_expiry_and_ancestor_lifetime_escape() -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    tampered = json.loads(carrier_bytes.decode("ascii"))
    tampered["claim_safe"] = True
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="signature verification failed",
    ):
        _verify_authorization(
            _canonical(tampered),
            raw_authorization,
            raw_review,
            raw_stage3,
        )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="not currently valid",
    ):
        _verify_authorization(
            carrier_bytes,
            raw_authorization,
            raw_review,
            raw_stage3,
            checked_at=AUTHORIZATION_CARRIER_EXPIRES_AT,
        )
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="ancestor lifetime",
    ):
        build_signed_production_authorization_carrier(
            raw_authorization_receipt_bytes=raw_authorization,
            raw_review_attestation_bytes=raw_review,
            raw_pre_execution_review_carrier_bytes=raw_stage3,
            lane="energy_force",
            run_context=_run_context(),
            upstream_authorization_verification_arguments=_authorization_arguments(
                "energy_force"
            ),
            pre_execution_review_reverification_arguments=(
                _stage3_reverification_arguments("energy_force", raw_stage3)
            ),
            prior_custody_event_sha256=STAGE3_CUSTODY_EVENT_SHA256,
            production_authorization_operator_identity_sha256=(
                PRODUCTION_AUTHORIZATION_OPERATOR_IDENTITY
            ),
            production_authorization_key_id=PRODUCTION_AUTHORIZATION_KEY_ID,
            signing_key=PRODUCTION_AUTHORIZATION_PRIVATE_KEY,
            signed_at=AUTHORIZATION_CARRIER_SIGNED_AT,
            expires_at=AUTHORIZATION_EXPIRES_AT + timedelta(seconds=1),
        )


def test_stage4_signed_inputs_are_bytes_only_and_json_depth_is_bounded() -> None:
    carrier_bytes, raw_authorization, raw_review, raw_stage3 = _authorization_carrier()
    non_bytes_cases = (
        ("source", json.loads(carrier_bytes)),
        ("raw_authorization_receipt_bytes", json.loads(raw_authorization)),
        ("raw_review_attestation_bytes", json.loads(raw_review)),
        ("raw_pre_execution_review_carrier_bytes", json.loads(raw_stage3)),
    )
    for argument_name, value in non_bytes_cases:
        with pytest.raises(
            ValidationProductionReviewAuthorizationCustodyExtensionError,
            match="must be non-empty bytes",
        ):
            _verify_authorization(
                carrier_bytes,
                raw_authorization,
                raw_review,
                raw_stage3,
                **{argument_name: value},
            )

    deeply_nested = b'{"x":' + (b"[" * 129) + b"0" + (b"]" * 129) + b"}"
    with pytest.raises(
        ValidationProductionReviewAuthorizationCustodyExtensionError,
        match="JSON nesting bound",
    ):
        _verify_authorization(
            deeply_nested,
            raw_authorization,
            raw_review,
            raw_stage3,
        )
