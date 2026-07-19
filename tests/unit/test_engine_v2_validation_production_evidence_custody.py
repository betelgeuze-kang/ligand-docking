from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from betelgeuze_engine_v2.physics import (
    validation_production_evidence_custody as custody,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)


UTC = timezone.utc
ISSUED = datetime(2026, 7, 19, 3, tzinfo=UTC)
CHECKED = ISSUED + timedelta(hours=1)
AUTHORITY_PRIVATE_KEY = b"a" * 32
CURRENT_AUTHORITY_PRIVATE_KEY = b"c" * 32
FROM_PRIVATE_KEY = b"f" * 32
TO_PRIVATE_KEY = b"t" * 32
THIRD_PRIVATE_KEY = b"z" * 32
AUTHORITY_KEY_ID = "evidence-authority-2026-01"
CURRENT_AUTHORITY_KEY_ID = "evidence-authority-2026-02"
FROM_KEY_ID = "run-custodian-2026-01"
TO_KEY_ID = "artifact-store-2026-01"
THIRD_KEY_ID = "review-store-2026-01"
AUTHORITY_ID = "1" * 64
CURRENT_AUTHORITY_ID = "0" * 64
CUSTODIAN_ID = "2" * 64
FROM_ID = CUSTODIAN_ID
TO_ID = "3" * 64
THIRD_ID = "a" * 64
HOST_ID = "4" * 64
PERMIT_ID = "5" * 64
STUDY_ID = "6" * 64
RUN_ID = "7" * 64
NONCE = "8" * 64
OUTPUT_ROOT_ID = "9" * 64
CHECKPOINT = "a" * 64
CURRENT_CHECKPOINT = "9" * 64
THIRD_STATUS_CHECKPOINT = "8" * 64
SOURCE = "b" * 64
SOURCE_MANIFEST = "c" * 64
DEPENDENCY_MANIFEST = "d" * 64
RUNTIME_MANIFEST = "e" * 64
BUNDLE = {"physics/1.0.0": "f" * 64, "runner/1.0.0": "0" * 64}
INNER_SCHEMA = "test.synthetic_validation_observation/1.0.0"


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _authority_anchor(
    *,
    authority_identity_sha256: str = AUTHORITY_ID,
    private_key: bytes = AUTHORITY_PRIVATE_KEY,
) -> custody.EvidenceAuthorityTrustAnchor:
    return custody.EvidenceAuthorityTrustAnchor(
        authority_identity_sha256=authority_identity_sha256,
        verification_key=ed25519_public_key_bytes(private_key),
    )


def _permit(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "permit_id_sha256": PERMIT_ID,
        "lane": "energy_force",
        "study_id_sha256": STUDY_ID,
        "run_id_sha256": RUN_ID,
        "authorization_nonce_sha256": NONCE,
        "contract_bundle_sha256_rows": BUNDLE,
        "code_commit_sha": "1" * 40,
        "source_sha256": SOURCE,
        "source_manifest_sha256": SOURCE_MANIFEST,
        "dependency_manifest_sha256": DEPENDENCY_MANIFEST,
        "runtime_manifest_sha256": RUNTIME_MANIFEST,
        "expected_custodian_identity_sha256": CUSTODIAN_ID,
        "expected_enrolled_host_identity_sha256": HOST_ID,
        "seed": 1729,
        "command_argv": ["python3", "-m", "production_validation"],
        "artifact_output_root_identity_sha256": OUTPUT_ROOT_ID,
        "authority_identity_sha256": AUTHORITY_ID,
        "authority_key_id": AUTHORITY_KEY_ID,
        "signing_key": AUTHORITY_PRIVATE_KEY,
        "issued_at": ISSUED,
        "expires_at": ISSUED + timedelta(hours=24),
        "external_log_sequence": 17,
        "external_log_checkpoint_sha256": CHECKPOINT,
    }
    values.update(overrides)
    return custody.build_signed_production_evidence_permit(**values)  # type: ignore[arg-type]


def _verify_permit(
    permit: dict[str, object] | bytes,
    **overrides: object,
) -> custody.ProductionEvidencePermitVerification:
    document = (
        json.loads(permit.decode("ascii")) if isinstance(permit, bytes) else permit
    )
    values: dict[str, object] = {
        "expected_permit_sha256": document["permit_sha256"],
        "trusted_authority_keys": {AUTHORITY_KEY_ID: _authority_anchor()},
        "checked_at": CHECKED,
        "expected_lane": "energy_force",
        "expected_permit_id_sha256": PERMIT_ID,
        "expected_study_id_sha256": STUDY_ID,
        "expected_run_id_sha256": RUN_ID,
        "expected_authorization_nonce_sha256": NONCE,
        "expected_contract_bundle_sha256_rows": BUNDLE,
        "expected_code_commit_sha": "1" * 40,
        "expected_source_sha256": SOURCE,
        "expected_source_manifest_sha256": SOURCE_MANIFEST,
        "expected_dependency_manifest_sha256": DEPENDENCY_MANIFEST,
        "expected_runtime_manifest_sha256": RUNTIME_MANIFEST,
        "expected_custodian_identity_sha256": CUSTODIAN_ID,
        "expected_enrolled_host_identity_sha256": HOST_ID,
        "expected_seed": 1729,
        "expected_command_argv": ["python3", "-m", "production_validation"],
        "expected_artifact_output_root_identity_sha256": OUTPUT_ROOT_ID,
        "minimum_external_log_sequence": 17,
        "expected_external_log_checkpoint_sha256": CHECKPOINT,
        "revoked_authority_key_ids": (),
        "revoked_permit_sha256s": (),
        "superseded_permit_sha256s": (),
        "consumed_permit_sha256s": (),
    }
    values.update(overrides)
    return custody.verify_signed_production_evidence_permit(  # type: ignore[arg-type]
        permit,
        **values,
    )


def _snapshot(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "permit_sha256": "1" * 64,
        "run_id_sha256": RUN_ID,
        "lane": "energy_force",
        "custodian_identity_sha256": CUSTODIAN_ID,
        "enrolled_host_identity_sha256": HOST_ID,
        "status_sequence": 1,
        "external_log_checkpoint_sha256": CHECKPOINT,
        "previous_snapshot_sha256": None,
        "issued_at": ISSUED,
        "authority_identity_sha256": AUTHORITY_ID,
        "authority_key_id": AUTHORITY_KEY_ID,
        "signing_key": AUTHORITY_PRIVATE_KEY,
    }
    values.update(overrides)
    return custody.build_signed_production_evidence_status_snapshot(  # type: ignore[arg-type]
        **values
    )


def _verify_snapshot(
    snapshot: dict[str, object] | bytes,
    **overrides: object,
) -> custody.ProductionEvidenceStatusSnapshotVerification:
    document = (
        json.loads(snapshot.decode("ascii"))
        if isinstance(snapshot, bytes)
        else snapshot
    )
    values: dict[str, object] = {
        "expected_snapshot_sha256": document["snapshot_sha256"],
        "expected_permit_sha256": "1" * 64,
        "expected_run_id_sha256": RUN_ID,
        "expected_lane": "energy_force",
        "expected_custodian_identity_sha256": CUSTODIAN_ID,
        "expected_enrolled_host_identity_sha256": HOST_ID,
        "trusted_authority_keys": {AUTHORITY_KEY_ID: _authority_anchor()},
        "checked_at": CHECKED,
        "minimum_trusted_sequence": 1,
        "minimum_trusted_external_log_checkpoint_sha256": CHECKPOINT,
        "minimum_trusted_issued_at": ISSUED,
        "expected_previous_snapshot_sha256": None,
        "revoked_authority_key_ids": (),
    }
    values.update(overrides)
    return custody.verify_signed_production_evidence_status_snapshot(  # type: ignore[arg-type]
        snapshot,
        **values,
    )


def _permit_verification_arguments() -> dict[str, object]:
    return {
        "expected_permit_id_sha256": PERMIT_ID,
        "expected_study_id_sha256": STUDY_ID,
        "expected_authorization_nonce_sha256": NONCE,
        "expected_contract_bundle_sha256_rows": BUNDLE,
        "expected_code_commit_sha": "1" * 40,
        "expected_source_sha256": SOURCE,
        "expected_source_manifest_sha256": SOURCE_MANIFEST,
        "expected_dependency_manifest_sha256": DEPENDENCY_MANIFEST,
        "expected_runtime_manifest_sha256": RUNTIME_MANIFEST,
        "expected_seed": 1729,
        "expected_command_argv": ["python3", "-m", "production_validation"],
        "expected_artifact_output_root_identity_sha256": OUTPUT_ROOT_ID,
        "minimum_external_log_sequence": 17,
        "expected_external_log_checkpoint_sha256": CHECKPOINT,
        "revoked_authority_key_ids": (),
        "revoked_permit_sha256s": (),
        "superseded_permit_sha256s": (),
        "consumed_permit_sha256s": (),
    }


def _custody_trust() -> dict[str, custody.CustodyRoleTrustAnchor]:
    return {
        FROM_KEY_ID: custody.CustodyRoleTrustAnchor(
            "run_custodian",
            FROM_ID,
            ed25519_public_key_bytes(FROM_PRIVATE_KEY),
        ),
        TO_KEY_ID: custody.CustodyRoleTrustAnchor(
            "artifact_store",
            TO_ID,
            ed25519_public_key_bytes(TO_PRIVATE_KEY),
        ),
        THIRD_KEY_ID: custody.CustodyRoleTrustAnchor(
            "review_store",
            THIRD_ID,
            ed25519_public_key_bytes(THIRD_PRIVATE_KEY),
        ),
    }


def _scenario(
    *,
    current_revoked_key_rows: list[dict[str, str]] | None = None,
    current_revoked_artifact_rows: list[dict[str, str]] | None = None,
    current_supersession_rows: list[dict[str, str]] | None = None,
    rotate_current_authority: bool = False,
) -> dict[str, object]:
    permit = _permit()
    permit_sha256 = str(permit["permit_sha256"])
    permit_verification = _verify_permit(permit)
    status_one = _snapshot(
        permit_sha256=permit_sha256,
        issued_at=ISSUED,
    )
    status_one_verification = _verify_snapshot(
        status_one,
        expected_permit_sha256=permit_sha256,
    )
    trusted_authority_keys = {AUTHORITY_KEY_ID: _authority_anchor()}
    current_authority_arguments: dict[str, object] = {}
    if rotate_current_authority:
        trusted_authority_keys[CURRENT_AUTHORITY_KEY_ID] = _authority_anchor(
            authority_identity_sha256=CURRENT_AUTHORITY_ID,
            private_key=CURRENT_AUTHORITY_PRIVATE_KEY,
        )
        current_authority_arguments = {
            "authority_identity_sha256": CURRENT_AUTHORITY_ID,
            "authority_key_id": CURRENT_AUTHORITY_KEY_ID,
            "signing_key": CURRENT_AUTHORITY_PRIVATE_KEY,
        }
    status_two = _snapshot(
        permit_sha256=permit_sha256,
        status_sequence=2,
        external_log_checkpoint_sha256=CURRENT_CHECKPOINT,
        previous_snapshot_sha256=status_one_verification.snapshot_sha256,
        issued_at=ISSUED + timedelta(minutes=10),
        revoked_key_rows=current_revoked_key_rows or (),
        revoked_artifact_rows=current_revoked_artifact_rows or (),
        supersession_rows=current_supersession_rows or (),
        **current_authority_arguments,
    )
    status_two_verification = _verify_snapshot(
        status_two,
        expected_permit_sha256=permit_sha256,
        minimum_trusted_sequence=2,
        minimum_trusted_external_log_checkpoint_sha256=CURRENT_CHECKPOINT,
        expected_previous_snapshot_sha256=status_one_verification.snapshot_sha256,
        previous_verified_snapshot=status_one_verification,
        trusted_authority_keys=trusted_authority_keys,
    )
    permit_raw = _canonical(permit)
    status_one_raw = _canonical(status_one)
    event_one = custody.build_signed_production_custody_event(
        raw_artifact_bytes=permit_raw,
        inner_schema_id=custody.PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
        artifact_stage="production_permit",
        prior_custody_event_sha256=None,
        custody_sequence=1,
        permit_sha256=permit_sha256,
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="run_custodian",
        from_role_identity_sha256=FROM_ID,
        from_key_id=FROM_KEY_ID,
        from_signing_key=FROM_PRIVATE_KEY,
        to_role="artifact_store",
        to_role_identity_sha256=TO_ID,
        to_key_id=TO_KEY_ID,
        to_signing_key=TO_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=5),
        received_at=ISSUED + timedelta(minutes=6),
        status_snapshot_sha256=status_one_verification.snapshot_sha256,
    )
    event_two = custody.build_signed_production_custody_event(
        raw_artifact_bytes=status_one_raw,
        inner_schema_id=custody.PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        artifact_stage="status_snapshot",
        prior_custody_event_sha256=str(event_one["custody_event_sha256"]),
        custody_sequence=2,
        permit_sha256=permit_sha256,
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="artifact_store",
        from_role_identity_sha256=TO_ID,
        from_key_id=TO_KEY_ID,
        from_signing_key=TO_PRIVATE_KEY,
        to_role="review_store",
        to_role_identity_sha256=THIRD_ID,
        to_key_id=THIRD_KEY_ID,
        to_signing_key=THIRD_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=15),
        received_at=ISSUED + timedelta(minutes=16),
        status_snapshot_sha256=status_one_verification.snapshot_sha256,
    )
    return {
        "permit": permit,
        "permit_raw": permit_raw,
        "permit_sha256": permit_sha256,
        "permit_verification": permit_verification,
        "status_one": status_one,
        "status_one_raw": status_one_raw,
        "status_one_verification": status_one_verification,
        "status_two": status_two,
        "status_two_verification": status_two_verification,
        "event_one": event_one,
        "event_two": event_two,
        "trusted_authority_keys": trusted_authority_keys,
    }


def _append_third_status(
    scenario: dict[str, object],
    *,
    revoked_artifact_rows: tuple[dict[str, str], ...] = (),
    supersession_rows: tuple[dict[str, str], ...] = (),
) -> dict[str, object]:
    status_two_verification = scenario["status_two_verification"]
    status_three = _snapshot(
        permit_sha256=scenario["permit_sha256"],
        status_sequence=3,
        external_log_checkpoint_sha256=THIRD_STATUS_CHECKPOINT,
        previous_snapshot_sha256=status_two_verification.snapshot_sha256,
        issued_at=ISSUED + timedelta(minutes=20),
        revoked_artifact_rows=revoked_artifact_rows,
        supersession_rows=supersession_rows,
    )
    status_three_verification = _verify_snapshot(
        status_three,
        expected_permit_sha256=scenario["permit_sha256"],
        minimum_trusted_sequence=3,
        minimum_trusted_external_log_checkpoint_sha256=THIRD_STATUS_CHECKPOINT,
        expected_previous_snapshot_sha256=status_two_verification.snapshot_sha256,
        previous_verified_snapshot=status_two_verification,
        trusted_authority_keys=scenario["trusted_authority_keys"],
    )
    extended = dict(scenario)
    extended["status_three"] = status_three
    extended["status_three_verification"] = status_three_verification
    return extended


def _verify_scenario_event_one_with_third_status(
    scenario: dict[str, object],
) -> custody.ProductionCustodyEventVerification:
    return _verify_scenario_event_one(
        scenario,
        status_lineage_sources=[
            scenario["status_one"],
            scenario["status_two"],
            scenario["status_three"],
        ],
        expected_current_status_snapshot_sha256=scenario[
            "status_three_verification"
        ].snapshot_sha256,
        expected_current_status_checkpoint_sha256=THIRD_STATUS_CHECKPOINT,
        verified_current_status_snapshot=scenario["status_three_verification"],
    )


def _verify_scenario_event_one(
    scenario: dict[str, object],
    **overrides: object,
) -> custody.ProductionCustodyEventVerification:
    event = scenario["event_one"]
    values: dict[str, object] = {
        "raw_artifact_bytes": scenario["permit_raw"],
        "expected_custody_event_sha256": event["custody_event_sha256"],  # type: ignore[index]
        "trusted_custody_keys": _custody_trust(),
        "trusted_authority_keys": scenario["trusted_authority_keys"],
        "checked_at": CHECKED,
        "expected_inner_schema_id": custody.PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
        "expected_artifact_stage": "production_permit",
        "expected_prior_custody_event_sha256": None,
        "expected_custody_sequence": 1,
        "expected_permit_sha256": scenario["permit_sha256"],
        "expected_run_id_sha256": RUN_ID,
        "expected_lane": "energy_force",
        "expected_custodian_identity_sha256": CUSTODIAN_ID,
        "expected_enrolled_host_identity_sha256": HOST_ID,
        "expected_from_role": "run_custodian",
        "expected_from_role_identity_sha256": FROM_ID,
        "expected_from_key_id": FROM_KEY_ID,
        "expected_to_role": "artifact_store",
        "expected_to_role_identity_sha256": TO_ID,
        "expected_to_key_id": TO_KEY_ID,
        "permit_source": scenario["permit"],
        "permit_verification_arguments": _permit_verification_arguments(),
        "verified_permit": scenario["permit_verification"],
        "status_lineage_sources": [
            scenario["status_one"],
            scenario["status_two"],
        ],
        "expected_current_status_snapshot_sha256": scenario[
            "status_two_verification"
        ].snapshot_sha256,
        "expected_current_status_checkpoint_sha256": CURRENT_CHECKPOINT,
        "verified_handoff_status_snapshot": scenario["status_one_verification"],
        "verified_current_status_snapshot": scenario["status_two_verification"],
        "revoked_authority_key_ids": (),
    }
    values.update(overrides)
    return custody.verify_signed_production_custody_event(  # type: ignore[arg-type]
        event,
        **values,
    )


def _verify_scenario_event_two(
    scenario: dict[str, object],
    previous: custody.ProductionCustodyEventVerification,
    **overrides: object,
) -> custody.ProductionCustodyEventVerification:
    event = scenario["event_two"]
    event_one = scenario["event_one"]
    values: dict[str, object] = {
        "raw_artifact_bytes": scenario["status_one_raw"],
        "expected_custody_event_sha256": event["custody_event_sha256"],  # type: ignore[index]
        "trusted_custody_keys": _custody_trust(),
        "trusted_authority_keys": scenario["trusted_authority_keys"],
        "checked_at": CHECKED,
        "expected_inner_schema_id": custody.PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        "expected_artifact_stage": "status_snapshot",
        "expected_prior_custody_event_sha256": event_one[  # type: ignore[index]
            "custody_event_sha256"
        ],
        "expected_custody_sequence": 2,
        "expected_permit_sha256": scenario["permit_sha256"],
        "expected_run_id_sha256": RUN_ID,
        "expected_lane": "energy_force",
        "expected_custodian_identity_sha256": CUSTODIAN_ID,
        "expected_enrolled_host_identity_sha256": HOST_ID,
        "expected_from_role": "artifact_store",
        "expected_from_role_identity_sha256": TO_ID,
        "expected_from_key_id": TO_KEY_ID,
        "expected_to_role": "review_store",
        "expected_to_role_identity_sha256": THIRD_ID,
        "expected_to_key_id": THIRD_KEY_ID,
        "permit_source": scenario["permit"],
        "permit_verification_arguments": _permit_verification_arguments(),
        "verified_permit": scenario["permit_verification"],
        "status_lineage_sources": [
            scenario["status_one"],
            scenario["status_two"],
        ],
        "expected_current_status_snapshot_sha256": scenario[
            "status_two_verification"
        ].snapshot_sha256,
        "expected_current_status_checkpoint_sha256": CURRENT_CHECKPOINT,
        "verified_handoff_status_snapshot": scenario["status_one_verification"],
        "verified_current_status_snapshot": scenario["status_two_verification"],
        "revoked_authority_key_ids": (),
        "previous_event_source": scenario["event_one"],
        "previous_raw_artifact_bytes": scenario["permit_raw"],
        "previous_verified_event": previous,
    }
    values.update(overrides)
    return custody.verify_signed_production_custody_event(  # type: ignore[arg-type]
        event,
        **values,
    )


def _build_context_test_event(
    scenario: dict[str, object],
    raw: bytes,
    *,
    stage: str,
) -> dict[str, object]:
    is_permit = stage == "production_permit"
    return custody.build_signed_production_custody_event(
        raw_artifact_bytes=raw,
        inner_schema_id=(
            custody.PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID
            if is_permit
            else custody.PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID
        ),
        artifact_stage=stage,
        prior_custody_event_sha256=(
            None if is_permit else scenario["event_one"]["custody_event_sha256"]
        ),
        custody_sequence=1 if is_permit else 2,
        permit_sha256=scenario["permit_sha256"],
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="run_custodian" if is_permit else "artifact_store",
        from_role_identity_sha256=FROM_ID if is_permit else TO_ID,
        from_key_id=FROM_KEY_ID if is_permit else TO_KEY_ID,
        from_signing_key=FROM_PRIVATE_KEY if is_permit else TO_PRIVATE_KEY,
        to_role="artifact_store" if is_permit else "review_store",
        to_role_identity_sha256=TO_ID if is_permit else THIRD_ID,
        to_key_id=TO_KEY_ID if is_permit else THIRD_KEY_ID,
        to_signing_key=TO_PRIVATE_KEY if is_permit else THIRD_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=5 if is_permit else 15),
        received_at=ISSUED + timedelta(minutes=6 if is_permit else 16),
        status_snapshot_sha256=scenario["status_one_verification"].snapshot_sha256,
    )


def _resign_single_authority_artifact(
    artifact: dict[str, object],
    *,
    hash_field: str,
) -> dict[str, object]:
    payload = deepcopy(artifact)
    payload.pop("signature")
    payload.pop(hash_field)
    payload[hash_field] = _digest(payload)
    payload["signature"] = {
        "algorithm": "ed25519",
        "key_id": AUTHORITY_KEY_ID,
        "value": sign_ed25519(_canonical(payload), AUTHORITY_PRIVATE_KEY),
    }
    return payload


def _resign_custody_artifact(
    artifact: dict[str, object],
    *,
    from_key_id: str,
    from_private_key: bytes,
    to_key_id: str,
    to_private_key: bytes,
) -> dict[str, object]:
    payload = deepcopy(artifact)
    payload.pop("signatures")
    payload.pop("custody_event_sha256")
    payload["custody_event_sha256"] = _digest(payload)
    message = _canonical(payload)
    payload["signatures"] = {
        "from": {
            "algorithm": "ed25519",
            "key_id": from_key_id,
            "value": sign_ed25519(message, from_private_key),
        },
        "to": {
            "algorithm": "ed25519",
            "key_id": to_key_id,
            "value": sign_ed25519(message, to_private_key),
        },
    }
    return payload


def test_frozen_contract_and_decision_are_claim_closed() -> None:
    contract = custody.production_evidence_custody_contract_document()
    assert contract["contract_sha256"] == (
        custody.FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
    )
    assert contract["evidence_class"]["lanes"] == ["energy_force", "minimization"]
    assert custody.SUPPORTED_PRODUCTION_LANES == ("energy_force", "minimization")
    decision = custody.production_evidence_custody_decision()
    assert decision["common_production_evidence_foundation_implemented"] is True
    for key, value in decision.items():
        if key.endswith(
            (
                "validated",
                "authorized",
                "qualified",
                "enabled",
                "safe",
                "present",
                "provisioned",
                "collected",
            )
        ):
            assert value is False


@pytest.mark.parametrize("lane", custody.SUPPORTED_PRODUCTION_LANES)
def test_permit_verifies_exact_lane_and_canonical_transport(lane: str) -> None:
    permit = _permit(lane=lane)
    verified = _verify_permit(permit, expected_lane=lane)
    assert verified.production_evidence_permit_verified is True
    assert verified.lane == lane
    assert verified.claim_safe is False
    assert _verify_permit(_canonical(permit), expected_lane=lane) == verified


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("expected_lane", "minimization"),
        ("expected_run_id_sha256", "0" * 64),
        ("expected_authorization_nonce_sha256", "0" * 64),
        ("expected_enrolled_host_identity_sha256", "0" * 64),
        ("expected_contract_bundle_sha256_rows", {"other/1.0.0": "0" * 64}),
    ],
)
def test_permit_rejects_cross_lane_run_nonce_host_or_bundle(
    name: str, value: object
) -> None:
    permit = _permit()
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(permit, **{name: value})


def test_permit_rejects_class_downgrade_replay_revocation_time_and_role_collision() -> (
    None
):
    permit = _permit()
    downgraded = deepcopy(permit)
    downgraded["evidence_class"] = "test_only"
    downgraded = _resign_single_authority_artifact(
        downgraded,
        hash_field="permit_sha256",
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(downgraded)
    permit_sha = str(permit["permit_sha256"])
    for extra in (
        {"consumed_permit_sha256s": (permit_sha,)},
        {"revoked_permit_sha256s": (permit_sha,)},
        {"superseded_permit_sha256s": (permit_sha,)},
        {"revoked_authority_key_ids": (AUTHORITY_KEY_ID,)},
        {"checked_at": ISSUED - timedelta(seconds=1)},
        {"checked_at": ISSUED + timedelta(hours=24)},
    ):
        with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
            _verify_permit(permit, **extra)
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _permit(expected_custodian_identity_sha256=AUTHORITY_ID)


def test_permit_rejects_noncanonical_duplicate_and_signature_tamper() -> None:
    permit = _permit()
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(json.dumps(permit, indent=2).encode())
    duplicate = _canonical(permit)[:-1] + b',"lane":"energy_force"}'
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(duplicate)
    tampered = deepcopy(permit)
    tampered["signature"]["value"] = "0" * 128  # type: ignore[index]
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(tampered)


def test_fixed_resource_limits_reject_transport_argv_bundle_and_status_row_bombs() -> (
    None
):
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _permit(
            command_argv=["x" * (custody.PRODUCTION_EVIDENCE_MAX_ARGV_ITEM_BYTES + 1)]
        )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _permit(
            command_argv=[
                "x" for _ in range(custody.PRODUCTION_EVIDENCE_MAX_ARGV_ITEMS + 1)
            ]
        )
    oversized_bundle = {
        f"contract-{index}": "0" * 64
        for index in range(custody.PRODUCTION_EVIDENCE_MAX_CONTRACT_BUNDLE_ROWS + 1)
    }
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _permit(contract_bundle_sha256_rows=oversized_bundle)
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _snapshot(
            revoked_key_rows=[{}]
            * (custody.PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND + 1)
        )
    permit = _permit()
    giant = deepcopy(permit)
    giant["untrusted_padding"] = "x" * (
        custody.PRODUCTION_EVIDENCE_MAX_SIGNED_TRANSPORT_BYTES + 1
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(giant)
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(_canonical(giant))


def test_status_builder_rejects_final_signed_carrier_over_transport_bound() -> None:
    revoked_keys = [
        {
            "role": f"role-{index:04d}-" + "r" * 230,
            "key_id": f"key-{index:04d}-" + "k" * 105,
            "revoked_at_utc": _utc(ISSUED),
            "reason_code": "x" * 256,
        }
        for index in range(custody.PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND)
    ]
    revoked_artifacts = [
        {
            "artifact_kind": f"kind-{index:04d}-" + "a" * 230,
            "artifact_sha256": hashlib.sha256(str(index).encode()).hexdigest(),
            "revoked_at_utc": _utc(ISSUED),
            "reason_code": "x" * 256,
        }
        for index in range(custody.PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND)
    ]
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _snapshot(
            revoked_key_rows=revoked_keys,
            revoked_artifact_rows=revoked_artifacts,
        )


def test_authority_trust_store_rejects_public_key_aliases() -> None:
    aliases = {
        AUTHORITY_KEY_ID: _authority_anchor(),
        "authority-alias": custody.EvidenceAuthorityTrustAnchor(
            authority_identity_sha256="0" * 64,
            verification_key=ed25519_public_key_bytes(AUTHORITY_PRIVATE_KEY),
        ),
    }
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(_permit(), trusted_authority_keys=aliases)
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_snapshot(_snapshot(), trusted_authority_keys=aliases)


def test_status_snapshot_is_monotonic_canonical_and_claim_closed() -> None:
    snapshot = _snapshot(
        revoked_key_rows=[
            {
                "role": "old_role",
                "key_id": "old-key",
                "revoked_at_utc": _utc(ISSUED - timedelta(minutes=2)),
                "reason_code": "rotation",
            }
        ],
        revoked_artifact_rows=[
            {
                "artifact_kind": "result",
                "artifact_sha256": "2" * 64,
                "revoked_at_utc": _utc(ISSUED - timedelta(minutes=1)),
                "reason_code": "invalid",
            }
        ],
        supersession_rows=[
            {
                "artifact_kind": "result",
                "superseded_sha256": "3" * 64,
                "replacement_sha256": "4" * 64,
                "superseded_at_utc": _utc(ISSUED),
            }
        ],
    )
    verified = _verify_snapshot(snapshot)
    assert verified.key_is_revoked("old_role", "old-key")
    assert verified.artifact_is_revoked("result", "2" * 64)
    assert verified.artifact_is_superseded("result", "3" * 64)
    assert verified.claim_safe is False
    assert _verify_snapshot(_canonical(snapshot)) == verified


@pytest.mark.parametrize(
    "overrides",
    [
        {"minimum_trusted_sequence": 2},
        {"minimum_trusted_external_log_checkpoint_sha256": "0" * 64},
        {"minimum_trusted_issued_at": ISSUED + timedelta(seconds=1)},
        {"checked_at": ISSUED - timedelta(seconds=1)},
        {"checked_at": ISSUED + timedelta(hours=24, seconds=1)},
        {"expected_previous_snapshot_sha256": "0" * 64},
        {"revoked_authority_key_ids": (AUTHORITY_KEY_ID,)},
    ],
)
def test_status_rejects_stale_fork_backdating_or_revoked_authority(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_snapshot(_snapshot(), **overrides)


def test_status_rejects_bad_chain_rows_class_and_signature() -> None:
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _snapshot(status_sequence=2, previous_snapshot_sha256=None)
    row = {
        "artifact_kind": "result",
        "superseded_sha256": "3" * 64,
        "replacement_sha256": "4" * 64,
        "superseded_at_utc": _utc(ISSUED),
    }
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _snapshot(supersession_rows=[row, row])
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _snapshot(
            revoked_key_rows=[
                {
                    "role": "worker",
                    "key_id": "future-key",
                    "revoked_at_utc": _utc(ISSUED + timedelta(seconds=1)),
                    "reason_code": "future",
                }
            ]
        )
    snapshot = _snapshot()
    downgraded = deepcopy(snapshot)
    downgraded.pop("evidence_class")
    downgraded = _resign_single_authority_artifact(
        downgraded,
        hash_field="snapshot_sha256",
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_snapshot(downgraded)
    tampered = deepcopy(snapshot)
    tampered["signature"]["value"] = "0" * 128  # type: ignore[index]
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_snapshot(tampered)


def test_status_requires_adjacent_verified_predecessor_and_accumulated_rows() -> None:
    revoked_key = {
        "role": "worker",
        "key_id": "retired-worker-key",
        "revoked_at_utc": _utc(ISSUED),
        "reason_code": "rotation",
    }
    supersession = {
        "artifact_kind": "result",
        "superseded_sha256": "3" * 64,
        "replacement_sha256": "4" * 64,
        "superseded_at_utc": _utc(ISSUED),
    }
    first = _snapshot(
        revoked_key_rows=[revoked_key],
        supersession_rows=[supersession],
    )
    first_verified = _verify_snapshot(first)
    second = _snapshot(
        status_sequence=2,
        previous_snapshot_sha256=first_verified.snapshot_sha256,
        issued_at=ISSUED + timedelta(minutes=1),
        revoked_key_rows=[revoked_key],
        supersession_rows=[supersession],
    )
    verified = _verify_snapshot(
        second,
        expected_previous_snapshot_sha256=first_verified.snapshot_sha256,
        previous_verified_snapshot=first_verified,
    )
    assert verified.status_sequence == 2
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_snapshot(
            second,
            expected_previous_snapshot_sha256=first_verified.snapshot_sha256,
        )
    dropped = _snapshot(
        status_sequence=2,
        previous_snapshot_sha256=first_verified.snapshot_sha256,
        issued_at=ISSUED + timedelta(minutes=1),
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_snapshot(
            dropped,
            expected_previous_snapshot_sha256=first_verified.snapshot_sha256,
            previous_verified_snapshot=first_verified,
        )
    rewritten = _snapshot(
        status_sequence=2,
        previous_snapshot_sha256=first_verified.snapshot_sha256,
        issued_at=ISSUED + timedelta(minutes=1),
        revoked_key_rows=[{**revoked_key, "reason_code": "rewritten_reason"}],
        supersession_rows=[supersession],
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_snapshot(
            rewritten,
            expected_previous_snapshot_sha256=first_verified.snapshot_sha256,
            previous_verified_snapshot=first_verified,
        )


def test_status_rejects_self_revocation_under_any_role_label() -> None:
    snapshot = _snapshot(
        revoked_key_rows=[
            {
                "role": "misleading_other_role",
                "key_id": AUTHORITY_KEY_ID,
                "revoked_at_utc": _utc(ISSUED),
                "reason_code": "compromised",
            }
        ]
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_snapshot(snapshot)


def test_v1_raw_reverified_custody_chain_succeeds_and_preserves_lineage() -> None:
    scenario = _scenario()
    first = _verify_scenario_event_one(scenario)
    second = _verify_scenario_event_two(scenario, first)
    assert first.lineage_artifact_stages == ("production_permit",)
    assert second.lineage_artifact_stages == (
        "production_permit",
        "status_snapshot",
    )
    assert second.lineage_custody_event_sha256s == (
        first.custody_event_sha256,
        second.custody_event_sha256,
    )
    assert (
        second.current_status_snapshot_sha256
        == scenario["status_two_verification"].snapshot_sha256
    )
    assert (
        first.from_public_key_sha256
        == hashlib.sha256(ed25519_public_key_bytes(FROM_PRIVATE_KEY)).hexdigest()
    )
    assert scenario["permit_verification"].authority_public_key_sha256 == (
        hashlib.sha256(ed25519_public_key_bytes(AUTHORITY_PRIVATE_KEY)).hexdigest()
    )
    assert scenario["status_two_verification"].lineage_snapshot_sha256s == (
        scenario["status_one_verification"].snapshot_sha256,
        scenario["status_two_verification"].snapshot_sha256,
    )
    assert second.claim_safe is False


def test_sibling_successors_require_an_external_uniqueness_registry() -> None:
    scenario = _scenario()
    first = _verify_scenario_event_one(scenario)
    first_successor = _verify_scenario_event_two(scenario, first)
    sibling_scenario = dict(scenario)
    sibling_scenario["event_two"] = custody.build_signed_production_custody_event(
        raw_artifact_bytes=scenario["status_one_raw"],
        inner_schema_id=custody.PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        artifact_stage="status_snapshot",
        prior_custody_event_sha256=scenario["event_one"]["custody_event_sha256"],
        custody_sequence=2,
        permit_sha256=scenario["permit_sha256"],
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="artifact_store",
        from_role_identity_sha256=TO_ID,
        from_key_id=TO_KEY_ID,
        from_signing_key=TO_PRIVATE_KEY,
        to_role="review_store",
        to_role_identity_sha256=THIRD_ID,
        to_key_id=THIRD_KEY_ID,
        to_signing_key=THIRD_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=15),
        received_at=ISSUED + timedelta(minutes=17),
        status_snapshot_sha256=scenario["status_one_verification"].snapshot_sha256,
    )
    sibling_successor = _verify_scenario_event_two(sibling_scenario, first)
    assert sibling_successor.custody_event_sha256 != (
        first_successor.custody_event_sha256
    )
    contract = custody.production_evidence_custody_contract_document()
    assert contract["custody_event"]["custody_successor_uniqueness_enforced"] is False
    assert (
        contract["custody_event"]["custody_fork_prevention_requires_external_log"]
        is True
    )
    assert (
        "external_custody_successor_uniqueness_not_provisioned" in contract["blockers"]
    )


def test_legacy_custody_verifier_is_a_fail_closed_tombstone() -> None:
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        custody._verify_signed_production_custody_event_legacy_unreachable()  # type: ignore[attr-defined,call-arg]


def test_contract_exposes_inspection_only_permit_and_bounded_v1_custody() -> None:
    contract = custody.production_evidence_custody_contract_document()
    assert contract["frozen_at_utc"] == "2026-07-19T02:00:00Z"
    assert contract["permit"]["one_use_enforced"] is False
    assert contract["permit"]["verification_consumes_permit"] is False
    assert (
        contract["permit"][
            "global_atomic_compare_and_set_consumption_registry_required"
        ]
        is True
    )
    assert contract["custody_event"]["verified_stage_sequence"] == [
        "production_permit",
        "status_snapshot",
    ]
    assert contract["custody_event"]["maximum_verified_sequence"] == 2
    assert contract["custody_event"]["post_status_snapshot_stage_implemented"] is False
    assert contract["custody_event"]["custody_successor_uniqueness_enforced"] is False
    assert (
        contract["custody_event"]["custody_fork_prevention_requires_external_log"]
        is True
    )
    assert (
        contract["status_snapshot"][
            "current_artifact_revocation_and_supersession_apply_to_full_permit_and_status_lineage"
        ]
        is True
    )
    assert "observation" in contract["custody_event"]["planned_only_stages"]
    decision = custody.production_evidence_custody_decision()
    assert decision["production_permit_one_use_enforced"] is False
    assert decision["maximum_verified_custody_sequence"] == 2
    assert decision["custody_stages_after_status_snapshot_implemented"] is False
    assert decision["custody_successor_uniqueness_enforced"] is False
    assert decision["custody_fork_prevention_requires_external_log"] is True


def test_verification_receipts_are_non_public_init_and_raw_evidence_still_wins() -> (
    None
):
    for verification_type in (
        custody.ProductionEvidencePermitVerification,
        custody.ProductionEvidenceStatusSnapshotVerification,
        custody.ProductionCustodyEventVerification,
    ):
        with pytest.raises(TypeError):
            verification_type(fake="value")

    scenario = _scenario()
    unsealed_permit = custody.ProductionEvidencePermitVerification()
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(scenario, verified_permit=unsealed_permit)
    forged_permit = deepcopy(scenario["permit_verification"])
    object.__setattr__(forged_permit, "permit_sha256", "0" * 64)
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(scenario, verified_permit=forged_permit)

    forged_current = deepcopy(scenario["status_two_verification"])
    object.__setattr__(forged_current, "snapshot_sha256", "0" * 64)
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            verified_current_status_snapshot=forged_current,
        )

    first = _verify_scenario_event_one(scenario)
    forged_previous = deepcopy(first)
    object.__setattr__(forged_previous, "custody_event_sha256", "0" * 64)
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_two(scenario, forged_previous)


def test_custody_reverifies_raw_permit_status_and_previous_event_signatures() -> None:
    scenario = _scenario()
    tampered_permit = deepcopy(scenario["permit"])
    tampered_permit["signature"]["value"] = "0" * 128
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(scenario, permit_source=tampered_permit)

    tampered_status = deepcopy(scenario["status_two"])
    tampered_status["signature"]["value"] = "0" * 128
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            status_lineage_sources=[scenario["status_one"], tampered_status],
        )

    first = _verify_scenario_event_one(scenario)
    tampered_previous = deepcopy(scenario["event_one"])
    tampered_previous["signatures"]["from"]["value"] = "0" * 128
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_two(
            scenario,
            first,
            previous_event_source=tampered_previous,
        )


def test_custody_rejects_orphan_gap_fork_reorder_and_receiver_sender_break() -> None:
    scenario = _scenario()
    first = _verify_scenario_event_one(scenario)
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_two(
            scenario,
            first,
            previous_event_source=None,
        )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_two(
            scenario,
            first,
            expected_prior_custody_event_sha256="0" * 64,
        )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        custody.build_signed_production_custody_event(
            raw_artifact_bytes=scenario["permit_raw"],
            inner_schema_id=custody.PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
            artifact_stage="production_permit",
            prior_custody_event_sha256="0" * 64,
            custody_sequence=2,
            permit_sha256=scenario["permit_sha256"],
            run_id_sha256=RUN_ID,
            lane="energy_force",
            custodian_identity_sha256=CUSTODIAN_ID,
            enrolled_host_identity_sha256=HOST_ID,
            from_role="artifact_store",
            from_role_identity_sha256=TO_ID,
            from_key_id=TO_KEY_ID,
            from_signing_key=TO_PRIVATE_KEY,
            to_role="review_store",
            to_role_identity_sha256=THIRD_ID,
            to_key_id=THIRD_KEY_ID,
            to_signing_key=THIRD_PRIVATE_KEY,
            handed_off_at=ISSUED + timedelta(minutes=15),
            received_at=ISSUED + timedelta(minutes=16),
            status_snapshot_sha256=scenario["status_one_verification"].snapshot_sha256,
        )

    broken = dict(scenario)
    broken_event = custody.build_signed_production_custody_event(
        raw_artifact_bytes=scenario["status_one_raw"],
        inner_schema_id=custody.PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        artifact_stage="status_snapshot",
        prior_custody_event_sha256=scenario["event_one"]["custody_event_sha256"],
        custody_sequence=2,
        permit_sha256=scenario["permit_sha256"],
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="run_custodian",
        from_role_identity_sha256=FROM_ID,
        from_key_id=FROM_KEY_ID,
        from_signing_key=FROM_PRIVATE_KEY,
        to_role="review_store",
        to_role_identity_sha256=THIRD_ID,
        to_key_id=THIRD_KEY_ID,
        to_signing_key=THIRD_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=15),
        received_at=ISSUED + timedelta(minutes=16),
        status_snapshot_sha256=scenario["status_one_verification"].snapshot_sha256,
    )
    broken["event_two"] = broken_event
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_two(
            broken,
            first,
            expected_from_role="run_custodian",
            expected_from_role_identity_sha256=FROM_ID,
            expected_from_key_id=FROM_KEY_ID,
        )


def test_custody_rejects_successor_handoff_before_predecessor_receipt() -> None:
    scenario = _scenario()
    first = _verify_scenario_event_one(scenario)
    broken = dict(scenario)
    broken["event_two"] = custody.build_signed_production_custody_event(
        raw_artifact_bytes=scenario["status_one_raw"],
        inner_schema_id=custody.PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        artifact_stage="status_snapshot",
        prior_custody_event_sha256=scenario["event_one"]["custody_event_sha256"],
        custody_sequence=2,
        permit_sha256=scenario["permit_sha256"],
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="artifact_store",
        from_role_identity_sha256=TO_ID,
        from_key_id=TO_KEY_ID,
        from_signing_key=TO_PRIVATE_KEY,
        to_role="review_store",
        to_role_identity_sha256=THIRD_ID,
        to_key_id=THIRD_KEY_ID,
        to_signing_key=THIRD_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=5),
        received_at=ISSUED + timedelta(minutes=5, seconds=30),
        status_snapshot_sha256=scenario["status_one_verification"].snapshot_sha256,
    )
    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="before its predecessor is received",
    ):
        _verify_scenario_event_two(broken, first)


def test_custody_rejects_dual_signed_malformed_raw_predecessors() -> None:
    scenario = _scenario()
    first = _verify_scenario_event_one(scenario)

    wrong_schema = deepcopy(scenario["event_one"])
    wrong_schema["inner_schema_id"] = INNER_SCHEMA
    wrong_schema = _resign_custody_artifact(
        wrong_schema,
        from_key_id=FROM_KEY_ID,
        from_private_key=FROM_PRIVATE_KEY,
        to_key_id=TO_KEY_ID,
        to_private_key=TO_PRIVATE_KEY,
    )
    wrong_schema_scenario = dict(scenario)
    wrong_schema_scenario["event_one"] = wrong_schema
    wrong_schema_scenario["event_two"] = custody.build_signed_production_custody_event(
        raw_artifact_bytes=scenario["status_one_raw"],
        inner_schema_id=custody.PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        artifact_stage="status_snapshot",
        prior_custody_event_sha256=wrong_schema["custody_event_sha256"],
        custody_sequence=2,
        permit_sha256=scenario["permit_sha256"],
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="artifact_store",
        from_role_identity_sha256=TO_ID,
        from_key_id=TO_KEY_ID,
        from_signing_key=TO_PRIVATE_KEY,
        to_role="review_store",
        to_role_identity_sha256=THIRD_ID,
        to_key_id=THIRD_KEY_ID,
        to_signing_key=THIRD_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=15),
        received_at=ISSUED + timedelta(minutes=16),
        status_snapshot_sha256=scenario["status_one_verification"].snapshot_sha256,
    )
    forged_schema_receipt = first
    object.__setattr__(
        forged_schema_receipt,
        "custody_event_sha256",
        wrong_schema["custody_event_sha256"],
    )
    object.__setattr__(
        forged_schema_receipt,
        "lineage_custody_event_sha256s",
        (wrong_schema["custody_event_sha256"],),
    )
    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="fixed inner schema",
    ):
        _verify_scenario_event_two(
            wrong_schema_scenario,
            forged_schema_receipt,
        )

    wrong_sender = deepcopy(scenario["event_one"])
    wrong_sender.update(
        {
            "from_role": "artifact_store",
            "from_role_identity_sha256": TO_ID,
            "from_key_id": TO_KEY_ID,
            "to_role": "run_custodian",
            "to_role_identity_sha256": FROM_ID,
            "to_key_id": FROM_KEY_ID,
        }
    )
    wrong_sender = _resign_custody_artifact(
        wrong_sender,
        from_key_id=TO_KEY_ID,
        from_private_key=TO_PRIVATE_KEY,
        to_key_id=FROM_KEY_ID,
        to_private_key=FROM_PRIVATE_KEY,
    )
    wrong_sender_scenario = dict(scenario)
    wrong_sender_scenario["event_one"] = wrong_sender
    wrong_sender_scenario["event_two"] = custody.build_signed_production_custody_event(
        raw_artifact_bytes=scenario["status_one_raw"],
        inner_schema_id=custody.PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        artifact_stage="status_snapshot",
        prior_custody_event_sha256=wrong_sender["custody_event_sha256"],
        custody_sequence=2,
        permit_sha256=scenario["permit_sha256"],
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="run_custodian",
        from_role_identity_sha256=FROM_ID,
        from_key_id=FROM_KEY_ID,
        from_signing_key=FROM_PRIVATE_KEY,
        to_role="review_store",
        to_role_identity_sha256=THIRD_ID,
        to_key_id=THIRD_KEY_ID,
        to_signing_key=THIRD_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=15),
        received_at=ISSUED + timedelta(minutes=16),
        status_snapshot_sha256=scenario["status_one_verification"].snapshot_sha256,
    )
    forged_sender_receipt = _verify_scenario_event_one(scenario)
    object.__setattr__(
        forged_sender_receipt,
        "custody_event_sha256",
        wrong_sender["custody_event_sha256"],
    )
    object.__setattr__(
        forged_sender_receipt,
        "lineage_custody_event_sha256s",
        (wrong_sender["custody_event_sha256"],),
    )
    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="initial custody sender",
    ):
        _verify_scenario_event_two(
            wrong_sender_scenario,
            forged_sender_receipt,
            expected_from_role="run_custodian",
            expected_from_role_identity_sha256=FROM_ID,
            expected_from_key_id=FROM_KEY_ID,
        )


def test_current_status_must_descend_from_handoff_and_be_fresh() -> None:
    scenario = _scenario()
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            status_lineage_sources=[scenario["status_two"]],
        )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            checked_at=ISSUED + timedelta(hours=25),
        )

    retroactive = deepcopy(scenario)
    retroactive_event = custody.build_signed_production_custody_event(
        raw_artifact_bytes=scenario["permit_raw"],
        inner_schema_id=custody.PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
        artifact_stage="production_permit",
        prior_custody_event_sha256=None,
        custody_sequence=1,
        permit_sha256=scenario["permit_sha256"],
        run_id_sha256=RUN_ID,
        lane="energy_force",
        custodian_identity_sha256=CUSTODIAN_ID,
        enrolled_host_identity_sha256=HOST_ID,
        from_role="run_custodian",
        from_role_identity_sha256=FROM_ID,
        from_key_id=FROM_KEY_ID,
        from_signing_key=FROM_PRIVATE_KEY,
        to_role="artifact_store",
        to_role_identity_sha256=TO_ID,
        to_key_id=TO_KEY_ID,
        to_signing_key=TO_PRIVATE_KEY,
        handed_off_at=ISSUED + timedelta(minutes=5),
        received_at=ISSUED + timedelta(minutes=6),
        status_snapshot_sha256=scenario["status_two_verification"].snapshot_sha256,
    )
    retroactive["event_one"] = retroactive_event
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            retroactive,
            verified_handoff_status_snapshot=scenario["status_two_verification"],
        )


def test_stage_schema_allowlist_and_inner_context_are_fail_closed() -> None:
    scenario = _scenario()
    unsupported = _canonical(
        {
            "artifact_stage": "observation",
            "contract_sha256": custody.production_evidence_custody_contract_document()[
                "contract_sha256"
            ],
            "evidence_class": custody.PRODUCTION_EVIDENCE_CLASS,
            "lane": "energy_force",
            "permit_sha256": scenario["permit_sha256"],
            "run_id_sha256": RUN_ID,
            "schema_id": INNER_SCHEMA,
        }
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        custody.build_signed_production_custody_event(
            raw_artifact_bytes=unsupported,
            inner_schema_id=INNER_SCHEMA,
            artifact_stage="observation",
            prior_custody_event_sha256=None,
            custody_sequence=1,
            permit_sha256=scenario["permit_sha256"],
            run_id_sha256=RUN_ID,
            lane="energy_force",
            custodian_identity_sha256=CUSTODIAN_ID,
            enrolled_host_identity_sha256=HOST_ID,
            from_role="run_custodian",
            from_role_identity_sha256=FROM_ID,
            from_key_id=FROM_KEY_ID,
            from_signing_key=FROM_PRIVATE_KEY,
            to_role="artifact_store",
            to_role_identity_sha256=TO_ID,
            to_key_id=TO_KEY_ID,
            to_signing_key=TO_PRIVATE_KEY,
            handed_off_at=ISSUED + timedelta(minutes=5),
            received_at=ISSUED + timedelta(minutes=6),
            status_snapshot_sha256=scenario["status_one_verification"].snapshot_sha256,
        )


@pytest.mark.parametrize("stage", ["production_permit", "status_snapshot"])
@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("artifact_stage", None),
        ("contract_sha256", "0" * 64),
        ("permit_sha256", None),
        ("run_id_sha256", "0" * 64),
        ("lane", "minimization"),
        ("custodian", "0" * 64),
        ("host", "0" * 64),
    ],
)
def test_each_allowlisted_inner_schema_rejects_missing_or_transplanted_context(
    stage: str,
    field: str,
    replacement: str | None,
) -> None:
    scenario = _scenario()
    carrier = deepcopy(
        scenario["permit"] if stage == "production_permit" else scenario["status_one"]
    )
    actual_field = field
    if field == "custodian":
        actual_field = (
            "expected_custodian_identity_sha256"
            if stage == "production_permit"
            else "custodian_identity_sha256"
        )
    elif field == "host":
        actual_field = (
            "expected_enrolled_host_identity_sha256"
            if stage == "production_permit"
            else "enrolled_host_identity_sha256"
        )
    if replacement is None:
        carrier.pop(actual_field)
    else:
        carrier[actual_field] = replacement
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _build_context_test_event(
            scenario,
            _canonical(carrier),
            stage=stage,
        )


def test_global_trust_maps_reject_unused_cross_map_key_or_identity_alias() -> None:
    scenario = _scenario()
    aliased_custody = _custody_trust()
    aliased_custody["unused-authority-key-alias"] = custody.CustodyRoleTrustAnchor(
        "unused_role",
        "b" * 64,
        ed25519_public_key_bytes(AUTHORITY_PRIVATE_KEY),
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            trusted_custody_keys=aliased_custody,
        )
    identity_alias = _custody_trust()
    identity_alias["unused-identity-alias"] = custody.CustodyRoleTrustAnchor(
        "unused_role",
        AUTHORITY_ID,
        ed25519_public_key_bytes(b"q" * 32),
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            trusted_custody_keys=identity_alias,
        )
    internal_alias = _custody_trust()
    internal_alias["unused-internal-alias"] = custody.CustodyRoleTrustAnchor(
        "unused_role",
        "c" * 64,
        ed25519_public_key_bytes(FROM_PRIVATE_KEY),
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            trusted_custody_keys=internal_alias,
        )


def test_current_status_revocation_and_supersession_apply_to_entire_chain() -> None:
    revoked = _scenario(
        current_revoked_key_rows=[
            {
                "role": "misleading_other_role",
                "key_id": TO_KEY_ID,
                "revoked_at_utc": _utc(ISSUED + timedelta(minutes=10)),
                "reason_code": "compromised",
            }
        ]
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(revoked)

    baseline = _scenario()
    permit_raw_sha = hashlib.sha256(baseline["permit_raw"]).hexdigest()
    superseded = _scenario(
        current_supersession_rows=[
            {
                "artifact_kind": "production_permit",
                "superseded_sha256": permit_raw_sha,
                "replacement_sha256": "0" * 64,
                "superseded_at_utc": _utc(ISSUED + timedelta(minutes=10)),
            }
        ]
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(superseded)

    rotated = _scenario(
        rotate_current_authority=True,
        current_revoked_key_rows=[
            {
                "role": "misleading_non_authority_role",
                "key_id": AUTHORITY_KEY_ID,
                "revoked_at_utc": _utc(ISSUED + timedelta(minutes=10)),
                "reason_code": "authority_rotation",
            }
        ],
    )
    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="currently revoked authority key",
    ):
        _verify_scenario_event_one(rotated)


@pytest.mark.parametrize("artifact_kind", ["production_permit", "permit"])
@pytest.mark.parametrize("identity_kind", ["logical", "signed_carrier"])
@pytest.mark.parametrize("disposition", ["revoked", "superseded"])
def test_current_status_blocks_all_permit_identity_and_kind_forms(
    artifact_kind: str,
    identity_kind: str,
    disposition: str,
) -> None:
    baseline = _scenario()
    identity = (
        baseline["permit_sha256"]
        if identity_kind == "logical"
        else hashlib.sha256(baseline["permit_raw"]).hexdigest()
    )
    if disposition == "revoked":
        scenario = _scenario(
            current_revoked_artifact_rows=[
                {
                    "artifact_kind": artifact_kind,
                    "artifact_sha256": identity,
                    "revoked_at_utc": _utc(ISSUED + timedelta(minutes=10)),
                    "reason_code": "permit_invalidated",
                }
            ]
        )
    else:
        scenario = _scenario(
            current_supersession_rows=[
                {
                    "artifact_kind": artifact_kind,
                    "superseded_sha256": identity,
                    "replacement_sha256": "6" * 64,
                    "superseded_at_utc": _utc(ISSUED + timedelta(minutes=10)),
                }
            ]
        )
    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="permit lineage artifact is currently revoked or superseded",
    ):
        _verify_scenario_event_one(scenario)


@pytest.mark.parametrize("ancestor_name", ["status_one", "status_two"])
@pytest.mark.parametrize("identity_kind", ["logical", "signed_carrier"])
@pytest.mark.parametrize("disposition", ["revoked", "superseded"])
def test_current_status_blocks_all_ancestor_status_identity_forms(
    ancestor_name: str,
    identity_kind: str,
    disposition: str,
) -> None:
    baseline = _scenario()
    ancestor = baseline[ancestor_name]
    verification = baseline[f"{ancestor_name}_verification"]
    identity = (
        verification.snapshot_sha256
        if identity_kind == "logical"
        else hashlib.sha256(_canonical(ancestor)).hexdigest()
    )
    if disposition == "revoked":
        scenario = _append_third_status(
            baseline,
            revoked_artifact_rows=(
                {
                    "artifact_kind": "status_snapshot",
                    "artifact_sha256": identity,
                    "revoked_at_utc": _utc(ISSUED + timedelta(minutes=20)),
                    "reason_code": "status_invalidated",
                },
            ),
        )
    else:
        scenario = _append_third_status(
            baseline,
            supersession_rows=(
                {
                    "artifact_kind": "status_snapshot",
                    "superseded_sha256": identity,
                    "replacement_sha256": "6" * 64,
                    "superseded_at_utc": _utc(ISSUED + timedelta(minutes=20)),
                },
            ),
        )
    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="status lineage artifact is currently revoked or superseded",
    ):
        _verify_scenario_event_one_with_third_status(scenario)


@pytest.mark.parametrize("identity_kind", ["logical", "signed_carrier"])
@pytest.mark.parametrize("disposition", ["revoked", "superseded"])
def test_current_status_self_identity_forms_are_fail_closed(
    identity_kind: str,
    disposition: str,
) -> None:
    scenario = _scenario()
    current = scenario["status_two_verification"]
    current_raw_sha256 = hashlib.sha256(_canonical(scenario["status_two"])).hexdigest()
    identity = (
        current.snapshot_sha256 if identity_kind == "logical" else current_raw_sha256
    )
    if disposition == "revoked":
        object.__setattr__(
            current,
            "revoked_artifact_rows",
            (("status_snapshot", identity),),
        )
    else:
        object.__setattr__(
            current,
            "supersession_rows",
            (("status_snapshot", identity, "6" * 64),),
        )
    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="status lineage artifact is currently revoked or superseded",
    ):
        custody._require_current_status_allows_evidence_lineage(  # type: ignore[attr-defined]
            current,
            permit=scenario["permit_verification"],
            permit_raw_sha256=hashlib.sha256(scenario["permit_raw"]).hexdigest(),
            status_lineage=(
                scenario["status_one_verification"],
                current,
            ),
            status_raw_sha256s=(
                hashlib.sha256(scenario["status_one_raw"]).hexdigest(),
                current_raw_sha256,
            ),
        )


def test_mapping_transport_is_exact_dict_and_preflight_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert custody._bounded_json_size(  # type: ignore[attr-defined]
        "\x7f",
        remaining=8,
        name="DEL scalar",
        active_container_ids=set(),
    ) == len(_canonical("\x7f"))

    class HostileMapping(dict[str, object]):
        def __iter__(self):  # type: ignore[no-untyped-def]
            pytest.fail("hostile Mapping must be rejected before iteration")

    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="exact built-in dict",
    ):
        custody._load_document(  # type: ignore[attr-defined]
            HostileMapping(),
            name="hostile mapping",
            maximum_bytes=128,
        )

    oversized_inputs = (
        {"padding": "x" * 129},
        {"padding": "\x7f" * 20},
    )

    def unexpected_canonicalization(_value: object) -> bytes:
        pytest.fail("oversized mapping reached canonical byte materialization")

    monkeypatch.setattr(custody, "_canonical_bytes", unexpected_canonicalization)
    for oversized in oversized_inputs:
        with pytest.raises(
            custody.ValidationProductionEvidenceCustodyError,
            match="fixed transport byte bound",
        ):
            custody._load_document(  # type: ignore[attr-defined]
                oversized,
                name="oversized mapping",
                maximum_bytes=128,
            )


def test_external_sequences_permit_argument_smuggling_and_lineage_bytes_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permit = _permit()
    too_many = tuple(
        hashlib.sha256(str(index).encode()).hexdigest()
        for index in range(custody.PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_ITEMS + 1)
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(permit, consumed_permit_sha256s=too_many)
    oversized_key_ids = tuple(
        f"revoked-{index:04d}-" + "x" * 90 for index in range(3000)
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_permit(permit, revoked_authority_key_ids=oversized_key_ids)

    scenario = _scenario()
    with pytest.raises(
        custody.ValidationProductionEvidenceCustodyError,
        match="revocation inputs differ",
    ):
        _verify_scenario_event_one(
            scenario,
            revoked_authority_key_ids=(AUTHORITY_KEY_ID,),
        )
    smuggled = _permit_verification_arguments()
    smuggled["source"] = "x" * 1_000_000
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            permit_verification_arguments=smuggled,
        )
    huge_scalar = _permit_verification_arguments()
    huge_scalar["expected_source_sha256"] = "x" * 1_000_000
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(
            scenario,
            permit_verification_arguments=huge_scalar,
        )

    first_size = len(scenario["status_one_raw"])
    monkeypatch.setattr(
        custody,
        "PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_TOTAL_BYTES",
        first_size + 1,
    )
    with pytest.raises(custody.ValidationProductionEvidenceCustodyError):
        _verify_scenario_event_one(scenario)
