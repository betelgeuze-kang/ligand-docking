from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_nonce_reservation import (
    reserve_reference_minimization_validation_authorization_nonce,
)
from betelgeuze_engine_v2.physics.reference_validation_nonce_reservation import (
    reserve_reference_validation_authorization_nonce,
)
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    build_signed_production_evidence_status_snapshot,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension import (
    FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V3,
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
    PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE,
    ProductionAtomicReservationCommitVerification,
    ProductionReservationIntentVerification,
    ProductionReservationRegistryTrustAnchor,
    ProductionReservationWitnessTrustAnchor,
    ValidationProductionReservationCustodyExtensionError,
    build_signed_production_atomic_reservation_commit,
    build_signed_production_reservation_intent,
    require_validation_production_reservation_custody_extension_contract_document,
    validation_production_reservation_custody_extension_contract_document,
    validation_production_reservation_custody_extension_decision,
    verify_signed_production_atomic_reservation_commit,
    verify_signed_production_reservation_intent,
)
from tests.unit.test_engine_v2_validation_production_review_authorization_custody_extension import (
    AUTHORIZATION_NONCE_SHA256,
    AUTHOR_IDENTITY,
    CUSTODIAN_IDENTITY,
    EVENT_RESERVATION_STORE_PRIVATE_KEY,
    EVENT_SEQUENCE_FOUR_RECEIVED_AT,
    EVENT_STATUS_AUTHORITY_PRIVATE_KEY,
    EVENT_STATUS_THREE_CHECKPOINT_SHA256,
    HOST_IDENTITY,
    STATUS_AUTHORITY_IDENTITY,
    STATUS_AUTHORITY_KEY_ID,
    _authorization_arguments,
    _event_base_reverification_arguments,
    _event_reverification_arguments,
    _event_scenario,
    _event_stage3_reverification_arguments,
    _event_stage4_reverification_arguments,
)


UTC = timezone.utc
RESERVED_AT = EVENT_SEQUENCE_FOUR_RECEIVED_AT + timedelta(minutes=1)
INTENT_SIGNED_AT = EVENT_SEQUENCE_FOUR_RECEIVED_AT + timedelta(minutes=5)
INTENT_EXPIRES_AT = INTENT_SIGNED_AT + timedelta(minutes=30)
COMMITTED_AT = INTENT_SIGNED_AT + timedelta(minutes=2)
CHECKED_AT = COMMITTED_AT + timedelta(minutes=5)
CURRENT_STATUS_ISSUED_AT = COMMITTED_AT + timedelta(minutes=2)
EXTERNAL_LAUNCH_NONCE_SHA256 = "f3" * 32
REGISTRY_REALM_IDENTITY_SHA256 = "f4" * 32
REGISTRY_EPOCH = "s0-production-2026-07"
PRIOR_REGISTRY_SEQUENCE = 41
PRIOR_REGISTRY_CHECKPOINT_SHA256 = "f5" * 32
REGISTRY_AUTHORITY_IDENTITY_SHA256 = "f6" * 32
REGISTRY_AUTHORITY_KEY_ID = "reservation-registry-2026-07"
REGISTRY_AUTHORITY_PRIVATE_KEY = bytes.fromhex("bc" * 32)
WITNESS_IDENTITY_SHA256 = "f7" * 32
WITNESS_KEY_ID = "reservation-checkpoint-witness-2026-07"
WITNESS_PRIVATE_KEY = bytes.fromhex("cd" * 32)


def _intent_authority_expectations() -> dict[str, object]:
    return {
        "expected_registry_authority_identity_sha256": (
            REGISTRY_AUTHORITY_IDENTITY_SHA256
        ),
        "expected_registry_authority_key_id": REGISTRY_AUTHORITY_KEY_ID,
        "expected_registry_authority_public_key_sha256": hashlib.sha256(
            ed25519_public_key_bytes(REGISTRY_AUTHORITY_PRIVATE_KEY)
        ).hexdigest(),
        "expected_checkpoint_witness_identity_sha256": WITNESS_IDENTITY_SHA256,
        "expected_checkpoint_witness_key_id": WITNESS_KEY_ID,
        "expected_checkpoint_witness_public_key_sha256": hashlib.sha256(
            ed25519_public_key_bytes(WITNESS_PRIVATE_KEY)
        ).hexdigest(),
    }


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _raw_prefix(scenario: dict[str, object]) -> dict[str, object]:
    return {
        "raw_authorization_carrier_bytes": scenario["raw_stage4"],
        "raw_authorization_receipt_bytes": scenario["raw_authorization"],
        "raw_review_attestation_bytes": scenario["raw_review"],
        "raw_pre_execution_review_carrier_bytes": scenario["raw_stage3"],
        "raw_sequence_three_custody_event_bytes": scenario["raw_event_three"],
        "raw_permit_bytes": scenario["raw_permit"],
        "raw_status_lineage_bytes": scenario["raw_status_lineage"],
        "raw_sequence_one_custody_event_bytes": scenario["raw_event_one"],
        "raw_sequence_two_custody_event_bytes": scenario["raw_event_two"],
        "raw_sequence_four_custody_event_bytes": scenario["raw_event_four"],
    }


def _reverification_arguments(scenario: dict[str, object]) -> dict[str, object]:
    return {
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
        "sequence_four_event_reverification_arguments": (
            _event_reverification_arguments(
                scenario["event_four"]  # type: ignore[arg-type]
            )
        ),
    }


def _scenario_with_reservation(
    tmp_path: Path,
    lane: str,
) -> dict[str, object]:
    scenario = _event_scenario(lane)
    root = tmp_path / f"{lane}-reservation"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    authorization_arguments = _authorization_arguments(lane)
    common: dict[str, object] = {
        "reservation_root": root,
        "authorization_receipt": scenario["raw_authorization"],
        "review_attestation": scenario["raw_review"],
        "trusted_reviewer_keys": authorization_arguments["trusted_reviewer_keys"],
        "expected_implementation_author_identity_sha256": AUTHOR_IDENTITY,
        "trusted_operator_keys": authorization_arguments["trusted_operator_keys"],
        "reserved_at": RESERVED_AT,
        "expected_code_commit_sha": scenario["context"][  # type: ignore[index]
            "code_commit_sha"
        ],
        "expected_runner_source_sha256": scenario["context"][  # type: ignore[index]
            "source_sha256"
        ],
        "expected_dependency_artifact_sha256_rows": authorization_arguments[
            "expected_dependency_artifact_sha256_rows"
        ],
    }
    if lane == "energy_force":
        reservation = reserve_reference_validation_authorization_nonce(
            **common  # type: ignore[arg-type]
        )
    else:
        reservation = reserve_reference_minimization_validation_authorization_nonce(
            **common  # type: ignore[arg-type]
        )
    raw_record = (root / f"{AUTHORIZATION_NONCE_SHA256}.json").read_bytes()
    extended = dict(scenario)
    extended["reservation"] = reservation
    extended["raw_reservation_record"] = raw_record
    return extended


def _build_intent(
    scenario: dict[str, object],
    *,
    external_launch_nonce_sha256: str = EXTERNAL_LAUNCH_NONCE_SHA256,
    registry_epoch: str = REGISTRY_EPOCH,
    expected_prior_registry_sequence: int = PRIOR_REGISTRY_SEQUENCE,
) -> tuple[dict[str, object], bytes]:
    intent = build_signed_production_reservation_intent(
        raw_sequence_four_prefix=_raw_prefix(scenario),
        sequence_four_reverification_arguments=_reverification_arguments(scenario),
        raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
            "raw_reservation_record"
        ],
        expected_run_context=scenario["context"],  # type: ignore[arg-type]
        external_launch_nonce_sha256=external_launch_nonce_sha256,
        registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
        registry_epoch=registry_epoch,
        expected_prior_registry_sequence=expected_prior_registry_sequence,
        expected_prior_registry_checkpoint_sha256=(PRIOR_REGISTRY_CHECKPOINT_SHA256),
        **_intent_authority_expectations(),
        from_signing_key=EVENT_RESERVATION_STORE_PRIVATE_KEY,
        signed_at=INTENT_SIGNED_AT,
        expires_at=INTENT_EXPIRES_AT,
    )
    return intent, _canonical(intent)


def _build_commit(
    scenario: dict[str, object],
    intent: dict[str, object],
    raw_intent: bytes,
    *,
    registry_identity: str = REGISTRY_AUTHORITY_IDENTITY_SHA256,
    registry_key_id: str = REGISTRY_AUTHORITY_KEY_ID,
    registry_private_key: bytes = REGISTRY_AUTHORITY_PRIVATE_KEY,
    witness_identity: str = WITNESS_IDENTITY_SHA256,
    witness_key_id: str = WITNESS_KEY_ID,
    witness_private_key: bytes = WITNESS_PRIVATE_KEY,
    expected_external_launch_nonce_sha256: str = EXTERNAL_LAUNCH_NONCE_SHA256,
    expected_prior_registry_sequence: int = PRIOR_REGISTRY_SEQUENCE,
    committed_at: datetime = COMMITTED_AT,
) -> tuple[dict[str, object], bytes]:
    commit = build_signed_production_atomic_reservation_commit(
        raw_intent_bytes=raw_intent,
        raw_sequence_four_prefix=_raw_prefix(scenario),
        sequence_four_reverification_arguments=_reverification_arguments(scenario),
        raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
            "raw_reservation_record"
        ],
        expected_run_context=scenario["context"],  # type: ignore[arg-type]
        expected_intent_sha256=intent["intent_sha256"],  # type: ignore[arg-type]
        expected_external_launch_nonce_sha256=(expected_external_launch_nonce_sha256),
        expected_registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
        expected_registry_epoch=REGISTRY_EPOCH,
        expected_prior_registry_sequence=expected_prior_registry_sequence,
        expected_prior_registry_checkpoint_sha256=(PRIOR_REGISTRY_CHECKPOINT_SHA256),
        registry_authority_identity_sha256=registry_identity,
        registry_authority_key_id=registry_key_id,
        registry_authority_signing_key=registry_private_key,
        checkpoint_witness_identity_sha256=witness_identity,
        checkpoint_witness_key_id=witness_key_id,
        checkpoint_witness_signing_key=witness_private_key,
        committed_at=committed_at,
    )
    return commit, _canonical(commit)


def _verify_commit(
    scenario: dict[str, object],
    intent: dict[str, object],
    raw_intent: bytes,
    commit: dict[str, object],
    raw_commit: bytes,
    **overrides: object,
) -> ProductionAtomicReservationCommitVerification:
    current = _current_status_descendant(scenario)
    values: dict[str, object] = {
        "source": raw_commit,
        "raw_intent_bytes": raw_intent,
        "intent_raw_sequence_four_prefix": _raw_prefix(scenario),
        "current_raw_sequence_four_prefix": _raw_prefix(current),
        "intent_sequence_four_reverification_arguments": (
            _reverification_arguments(scenario)
        ),
        "current_sequence_four_reverification_arguments": (
            _reverification_arguments(current)
        ),
        "raw_reservation_record_bytes": scenario["raw_reservation_record"],
        "expected_run_context": scenario["context"],
        "expected_intent_sha256": intent["intent_sha256"],
        "expected_commit_sha256": commit["commit_sha256"],
        "expected_raw_commit_sha256": hashlib.sha256(raw_commit).hexdigest(),
        "expected_external_launch_nonce_sha256": EXTERNAL_LAUNCH_NONCE_SHA256,
        "expected_registry_realm_identity_sha256": REGISTRY_REALM_IDENTITY_SHA256,
        "expected_registry_epoch": REGISTRY_EPOCH,
        "expected_prior_registry_sequence": PRIOR_REGISTRY_SEQUENCE,
        "expected_prior_registry_checkpoint_sha256": (PRIOR_REGISTRY_CHECKPOINT_SHA256),
        "expected_committed_registry_sequence": PRIOR_REGISTRY_SEQUENCE + 1,
        "expected_committed_registry_checkpoint_sha256": commit[
            "committed_registry_checkpoint_sha256"
        ],
        "trusted_registry_authority_keys": {
            REGISTRY_AUTHORITY_KEY_ID: ProductionReservationRegistryTrustAnchor(
                REGISTRY_AUTHORITY_IDENTITY_SHA256,
                REGISTRY_REALM_IDENTITY_SHA256,
                REGISTRY_EPOCH,
                ed25519_public_key_bytes(REGISTRY_AUTHORITY_PRIVATE_KEY),
            )
        },
        "trusted_checkpoint_witness_keys": {
            WITNESS_KEY_ID: ProductionReservationWitnessTrustAnchor(
                WITNESS_IDENTITY_SHA256,
                REGISTRY_REALM_IDENTITY_SHA256,
                REGISTRY_EPOCH,
                ed25519_public_key_bytes(WITNESS_PRIVATE_KEY),
            )
        },
        "checked_at": CHECKED_AT,
    }
    values.update(overrides)
    return verify_signed_production_atomic_reservation_commit(  # type: ignore[arg-type]
        **values
    )


def _current_status_descendant(
    scenario: dict[str, object],
    *,
    issued_at: datetime = CURRENT_STATUS_ISSUED_AT,
    revoked_key_rows: tuple[dict[str, str], ...] = (),
    revoked_artifact_rows: tuple[dict[str, str], ...] = (),
    supersession_rows: tuple[dict[str, str], ...] = (),
) -> dict[str, object]:
    status_two = scenario["status_lineage"][-1]  # type: ignore[index]
    status_three = build_signed_production_evidence_status_snapshot(
        permit_sha256=scenario["permit"]["permit_sha256"],  # type: ignore[index]
        run_id_sha256=scenario["context"]["run_id_sha256"],  # type: ignore[index]
        lane=scenario["lane"],  # type: ignore[arg-type]
        custodian_identity_sha256=CUSTODIAN_IDENTITY,
        enrolled_host_identity_sha256=HOST_IDENTITY,
        status_sequence=3,
        external_log_checkpoint_sha256=EVENT_STATUS_THREE_CHECKPOINT_SHA256,
        previous_snapshot_sha256=status_two["snapshot_sha256"],
        issued_at=issued_at,
        authority_identity_sha256=STATUS_AUTHORITY_IDENTITY,
        authority_key_id=STATUS_AUTHORITY_KEY_ID,
        signing_key=EVENT_STATUS_AUTHORITY_PRIVATE_KEY,
        revoked_key_rows=revoked_key_rows,
        revoked_artifact_rows=revoked_artifact_rows,
        supersession_rows=supersession_rows,
    )
    current = dict(scenario)
    current["status_lineage"] = [
        *scenario["status_lineage"],  # type: ignore[misc]
        status_three,
    ]
    current["raw_status_lineage"] = [
        *scenario["raw_status_lineage"],  # type: ignore[misc]
        _canonical(status_three),
    ]
    current["base_reverification_arguments"] = _event_base_reverification_arguments(
        scenario["context"],  # type: ignore[arg-type]
        scenario["event_one"],  # type: ignore[arg-type]
        scenario["event_two"],  # type: ignore[arg-type]
        current_status_snapshot_sha256=status_three["snapshot_sha256"],
        current_status_checkpoint_sha256=(EVENT_STATUS_THREE_CHECKPOINT_SHA256),
        revoked_authority_key_ids=tuple(
            sorted(row["key_id"] for row in revoked_key_rows)
        ),
    )
    return current


def test_contract_is_frozen_additive_and_claim_closed() -> None:
    contract = validation_production_reservation_custody_extension_contract_document()
    decision = validation_production_reservation_custody_extension_decision()

    assert contract["contract_sha256"] == (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    )
    assert contract["superseded_contract_sha256"] == (
        FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V3
    )
    assert contract["purpose"]["additive_sequence_five_companion_only"] is True
    assert (
        contract["purpose"]["external_serializable_registry_implemented_by_package"]
        is False
    )
    assert (
        contract["atomic_commit"]["witness_signature_covers_registry_signature"] is True
    )
    assert (
        contract["atomic_commit"]["current_revocation_and_supersession_applied"] is True
    )
    assert (
        contract["reservation_intent"][
            "registry_and_witness_identity_key_material_bound"
        ]
        is True
    )
    assert (
        contract["atomic_commit"]["external_serializable_commit_independently_verified"]
        is False
    )
    assert contract["atomic_commit"]["permit_one_use_slot_consumed"] is False
    assert contract["atomic_commit"]["custody_successor_uniqueness_enforced"] is False
    assert contract["claim_policy"]["claim_safe"] is False
    assert decision["actual_atomic_reservation_commit_present"] is False
    assert decision["external_serializable_registry_commit_verified"] is False
    assert decision["permit_one_use_slot_consumed"] is False
    assert decision["custody_successor_uniqueness_enforced"] is False
    assert decision["production_validation_execution_authorized"] is False
    assert decision["claim_safe"] is False
    assert (
        require_validation_production_reservation_custody_extension_contract_document(
            contract
        )
        == contract
    )

    tampered = deepcopy(contract)
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="differs from the frozen record",
    ):
        require_validation_production_reservation_custody_extension_contract_document(
            tampered
        )

    class DictSubclass(dict):
        pass

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="exact built-in dict",
    ):
        require_validation_production_reservation_custody_extension_contract_document(
            DictSubclass(contract)
        )

    deeply_nested: dict[str, object] = {}
    cursor = deeply_nested
    for _ in range(1_200):
        child: dict[str, object] = {}
        cursor["next"] = child
        cursor = child
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="not canonical JSON",
    ):
        require_validation_production_reservation_custody_extension_contract_document(
            deeply_nested
        )


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_intent_and_witnessed_atomic_commit_verify_both_lanes(
    tmp_path: Path,
    lane: str,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, lane)
    intent, raw_intent = _build_intent(scenario)
    verified_intent = verify_signed_production_reservation_intent(
        raw_intent,
        raw_sequence_four_prefix=_raw_prefix(scenario),
        sequence_four_reverification_arguments=_reverification_arguments(scenario),
        raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
            "raw_reservation_record"
        ],
        expected_run_context=scenario["context"],  # type: ignore[arg-type]
        expected_intent_sha256=intent["intent_sha256"],  # type: ignore[arg-type]
        expected_external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
        expected_registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
        expected_registry_epoch=REGISTRY_EPOCH,
        expected_prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
        expected_prior_registry_checkpoint_sha256=(PRIOR_REGISTRY_CHECKPOINT_SHA256),
        **_intent_authority_expectations(),
        checked_at=INTENT_SIGNED_AT + timedelta(minutes=1),
    )
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)
    verified = _verify_commit(scenario, intent, raw_intent, commit, raw_commit)

    assert type(verified_intent) is ProductionReservationIntentVerification
    assert verified_intent.lane == lane
    assert (
        verified_intent.raw_reservation_record_sha256
        == hashlib.sha256(
            scenario["raw_reservation_record"]  # type: ignore[arg-type]
        ).hexdigest()
    )
    assert type(verified) is ProductionAtomicReservationCommitVerification
    assert verified.lane == lane
    assert verified.committed_registry_sequence == PRIOR_REGISTRY_SEQUENCE + 1
    assert verified.external_serializable_registry_commit_attestation_verified is True
    assert verified.serializable_transaction_isolation_attested is True
    assert verified.status_head_compare_and_set_commit_attested is True
    assert verified.permit_one_use_slot_consumption_attested is True
    assert verified.authorization_nonce_slot_consumption_attested is True
    assert verified.predecessor_successor_slot_consumption_attested is True
    assert verified.append_only_commit_persistence_attested is True
    assert verified.checkpoint_witness_observed_commit_attested is True
    assert verified.external_serializable_registry_commit_verified is False
    assert verified.status_head_compare_and_set_committed is False
    assert verified.permit_one_use_slot_consumed is False
    assert verified.authorization_nonce_slot_consumed is False
    assert verified.predecessor_successor_slot_consumed is False
    assert verified.custody_successor_uniqueness_enforced is False
    assert verified.external_registry_non_equivocation_verified is False
    assert verified.registry_epoch_transition_continuity_verified is False
    assert verified.production_validation_execution_authorized is False
    assert verified.production_validation_results_collected is False
    assert verified.scientifically_validated is False
    assert verified.claim_safe is False


def test_same_prior_head_fork_remains_attestation_only(tmp_path: Path) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    first_intent, first_raw_intent = _build_intent(scenario)
    first_commit, first_raw_commit = _build_commit(
        scenario,
        first_intent,
        first_raw_intent,
    )
    second_launch_nonce = "e3" * 32
    second_intent, second_raw_intent = _build_intent(
        scenario,
        external_launch_nonce_sha256=second_launch_nonce,
    )
    second_commit, second_raw_commit = _build_commit(
        scenario,
        second_intent,
        second_raw_intent,
        expected_external_launch_nonce_sha256=second_launch_nonce,
    )

    first = _verify_commit(
        scenario,
        first_intent,
        first_raw_intent,
        first_commit,
        first_raw_commit,
    )
    second = _verify_commit(
        scenario,
        second_intent,
        second_raw_intent,
        second_commit,
        second_raw_commit,
        expected_external_launch_nonce_sha256=second_launch_nonce,
    )

    assert first.commit_sha256 != second.commit_sha256
    assert (
        first_commit["permit_uniqueness_slot_sha256"]
        == second_commit["permit_uniqueness_slot_sha256"]
    )
    assert first.external_serializable_registry_commit_attestation_verified is True
    assert second.external_serializable_registry_commit_attestation_verified is True
    assert first.external_serializable_registry_commit_verified is False
    assert second.external_serializable_registry_commit_verified is False
    assert first.permit_one_use_slot_consumed is False
    assert second.permit_one_use_slot_consumed is False
    assert first.custody_successor_uniqueness_enforced is False
    assert second.custody_successor_uniqueness_enforced is False


def test_uniqueness_slots_are_realm_global_across_epochs(tmp_path: Path) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    first, _first_raw = _build_intent(scenario)
    second, _second_raw = _build_intent(
        scenario,
        registry_epoch="s0-production-2026-08",
    )

    assert first["registry_epoch"] != second["registry_epoch"]
    for field in (
        "permit_uniqueness_slot_sha256",
        "authorization_nonce_uniqueness_slot_sha256",
        "predecessor_successor_uniqueness_slot_sha256",
    ):
        assert first[field] == second[field]


def test_commit_rejects_realm_epoch_and_prior_head_transplants(
    tmp_path: Path,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)

    for overrides in (
        {"expected_registry_realm_identity_sha256": "e0" * 32},
        {"expected_registry_epoch": "s0-production-2026-08"},
        {"expected_prior_registry_sequence": PRIOR_REGISTRY_SEQUENCE - 1},
        {"expected_prior_registry_checkpoint_sha256": "e1" * 32},
    ):
        with pytest.raises(ValidationProductionReservationCustodyExtensionError):
            _verify_commit(
                scenario,
                intent,
                raw_intent,
                commit,
                raw_commit,
                **overrides,
            )


def test_intent_rejects_raw_record_crosswire_and_exact_integer_alias(
    tmp_path: Path,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)
    raw_record = bytearray(scenario["raw_reservation_record"])  # type: ignore[arg-type]
    raw_record[-2] = ord("0") if raw_record[-2] != ord("0") else ord("1")

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="record verification failed",
    ):
        verify_signed_production_reservation_intent(
            raw_intent,
            raw_sequence_four_prefix=_raw_prefix(scenario),
            sequence_four_reverification_arguments=_reverification_arguments(scenario),
            raw_reservation_record_bytes=bytes(raw_record),
            expected_run_context=scenario["context"],  # type: ignore[arg-type]
            expected_intent_sha256=intent["intent_sha256"],  # type: ignore[arg-type]
            expected_external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
            expected_registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            expected_registry_epoch=REGISTRY_EPOCH,
            expected_prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
            expected_prior_registry_checkpoint_sha256=(
                PRIOR_REGISTRY_CHECKPOINT_SHA256
            ),
            **_intent_authority_expectations(),
            checked_at=INTENT_SIGNED_AT + timedelta(minutes=1),
        )

    signature_tamper = deepcopy(intent)
    signature_tamper["signature"]["value"] = "0" * 128  # type: ignore[index]
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="signature verification failed",
    ):
        verify_signed_production_reservation_intent(
            _canonical(signature_tamper),
            raw_sequence_four_prefix=_raw_prefix(scenario),
            sequence_four_reverification_arguments=(
                _reverification_arguments(scenario)
            ),
            raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
                "raw_reservation_record"
            ],
            expected_run_context=scenario["context"],  # type: ignore[arg-type]
            expected_intent_sha256=intent["intent_sha256"],  # type: ignore[arg-type]
            expected_external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
            expected_registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            expected_registry_epoch=REGISTRY_EPOCH,
            expected_prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
            expected_prior_registry_checkpoint_sha256=(
                PRIOR_REGISTRY_CHECKPOINT_SHA256
            ),
            **_intent_authority_expectations(),
            checked_at=INTENT_SIGNED_AT + timedelta(minutes=1),
        )

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="exact integer",
    ):
        build_signed_production_reservation_intent(
            raw_sequence_four_prefix=_raw_prefix(scenario),
            sequence_four_reverification_arguments=(
                _reverification_arguments(scenario)
            ),
            raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
                "raw_reservation_record"
            ],
            expected_run_context=scenario["context"],  # type: ignore[arg-type]
            external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
            registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            registry_epoch=REGISTRY_EPOCH,
            expected_prior_registry_sequence=True,  # type: ignore[arg-type]
            expected_prior_registry_checkpoint_sha256=(
                PRIOR_REGISTRY_CHECKPOINT_SHA256
            ),
            **_intent_authority_expectations(),
            from_signing_key=EVENT_RESERVATION_STORE_PRIVATE_KEY,
            signed_at=INTENT_SIGNED_AT,
            expires_at=INTENT_EXPIRES_AT,
        )

    deeply_nested = b"[" * 129 + b"0" + b"]" * 129
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="nesting bound",
    ):
        verify_signed_production_reservation_intent(
            deeply_nested,
            raw_sequence_four_prefix=_raw_prefix(scenario),
            sequence_four_reverification_arguments=(
                _reverification_arguments(scenario)
            ),
            raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
                "raw_reservation_record"
            ],
            expected_run_context=scenario["context"],  # type: ignore[arg-type]
            expected_intent_sha256=intent["intent_sha256"],  # type: ignore[arg-type]
            expected_external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
            expected_registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            expected_registry_epoch=REGISTRY_EPOCH,
            expected_prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
            expected_prior_registry_checkpoint_sha256=(
                PRIOR_REGISTRY_CHECKPOINT_SHA256
            ),
            **_intent_authority_expectations(),
            checked_at=INTENT_SIGNED_AT + timedelta(minutes=1),
        )

    oversized_integer = b'{"value":' + b"1" * 5_000 + b"}"
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="canonical ASCII JSON",
    ):
        verify_signed_production_reservation_intent(
            oversized_integer,
            raw_sequence_four_prefix=_raw_prefix(scenario),
            sequence_four_reverification_arguments=(
                _reverification_arguments(scenario)
            ),
            raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
                "raw_reservation_record"
            ],
            expected_run_context=scenario["context"],  # type: ignore[arg-type]
            expected_intent_sha256=intent["intent_sha256"],  # type: ignore[arg-type]
            expected_external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
            expected_registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            expected_registry_epoch=REGISTRY_EPOCH,
            expected_prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
            expected_prior_registry_checkpoint_sha256=(
                PRIOR_REGISTRY_CHECKPOINT_SHA256
            ),
            **_intent_authority_expectations(),
            checked_at=INTENT_SIGNED_AT + timedelta(minutes=1),
        )


def test_intent_rejects_registry_sequence_overflow(tmp_path: Path) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="exact integer",
    ):
        _build_intent(
            scenario,
            expected_prior_registry_sequence=(
                PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE
            ),
        )

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="run context must be an exact built-in dict",
    ):
        build_signed_production_reservation_intent(
            raw_sequence_four_prefix=_raw_prefix(scenario),
            sequence_four_reverification_arguments=(
                _reverification_arguments(scenario)
            ),
            raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
                "raw_reservation_record"
            ],
            expected_run_context=None,  # type: ignore[arg-type]
            external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
            registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            registry_epoch=REGISTRY_EPOCH,
            expected_prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
            expected_prior_registry_checkpoint_sha256=(
                PRIOR_REGISTRY_CHECKPOINT_SHA256
            ),
            **_intent_authority_expectations(),
            from_signing_key=EVENT_RESERVATION_STORE_PRIVATE_KEY,
            signed_at=INTENT_SIGNED_AT,
            expires_at=INTENT_EXPIRES_AT,
        )


def test_commit_rejects_tamper_raw_identity_and_registry_result_crosswire(
    tmp_path: Path,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)
    tampered = deepcopy(commit)
    tampered["registry_attests_permit_one_use_slot_consumption"] = False
    tampered_raw = _canonical(tampered)

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="logical SHA-256 verification failed",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            tampered_raw,
            expected_raw_commit_sha256=hashlib.sha256(tampered_raw).hexdigest(),
        )

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="raw atomic reservation commit identity is cross-wired",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            expected_raw_commit_sha256="0" * 64,
        )

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="committed registry sequence differs",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            expected_committed_registry_sequence=PRIOR_REGISTRY_SEQUENCE + 2,
        )

    for signature_field in (
        "registry_signature",
        "checkpoint_witness_signature",
    ):
        signature_tamper = deepcopy(commit)
        signature_tamper[signature_field]["value"] = "0" * 128  # type: ignore[index]
        signature_tamper_raw = _canonical(signature_tamper)
        with pytest.raises(
            ValidationProductionReservationCustodyExtensionError,
            match="signature verification failed",
        ):
            _verify_commit(
                scenario,
                intent,
                raw_intent,
                commit,
                signature_tamper_raw,
                expected_raw_commit_sha256=hashlib.sha256(
                    signature_tamper_raw
                ).hexdigest(),
            )


def test_final_verifier_accepts_exact_status_descendant_and_rejects_prefix_tamper(
    tmp_path: Path,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)
    current = _current_status_descendant(scenario)

    verified = _verify_commit(
        scenario,
        intent,
        raw_intent,
        commit,
        raw_commit,
        current_raw_sequence_four_prefix=_raw_prefix(current),
        current_sequence_four_reverification_arguments=(
            _reverification_arguments(current)
        ),
    )
    assert verified.current_status_sequence == 3
    assert verified.current_status_descendant_reverified is True

    reordered = _raw_prefix(current)
    lineage = list(reordered["raw_status_lineage_bytes"])  # type: ignore[arg-type]
    lineage[0], lineage[1] = lineage[1], lineage[0]
    reordered["raw_status_lineage_bytes"] = lineage
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="not an exact descendant",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            current_raw_sequence_four_prefix=reordered,
            current_sequence_four_reverification_arguments=(
                _reverification_arguments(current)
            ),
        )

    superseded = _current_status_descendant(
        scenario,
        supersession_rows=(
            {
                "artifact_kind": "reservation_seq5",
                "superseded_sha256": commit["commit_sha256"],  # type: ignore[dict-item]
                "replacement_sha256": "fb" * 32,
                "superseded_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="currently revoked or superseded",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            current_raw_sequence_four_prefix=_raw_prefix(superseded),
            current_sequence_four_reverification_arguments=(
                _reverification_arguments(superseded)
            ),
        )

    changed_ancestor = _raw_prefix(current)
    changed_ancestor["raw_sequence_four_custody_event_bytes"] = (
        changed_ancestor["raw_sequence_four_custody_event_bytes"] + b" "  # type: ignore[operator]
    )
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="differs outside status lineage",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            current_raw_sequence_four_prefix=changed_ancestor,
            current_sequence_four_reverification_arguments=(
                _reverification_arguments(current)
            ),
        )


def test_final_verifier_rejects_status_descendant_that_predates_commit(
    tmp_path: Path,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="lacks a post-commit descendant",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            current_raw_sequence_four_prefix=_raw_prefix(scenario),
            current_sequence_four_reverification_arguments=(
                _reverification_arguments(scenario)
            ),
        )

    stale = _current_status_descendant(
        scenario,
        issued_at=COMMITTED_AT - timedelta(seconds=1),
    )

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="status fence was stale",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            current_raw_sequence_four_prefix=_raw_prefix(stale),
            current_sequence_four_reverification_arguments=(
                _reverification_arguments(stale)
            ),
        )


@pytest.mark.parametrize(
    "identity_field",
    [
        "reservation_logical",
        "reservation_raw",
        "intent_logical",
        "intent_raw",
        "commit_logical",
        "commit_raw",
        "slot",
        "checkpoint",
        "raw_permit",
        "prior_registry_checkpoint",
        "registry_realm",
        "registry_identity",
        "registry_public_key",
        "witness_identity",
        "witness_public_key",
        "status_logical",
        "status_raw",
        "status_checkpoint",
    ],
)
def test_current_status_rejects_new_seq5_logical_raw_and_registry_identities(
    tmp_path: Path,
    identity_field: str,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)
    identity = {
        "reservation_logical": intent["reservation_record_sha256"],
        "reservation_raw": intent["raw_reservation_record_sha256"],
        "intent_logical": intent["intent_sha256"],
        "intent_raw": hashlib.sha256(raw_intent).hexdigest(),
        "commit_logical": commit["commit_sha256"],
        "commit_raw": hashlib.sha256(raw_commit).hexdigest(),
        "slot": commit["permit_uniqueness_slot_sha256"],
        "checkpoint": commit["committed_registry_checkpoint_sha256"],
        "raw_permit": hashlib.sha256(
            scenario["raw_permit"]  # type: ignore[arg-type]
        ).hexdigest(),
        "prior_registry_checkpoint": PRIOR_REGISTRY_CHECKPOINT_SHA256,
        "registry_realm": REGISTRY_REALM_IDENTITY_SHA256,
        "registry_identity": REGISTRY_AUTHORITY_IDENTITY_SHA256,
        "registry_public_key": hashlib.sha256(
            ed25519_public_key_bytes(REGISTRY_AUTHORITY_PRIVATE_KEY)
        ).hexdigest(),
        "witness_identity": WITNESS_IDENTITY_SHA256,
        "witness_public_key": hashlib.sha256(
            ed25519_public_key_bytes(WITNESS_PRIVATE_KEY)
        ).hexdigest(),
        "status_logical": scenario["status_lineage"][0][  # type: ignore[index]
            "snapshot_sha256"
        ],
        "status_raw": hashlib.sha256(
            scenario["raw_status_lineage"][0]  # type: ignore[index]
        ).hexdigest(),
        "status_checkpoint": scenario["status_lineage"][0][  # type: ignore[index]
            "external_log_checkpoint_sha256"
        ],
    }[identity_field]
    current = _current_status_descendant(
        scenario,
        revoked_artifact_rows=(
            {
                "artifact_kind": "reservation_seq5",
                "artifact_sha256": identity,  # type: ignore[dict-item]
                "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                "reason_code": "compromised",
            },
        ),
    )

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="currently revoked or superseded",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            current_raw_sequence_four_prefix=_raw_prefix(current),
            current_sequence_four_reverification_arguments=(
                _reverification_arguments(current)
            ),
        )


def test_current_status_rejects_registry_key_and_final_rejects_prior_material_alias(
    tmp_path: Path,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)
    current = _current_status_descendant(
        scenario,
        revoked_key_rows=(
            {
                "role": "reservation_registry",
                "key_id": REGISTRY_AUTHORITY_KEY_ID,
                "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                "reason_code": "rotation",
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="currently revoked",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            current_raw_sequence_four_prefix=_raw_prefix(current),
            current_sequence_four_reverification_arguments=(
                _reverification_arguments(current)
            ),
        )

    prior_private_key = bytes.fromhex("aa" * 32)
    alias_key_id = "new-registry-key-id"
    alias_identity = "fa" * 32
    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="aliases a prior role",
    ):
        _verify_commit(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            trusted_registry_authority_keys={
                REGISTRY_AUTHORITY_KEY_ID: ProductionReservationRegistryTrustAnchor(
                    REGISTRY_AUTHORITY_IDENTITY_SHA256,
                    REGISTRY_REALM_IDENTITY_SHA256,
                    REGISTRY_EPOCH,
                    ed25519_public_key_bytes(REGISTRY_AUTHORITY_PRIVATE_KEY),
                ),
                alias_key_id: ProductionReservationRegistryTrustAnchor(
                    alias_identity,
                    REGISTRY_REALM_IDENTITY_SHA256,
                    REGISTRY_EPOCH,
                    ed25519_public_key_bytes(prior_private_key),
                ),
            },
        )


def test_commit_time_window_and_verification_dtos_are_sealed(tmp_path: Path) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="not yet valid",
    ):
        verify_signed_production_reservation_intent(
            raw_intent,
            raw_sequence_four_prefix=_raw_prefix(scenario),
            sequence_four_reverification_arguments=(
                _reverification_arguments(scenario)
            ),
            raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
                "raw_reservation_record"
            ],
            expected_run_context=scenario["context"],  # type: ignore[arg-type]
            expected_intent_sha256=intent["intent_sha256"],  # type: ignore[arg-type]
            expected_external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
            expected_registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            expected_registry_epoch=REGISTRY_EPOCH,
            expected_prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
            expected_prior_registry_checkpoint_sha256=(
                PRIOR_REGISTRY_CHECKPOINT_SHA256
            ),
            **_intent_authority_expectations(),
            checked_at=INTENT_SIGNED_AT - timedelta(seconds=1),
        )

    with pytest.raises(
        ValidationProductionReservationCustodyExtensionError,
        match="expired",
    ):
        build_signed_production_atomic_reservation_commit(
            raw_intent_bytes=raw_intent,
            raw_sequence_four_prefix=_raw_prefix(scenario),
            sequence_four_reverification_arguments=(
                _reverification_arguments(scenario)
            ),
            raw_reservation_record_bytes=scenario[  # type: ignore[arg-type]
                "raw_reservation_record"
            ],
            expected_run_context=scenario["context"],  # type: ignore[arg-type]
            expected_intent_sha256=intent["intent_sha256"],  # type: ignore[arg-type]
            expected_external_launch_nonce_sha256=EXTERNAL_LAUNCH_NONCE_SHA256,
            expected_registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            expected_registry_epoch=REGISTRY_EPOCH,
            expected_prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
            expected_prior_registry_checkpoint_sha256=(
                PRIOR_REGISTRY_CHECKPOINT_SHA256
            ),
            registry_authority_identity_sha256=(REGISTRY_AUTHORITY_IDENTITY_SHA256),
            registry_authority_key_id=REGISTRY_AUTHORITY_KEY_ID,
            registry_authority_signing_key=REGISTRY_AUTHORITY_PRIVATE_KEY,
            checkpoint_witness_identity_sha256=WITNESS_IDENTITY_SHA256,
            checkpoint_witness_key_id=WITNESS_KEY_ID,
            checkpoint_witness_signing_key=WITNESS_PRIVATE_KEY,
            committed_at=INTENT_EXPIRES_AT,
        )

    with pytest.raises(TypeError):
        ProductionReservationIntentVerification(fake="value")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        ProductionAtomicReservationCommitVerification(fake="value")  # type: ignore[call-arg]
