from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_custody_extension import (
    PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
    ProductionReservationRegistryTrustAnchor,
    ProductionReservationWitnessTrustAnchor,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256,
    PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_AGE,
    PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES,
    PRODUCTION_RESERVATION_REGISTRY_TRANSACTION_PROOF_SCHEMA_ID,
    ProductionReservationRegistryBackendTrustAnchor,
    ProductionReservationRegistryHeadObserverTrustAnchor,
    ValidationProductionReservationRegistryProofError,
    production_reservation_native_registry_checkpoint_sha256,
    production_reservation_sparse_merkle_consumed_leaf_sha256,
    production_reservation_sparse_merkle_default_sha256s,
    production_reservation_sparse_merkle_node_sha256,
    require_validation_production_reservation_registry_proof_contract_document,
    validation_production_reservation_registry_proof_contract_document,
    validation_production_reservation_registry_proof_decision,
    verify_external_production_reservation_registry_transaction_proof,
)
from tests.unit.test_engine_v2_validation_production_reservation_custody_extension import (
    CHECKED_AT,
    COMMITTED_AT,
    EXTERNAL_LAUNCH_NONCE_SHA256,
    PRIOR_REGISTRY_CHECKPOINT_SHA256,
    PRIOR_REGISTRY_SEQUENCE,
    REGISTRY_AUTHORITY_IDENTITY_SHA256,
    REGISTRY_AUTHORITY_KEY_ID,
    REGISTRY_AUTHORITY_PRIVATE_KEY,
    REGISTRY_EPOCH,
    REGISTRY_REALM_IDENTITY_SHA256,
    WITNESS_IDENTITY_SHA256,
    WITNESS_KEY_ID,
    WITNESS_PRIVATE_KEY,
    _build_commit,
    _build_intent,
    _canonical,
    _current_status_descendant,
    _raw_prefix,
    _reverification_arguments,
    _scenario_with_reservation,
)


UTC = timezone.utc
PROOF_ISSUED_AT = COMMITTED_AT + timedelta(minutes=1)
OBSERVED_AT = COMMITTED_AT + timedelta(minutes=2)
PRIOR_NATIVE_CHECKPOINT_SHA256 = "31" * 32
BACKEND_IDENTITY_SHA256 = "32" * 32
BACKEND_KEY_ID = "external-registry-backend-2026-07"
BACKEND_PRIVATE_KEY = bytes.fromhex("de" * 32)
BACKEND_BINARY_SHA256 = "33" * 32
BACKEND_SCHEMA_SHA256 = "34" * 32
BACKEND_CONFIGURATION_SHA256 = "35" * 32
BACKEND_DEPLOYMENT_SHA256 = "36" * 32
OBSERVER_IDENTITY_SHA256 = "37" * 32
OBSERVER_KEY_ID = "external-registry-head-observer-2026-07"
OBSERVER_PRIVATE_KEY = bytes.fromhex("ef" * 32)
OBSERVER_DEPLOYMENT_SHA256 = "38" * 32
TRUST_VALID_FROM = "2026-07-19T00:00:00Z"
TRUST_VALID_UNTIL = "2026-07-20T00:00:00Z"


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slot_sha256(*, kind: str, value: object) -> str:
    return _sha256(
        {
            "registry_realm_identity_sha256": REGISTRY_REALM_IDENTITY_SHA256,
            "slot_kind": kind,
            "slot_value": value,
        }
    )


def _backend_anchor(
    *,
    valid_from_utc: str = TRUST_VALID_FROM,
    valid_until_utc: str = TRUST_VALID_UNTIL,
) -> ProductionReservationRegistryBackendTrustAnchor:
    return ProductionReservationRegistryBackendTrustAnchor(
        BACKEND_IDENTITY_SHA256,
        REGISTRY_REALM_IDENTITY_SHA256,
        REGISTRY_EPOCH,
        BACKEND_BINARY_SHA256,
        BACKEND_SCHEMA_SHA256,
        BACKEND_CONFIGURATION_SHA256,
        BACKEND_DEPLOYMENT_SHA256,
        valid_from_utc,
        valid_until_utc,
        ed25519_public_key_bytes(BACKEND_PRIVATE_KEY),
    )


def _observer_anchor(
    *,
    valid_from_utc: str = TRUST_VALID_FROM,
    valid_until_utc: str = TRUST_VALID_UNTIL,
) -> ProductionReservationRegistryHeadObserverTrustAnchor:
    return ProductionReservationRegistryHeadObserverTrustAnchor(
        OBSERVER_IDENTITY_SHA256,
        REGISTRY_REALM_IDENTITY_SHA256,
        REGISTRY_EPOCH,
        OBSERVER_DEPLOYMENT_SHA256,
        valid_from_utc,
        valid_until_utc,
        ed25519_public_key_bytes(OBSERVER_PRIVATE_KEY),
    )


def _seq5_arguments(
    scenario: dict[str, object],
    intent: dict[str, object],
    raw_intent: bytes,
    commit: dict[str, object],
    raw_commit: bytes,
    *,
    current_scenario: dict[str, object] | None = None,
) -> dict[str, object]:
    current = (
        _current_status_descendant(scenario)
        if current_scenario is None
        else current_scenario
    )
    return {
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
        "expected_raw_commit_sha256": _raw_sha256(raw_commit),
        "expected_external_launch_nonce_sha256": intent[
            "external_launch_nonce_sha256"
        ],
        "expected_registry_realm_identity_sha256": (
            REGISTRY_REALM_IDENTITY_SHA256
        ),
        "expected_registry_epoch": REGISTRY_EPOCH,
        "expected_prior_registry_sequence": PRIOR_REGISTRY_SEQUENCE,
        "expected_prior_registry_checkpoint_sha256": (
            PRIOR_REGISTRY_CHECKPOINT_SHA256
        ),
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
    }


def _sparse_state(
    leaves: dict[str, str],
    *,
    path_slots: tuple[str, ...] = (),
) -> tuple[str, dict[str, list[str]]]:
    defaults = production_reservation_sparse_merkle_default_sha256s()
    levels: list[dict[int, str]] = [
        {int(slot, 16): leaf for slot, leaf in leaves.items()}
    ]
    for level in range(256):
        current = levels[-1]
        parents: dict[int, str] = {}
        for parent in sorted({index >> 1 for index in current}):
            left = current.get(parent << 1, defaults[level])
            right = current.get((parent << 1) | 1, defaults[level])
            parents[parent] = production_reservation_sparse_merkle_node_sha256(
                left,
                right,
            )
        levels.append(parents)
    root = levels[-1].get(0, defaults[-1])
    paths: dict[str, list[str]] = {}
    for slot in sorted({*leaves, *path_slots}):
        key = int(slot, 16)
        paths[slot] = [
            levels[level].get((key >> level) ^ 1, defaults[level])
            for level in range(256)
        ]
    return root, paths


def _resign(
    document: dict[str, object],
    *,
    backend_key_id: str = BACKEND_KEY_ID,
    backend_private_key: bytes = BACKEND_PRIVATE_KEY,
    observer_key_id: str = OBSERVER_KEY_ID,
    observer_private_key: bytes = OBSERVER_PRIVATE_KEY,
) -> tuple[dict[str, object], bytes]:
    projection = {
        key: value
        for key, value in document.items()
        if key not in {"proof_sha256", "backend_signature", "head_observer_signature"}
    }
    proof_sha256 = _sha256(projection)
    backend_payload = {**projection, "proof_sha256": proof_sha256}
    backend_signature = {
        "algorithm": "Ed25519",
        "key_id": backend_key_id,
        "value": sign_ed25519(_canonical(backend_payload), backend_private_key),
    }
    observer_payload = {**backend_payload, "backend_signature": backend_signature}
    observer_signature = {
        "algorithm": "Ed25519",
        "key_id": observer_key_id,
        "value": sign_ed25519(_canonical(observer_payload), observer_private_key),
    }
    signed = {
        **projection,
        "proof_sha256": proof_sha256,
        "backend_signature": backend_signature,
        "head_observer_signature": observer_signature,
    }
    return signed, _canonical(signed)


def _proof(
    scenario: dict[str, object],
    intent: dict[str, object],
    raw_intent: bytes,
    commit: dict[str, object],
    raw_commit: bytes,
    *,
    initial_leaves: dict[str, str] | None = None,
) -> dict[str, object]:
    transaction = commit["registry_transaction_sha256"]
    assert isinstance(transaction, str)
    slots = {
        "permit": _slot_sha256(
            kind="permit",
            value=commit["permit_sha256"],
        ),
        "authorization_nonce": _slot_sha256(
            kind="authorization_nonce",
            value=commit["authorization_nonce_sha256"],
        ),
        "predecessor_successor": _slot_sha256(
            kind="predecessor_logical_and_raw",
            value={
                "logical_sha256": commit["prior_custody_event_sha256"],
                "raw_sha256": commit["prior_raw_custody_event_sha256"],
            },
        ),
    }
    current_leaves = dict(initial_leaves or {})
    if set(current_leaves) & set(slots.values()):
        raise AssertionError("test fixture pre-populates a reservation target slot")
    prior_root, _ = _sparse_state(current_leaves)
    current_root = prior_root
    transitions: list[dict[str, object]] = []
    for kind in ("permit", "authorization_nonce", "predecessor_successor"):
        slot = slots[kind]
        state_root_before, paths = _sparse_state(
            current_leaves,
            path_slots=(slot,),
        )
        assert state_root_before == current_root
        current_leaves[slot] = (
            production_reservation_sparse_merkle_consumed_leaf_sha256(
                slot_sha256=slot,
                registry_transaction_sha256=transaction,
            )
        )
        state_root_after, _ = _sparse_state(current_leaves)
        transitions.append(
            {
                "slot_kind": kind,
                "slot_sha256": slot,
                "state_root_before_sha256": state_root_before,
                "state_root_after_sha256": state_root_after,
                "sibling_sha256s": paths[slot],
                "consumed_by_registry_transaction_sha256": transaction,
            }
        )
        current_root = state_root_after
    committed_root = current_root
    native_checkpoint = production_reservation_native_registry_checkpoint_sha256(
        registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
        registry_epoch=REGISTRY_EPOCH,
        prior_registry_sequence=PRIOR_REGISTRY_SEQUENCE,
        committed_registry_sequence=PRIOR_REGISTRY_SEQUENCE + 1,
        prior_native_registry_checkpoint_sha256=PRIOR_NATIVE_CHECKPOINT_SHA256,
        seq5_prior_registry_checkpoint_sha256=PRIOR_REGISTRY_CHECKPOINT_SHA256,
        seq5_committed_registry_checkpoint_sha256=commit[
            "committed_registry_checkpoint_sha256"
        ],  # type: ignore[arg-type]
        registry_transaction_sha256=transaction,
        prior_registry_state_root_sha256=prior_root,
        committed_registry_state_root_sha256=committed_root,
        backend_identity_sha256=BACKEND_IDENTITY_SHA256,
        backend_service_binary_sha256=BACKEND_BINARY_SHA256,
        backend_service_schema_sha256=BACKEND_SCHEMA_SHA256,
        backend_service_configuration_sha256=BACKEND_CONFIGURATION_SHA256,
        backend_service_deployment_sha256=BACKEND_DEPLOYMENT_SHA256,
        committed_at_utc=commit["committed_at_utc"],  # type: ignore[arg-type]
    )
    projection: dict[str, object] = {
        "schema_id": PRODUCTION_RESERVATION_REGISTRY_TRANSACTION_PROOF_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
        ),
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_same_epoch_reservation_registry_transaction_proof",
        "lane": commit["lane"],
        "sequence_five_commit_sha256": commit["commit_sha256"],
        "raw_sequence_five_commit_sha256": _raw_sha256(raw_commit),
        "registry_transaction_sha256": transaction,
        "registry_realm_identity_sha256": REGISTRY_REALM_IDENTITY_SHA256,
        "registry_epoch": REGISTRY_EPOCH,
        "prior_registry_sequence": PRIOR_REGISTRY_SEQUENCE,
        "committed_registry_sequence": PRIOR_REGISTRY_SEQUENCE + 1,
        "seq5_prior_registry_checkpoint_sha256": PRIOR_REGISTRY_CHECKPOINT_SHA256,
        "seq5_committed_registry_checkpoint_sha256": commit[
            "committed_registry_checkpoint_sha256"
        ],
        "prior_native_registry_checkpoint_sha256": (
            PRIOR_NATIVE_CHECKPOINT_SHA256
        ),
        "committed_native_registry_checkpoint_sha256": native_checkpoint,
        "prior_registry_state_root_sha256": prior_root,
        "committed_registry_state_root_sha256": committed_root,
        "slot_transition_proofs": transitions,
        "backend_identity_sha256": BACKEND_IDENTITY_SHA256,
        "backend_key_id": BACKEND_KEY_ID,
        "backend_public_key_sha256": _raw_sha256(
            ed25519_public_key_bytes(BACKEND_PRIVATE_KEY)
        ),
        "backend_service_binary_sha256": BACKEND_BINARY_SHA256,
        "backend_service_schema_sha256": BACKEND_SCHEMA_SHA256,
        "backend_service_configuration_sha256": BACKEND_CONFIGURATION_SHA256,
        "backend_service_deployment_sha256": BACKEND_DEPLOYMENT_SHA256,
        "head_observer_identity_sha256": OBSERVER_IDENTITY_SHA256,
        "head_observer_key_id": OBSERVER_KEY_ID,
        "head_observer_public_key_sha256": _raw_sha256(
            ed25519_public_key_bytes(OBSERVER_PRIVATE_KEY)
        ),
        "head_observer_deployment_sha256": OBSERVER_DEPLOYMENT_SHA256,
        "committed_at_utc": commit["committed_at_utc"],
        "proof_issued_at_utc": _utc(PROOF_ISSUED_AT),
        "observed_at_utc": _utc(OBSERVED_AT),
        "external_transaction_outcome": "backend_attested_committed",
        "external_transaction_isolation": "backend_attested_serializable",
        "backend_serializable_transaction_attestation_verified": True,
        "exact_three_slot_state_transition_verified": True,
        "caller_expected_native_head_match_verified": True,
        "observer_signed_native_checkpoint_verified": True,
        "external_serializable_registry_commit_verified": False,
        "registry_head_compare_and_set_committed": False,
        "permit_one_use_slot_consumed": False,
        "authorization_nonce_slot_consumed": False,
        "predecessor_successor_slot_consumed": False,
        "status_head_compare_and_set_committed": False,
        "custody_successor_uniqueness_enforced": False,
        "external_registry_non_equivocation_verified": False,
        "registry_epoch_transition_continuity_verified": False,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "scientifically_validated": False,
        "parameter_fitting_authorized": False,
        "product_qualified": False,
        "claim_safe": False,
        "superseded": False,
        "revoked": False,
    }
    document, raw = _resign(projection)
    return {
        "document": document,
        "raw": raw,
        "seq5_arguments": _seq5_arguments(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
        ),
        "native_checkpoint": native_checkpoint,
        "scenario": scenario,
        "intent": intent,
        "raw_intent": raw_intent,
        "commit": commit,
        "raw_commit": raw_commit,
    }


def _scenario_and_proof(tmp_path: Path, lane: str) -> dict[str, object]:
    scenario = _scenario_with_reservation(tmp_path, lane)
    intent, raw_intent = _build_intent(scenario)
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)
    return _proof(scenario, intent, raw_intent, commit, raw_commit)


def _with_current_status(
    bundle: dict[str, object],
    *,
    issued_at: datetime = OBSERVED_AT,
    revoked_key_rows: tuple[dict[str, str], ...] = (),
    revoked_artifact_rows: tuple[dict[str, str], ...] = (),
    supersession_rows: tuple[dict[str, str], ...] = (),
) -> dict[str, object]:
    scenario = bundle["scenario"]
    intent = bundle["intent"]
    raw_intent = bundle["raw_intent"]
    commit = bundle["commit"]
    raw_commit = bundle["raw_commit"]
    assert isinstance(scenario, dict)
    assert isinstance(intent, dict)
    assert isinstance(raw_intent, bytes)
    assert isinstance(commit, dict)
    assert isinstance(raw_commit, bytes)
    current = _current_status_descendant(
        scenario,
        issued_at=issued_at,
        revoked_key_rows=revoked_key_rows,
        revoked_artifact_rows=revoked_artifact_rows,
        supersession_rows=supersession_rows,
    )
    return {
        **bundle,
        "seq5_arguments": _seq5_arguments(
            scenario,
            intent,
            raw_intent,
            commit,
            raw_commit,
            current_scenario=current,
        ),
    }


def _verification_arguments(
    bundle: dict[str, object],
    **overrides: object,
) -> dict[str, object]:
    raw = bundle["raw"]
    document = bundle["document"]
    assert isinstance(raw, bytes)
    assert isinstance(document, dict)
    values: dict[str, object] = {
        "source": raw,
        "sequence_five_reverification_arguments": bundle["seq5_arguments"],
        "expected_proof_sha256": document["proof_sha256"],
        "expected_raw_proof_sha256": _raw_sha256(raw),
        "expected_prior_native_registry_checkpoint_sha256": (
            PRIOR_NATIVE_CHECKPOINT_SHA256
        ),
        "expected_caller_registry_sequence": PRIOR_REGISTRY_SEQUENCE + 1,
        "expected_caller_native_registry_checkpoint_sha256": bundle[
            "native_checkpoint"
        ],
        "trusted_registry_backend_keys": {BACKEND_KEY_ID: _backend_anchor()},
        "trusted_registry_head_observer_keys": {
            OBSERVER_KEY_ID: _observer_anchor()
        },
        "checked_at": CHECKED_AT,
    }
    values.update(overrides)
    return values


def _verify(bundle: dict[str, object], **overrides: object):
    return verify_external_production_reservation_registry_transaction_proof(
        **_verification_arguments(bundle, **overrides)  # type: ignore[arg-type]
    )


def test_contract_is_frozen_verifier_only_and_claim_closed() -> None:
    first = validation_production_reservation_registry_proof_contract_document()
    second = validation_production_reservation_registry_proof_contract_document()
    assert first == second
    assert (
        first["contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_REGISTRY_PROOF_CONTRACT_SHA256
    )
    assert require_validation_production_reservation_registry_proof_contract_document(
        first
    ) == first
    assert first["purpose"]["verifier_only"] is True
    assert first["purpose"]["external_registry_backend_implemented_by_package"] is False
    assert first["purpose"]["actual_global_compare_and_set_proven"] is False
    assert first["purpose"]["authenticated_out_of_band_head_receipt_verified"] is False
    assert first["purpose"]["downstream_raw_proof_reverification_required"] is True
    assert first["purpose"]["epoch_transition_continuity_supported"] is False
    supplied = first["verified_facts_when_external_proof_is_supplied"]
    assert supplied["backend_serializable_transaction_attestation_verified"] is True
    assert supplied["exact_three_slot_state_transition_verified"] is True
    assert supplied["caller_expected_native_head_match_verified"] is True
    assert supplied["observer_signed_native_checkpoint_verified"] is True
    assert supplied["external_serializable_registry_commit_verified"] is False
    assert supplied["permit_one_use_slot_consumed"] is False
    assert first["trust"]["global_latest_status_head_verified"] is False
    decision = validation_production_reservation_registry_proof_decision()
    assert decision["verifier_implemented"] is True
    assert decision["external_registry_transaction_proof_present"] is False
    assert decision["external_serializable_registry_commit_verified"] is False
    assert decision["permit_one_use_slot_consumed"] is False
    assert decision["external_registry_non_equivocation_verified"] is False
    assert decision["production_validation_execution_authorized"] is False


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_external_same_epoch_registry_proof_verifies_both_lanes(
    tmp_path: Path,
    lane: str,
) -> None:
    verified = _verify(_scenario_and_proof(tmp_path, lane))
    assert verified.lane == lane
    assert verified.sequence_five_commit_reverified is True
    assert verified.backend_serializable_transaction_attestation_verified is True
    assert verified.exact_three_slot_state_transition_verified is True
    assert verified.caller_expected_native_head_match_verified is True
    assert verified.observer_signed_native_checkpoint_verified is True
    assert verified.external_serializable_registry_commit_verified is False
    assert verified.registry_head_compare_and_set_committed is False
    assert verified.permit_one_use_slot_consumed is False
    assert verified.authorization_nonce_slot_consumed is False
    assert verified.predecessor_successor_slot_consumed is False
    assert verified.status_head_compare_and_set_committed is False
    assert verified.custody_successor_uniqueness_enforced is False
    assert verified.external_registry_non_equivocation_verified is False
    assert verified.registry_epoch_transition_continuity_verified is False
    assert verified.production_validation_execution_authorized is False
    assert verified.production_validation_results_collected is False
    assert verified.scientifically_validated is False
    assert verified.claim_safe is False


def test_one_pinned_head_rejects_same_prior_head_sibling(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    sibling_root = tmp_path / "sibling"
    first_root.mkdir()
    sibling_root.mkdir()
    first_scenario = _scenario_with_reservation(first_root, "energy_force")
    first_intent, first_raw_intent = _build_intent(first_scenario)
    first_commit, first_raw_commit = _build_commit(
        first_scenario,
        first_intent,
        first_raw_intent,
    )
    first = _proof(
        first_scenario,
        first_intent,
        first_raw_intent,
        first_commit,
        first_raw_commit,
    )
    first_verified = _verify(first)

    sibling_scenario = _scenario_with_reservation(sibling_root, "energy_force")
    sibling_nonce = "39" * 32
    sibling_intent, sibling_raw_intent = _build_intent(
        sibling_scenario,
        external_launch_nonce_sha256=sibling_nonce,
    )
    sibling_commit, sibling_raw_commit = _build_commit(
        sibling_scenario,
        sibling_intent,
        sibling_raw_intent,
        expected_external_launch_nonce_sha256=sibling_nonce,
    )
    sibling = _proof(
        sibling_scenario,
        sibling_intent,
        sibling_raw_intent,
        sibling_commit,
        sibling_raw_commit,
    )
    assert sibling["native_checkpoint"] != first["native_checkpoint"]
    sibling_verified = _verify(sibling)
    for verified in (first_verified, sibling_verified):
        assert verified.external_serializable_registry_commit_verified is False
        assert verified.registry_head_compare_and_set_committed is False
        assert verified.permit_one_use_slot_consumed is False
        assert verified.external_registry_non_equivocation_verified is False
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="caller-expected checkpoint",
    ):
        _verify(
            sibling,
            expected_caller_native_registry_checkpoint_sha256=first[
                "native_checkpoint"
            ],
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("reorder", "reordered or cross-wired"),
        ("sibling_path", "not proven absent"),
        ("after_root", "does not produce its adjacent state root"),
        ("transaction", "not consumed by the sequence-five transaction"),
    ],
)
def test_slot_transition_tamper_fails_before_signature_trust(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "minimization")
    document = deepcopy(bundle["document"])
    rows = document["slot_transition_proofs"]
    assert isinstance(rows, list)
    if mutation == "reorder":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "sibling_path":
        rows[0]["sibling_sha256s"][0] = "0" * 64
    elif mutation == "after_root":
        rows[0]["state_root_after_sha256"] = "0" * 64
    else:
        rows[0]["consumed_by_registry_transaction_sha256"] = "0" * 64
    signed, raw = _resign(document)
    tampered = {
        **bundle,
        "document": signed,
        "raw": raw,
    }
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match=message,
    ):
        _verify(tampered)


def test_unrelated_leaf_is_retained_and_unrelated_mid_transition_add_is_rejected(
    tmp_path: Path,
) -> None:
    scenario = _scenario_with_reservation(tmp_path, "energy_force")
    intent, raw_intent = _build_intent(scenario)
    commit, raw_commit = _build_commit(scenario, intent, raw_intent)
    unrelated_slot = "ab" * 32
    unrelated_leaf = "cd" * 32
    retained = _proof(
        scenario,
        intent,
        raw_intent,
        commit,
        raw_commit,
        initial_leaves={unrelated_slot: unrelated_leaf},
    )
    assert _verify(retained).exact_three_slot_state_transition_verified is True

    document = deepcopy(retained["document"])
    rows = document["slot_transition_proofs"]
    assert isinstance(rows, list)
    target_slot = rows[0]["slot_sha256"]
    transaction = document["registry_transaction_sha256"]
    assert isinstance(target_slot, str)
    assert isinstance(transaction, str)
    malicious_slot = "ac" * 32
    malicious_root, _ = _sparse_state(
        {
            unrelated_slot: unrelated_leaf,
            malicious_slot: "ce" * 32,
            target_slot: production_reservation_sparse_merkle_consumed_leaf_sha256(
                slot_sha256=target_slot,
                registry_transaction_sha256=transaction,
            ),
        }
    )
    rows[0]["state_root_after_sha256"] = malicious_root
    rows[1]["state_root_before_sha256"] = malicious_root
    signed, raw = _resign(document)
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="does not produce its adjacent state root",
    ):
        _verify({**retained, "document": signed, "raw": raw})


def test_fixed_order_proof_handles_target_slots_with_shared_prefix(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "minimization")
    document = bundle["document"]
    assert isinstance(document, dict)
    rows = document["slot_transition_proofs"]
    assert isinstance(rows, list)
    bit_strings = [bin(int(row["slot_sha256"], 16))[2:].zfill(256) for row in rows]
    assert any(
        left[0] == right[0]
        for index, left in enumerate(bit_strings)
        for right in bit_strings[index + 1 :]
    )
    assert _verify(bundle).exact_three_slot_state_transition_verified is True


def test_backend_observer_alias_and_signature_tamper_fail_closed(tmp_path: Path) -> None:
    bundle = _scenario_and_proof(tmp_path, "energy_force")
    alias_observer = ProductionReservationRegistryHeadObserverTrustAnchor(
        OBSERVER_IDENTITY_SHA256,
        REGISTRY_REALM_IDENTITY_SHA256,
        REGISTRY_EPOCH,
        OBSERVER_DEPLOYMENT_SHA256,
        TRUST_VALID_FROM,
        TRUST_VALID_UNTIL,
        ed25519_public_key_bytes(BACKEND_PRIVATE_KEY),
    )
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="trust roles alias",
    ):
        _verify(
            bundle,
            trusted_registry_head_observer_keys={OBSERVER_KEY_ID: alias_observer},
        )

    document = deepcopy(bundle["document"])
    document["head_observer_signature"]["value"] = "0" * 128
    raw = _canonical(document)
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="signature verification failed",
    ):
        _verify(
            {**bundle, "document": document, "raw": raw},
        )


def test_external_backend_key_id_cannot_alias_a_sequence_five_role(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "energy_force")
    document = deepcopy(bundle["document"])
    document["backend_key_id"] = REGISTRY_AUTHORITY_KEY_ID
    signed, raw = _resign(
        document,
        backend_key_id=REGISTRY_AUTHORITY_KEY_ID,
    )
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="sequence-five trust roles alias",
    ):
        _verify(
            {**bundle, "document": signed, "raw": raw},
            trusted_registry_backend_keys={
                REGISTRY_AUTHORITY_KEY_ID: _backend_anchor()
            },
        )


@pytest.mark.parametrize(
    ("key_id", "role"),
    [
        (BACKEND_KEY_ID, "external_registry_backend"),
        (OBSERVER_KEY_ID, "external_registry_head_observer"),
    ],
)
def test_current_status_revoked_external_signer_is_rejected(
    tmp_path: Path,
    key_id: str,
    role: str,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "minimization")
    revoked = _with_current_status(
        bundle,
        revoked_key_rows=(
            {
                "role": role,
                "key_id": key_id,
                "revoked_at_utc": _utc(OBSERVED_AT),
                "reason_code": "compromised",
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="currently revoked",
    ):
        _verify(revoked)


@pytest.mark.parametrize("identity_name", ["proof", "native_checkpoint"])
def test_current_status_revoked_external_proof_identity_is_rejected(
    tmp_path: Path,
    identity_name: str,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "energy_force")
    document = bundle["document"]
    assert isinstance(document, dict)
    identity = (
        document["proof_sha256"]
        if identity_name == "proof"
        else bundle["native_checkpoint"]
    )
    assert isinstance(identity, str)
    revoked = _with_current_status(
        bundle,
        revoked_artifact_rows=(
            {
                "artifact_kind": f"external_registry_{identity_name}",
                "artifact_sha256": identity,
                "revoked_at_utc": _utc(OBSERVED_AT),
                "reason_code": "compromised",
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="currently revoked or superseded",
    ):
        _verify(revoked)


def test_supplied_status_lineage_tail_supersession_is_applied(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "energy_force")
    document = bundle["document"]
    assert isinstance(document, dict)
    proof_sha256 = document["proof_sha256"]
    assert isinstance(proof_sha256, str)
    superseded = _with_current_status(
        bundle,
        supersession_rows=(
            {
                "artifact_kind": "external_registry_proof",
                "superseded_sha256": proof_sha256,
                "replacement_sha256": "af" * 32,
                "superseded_at_utc": _utc(OBSERVED_AT),
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="currently revoked or superseded",
    ):
        _verify(superseded)


def test_same_denial_digest_under_distinct_artifact_kinds_is_not_misread_as_duplicate(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "minimization")
    unrelated = "b7" * 32
    supplied = _with_current_status(
        bundle,
        revoked_artifact_rows=(
            {
                "artifact_kind": "unrelated_kind_a",
                "artifact_sha256": unrelated,
                "revoked_at_utc": _utc(OBSERVED_AT),
                "reason_code": "retired",
            },
            {
                "artifact_kind": "unrelated_kind_b",
                "artifact_sha256": unrelated,
                "revoked_at_utc": _utc(OBSERVED_AT),
                "reason_code": "retired",
            },
        ),
    )
    assert _verify(supplied).observer_signed_native_checkpoint_verified is True


def test_signed_actual_compare_and_set_claim_promotion_is_rejected(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "energy_force")
    document = deepcopy(bundle["document"])
    document["external_serializable_registry_commit_verified"] = True
    document["registry_head_compare_and_set_committed"] = True
    document["permit_one_use_slot_consumed"] = True
    signed, raw = _resign(document)
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="fields are omitted or transplanted",
    ):
        _verify({**bundle, "document": signed, "raw": raw})


def test_raw_identity_seq5_reverification_and_freshness_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "minimization")
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="raw reservation registry proof identity is cross-wired",
    ):
        _verify(bundle, expected_raw_proof_sha256="0" * 64)

    seq5 = dict(bundle["seq5_arguments"])
    seq5["expected_commit_sha256"] = "0" * 64
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="sequence-five reservation commit reverification failed",
    ):
        _verify(bundle, sequence_five_reverification_arguments=seq5)

    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="head observation is stale",
    ):
        _verify(
            bundle,
            checked_at=(
                OBSERVED_AT
                + PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_AGE
                + timedelta(seconds=1)
            ),
        )


def test_causal_time_current_status_and_backend_validity_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "minimization")

    stale_status_document = deepcopy(bundle["document"])
    stale_status_document["observed_at_utc"] = _utc(
        OBSERVED_AT + timedelta(minutes=1)
    )
    stale_signed, stale_raw = _resign(stale_status_document)
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="supplied status lineage tail predates",
    ):
        _verify({**bundle, "document": stale_signed, "raw": stale_raw})

    backdated_document = deepcopy(bundle["document"])
    backdated_document["proof_issued_at_utc"] = _utc(
        COMMITTED_AT - timedelta(seconds=1)
    )
    backdated_signed, backdated_raw = _resign(backdated_document)
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="invalid causal time",
    ):
        _verify({**bundle, "document": backdated_signed, "raw": backdated_raw})

    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="not valid across commit, proof issuance, and check",
    ):
        _verify(
            bundle,
            trusted_registry_backend_keys={
                BACKEND_KEY_ID: _backend_anchor(
                    valid_until_utc=_utc(OBSERVED_AT + timedelta(minutes=1))
                )
            },
        )

    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="not valid across observation and check",
    ):
        _verify(
            bundle,
            trusted_registry_head_observer_keys={
                OBSERVER_KEY_ID: _observer_anchor(
                    valid_until_utc=_utc(OBSERVED_AT + timedelta(minutes=1))
                )
            },
        )


def test_contract_rejects_bool_alias_and_module_has_no_builder_or_signer() -> None:
    contract = validation_production_reservation_registry_proof_contract_document()
    contract["sparse_merkle"]["depth"] = True
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="does not match",
    ):
        require_validation_production_reservation_registry_proof_contract_document(
            contract
        )

    import betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof as module

    public = set(module.__all__)
    assert not any(name.startswith("build_") for name in public)
    assert not any(name.startswith("sign_") for name in public)
    assert not any("private" in name.lower() for name in public)
    assert EXTERNAL_LAUNCH_NONCE_SHA256 != "0" * 64


def test_supplied_status_tail_uses_the_upstream_sequence_five_transport_bound() -> None:
    import betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof as module

    raw = _canonical({"padding": "x" * PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES})
    assert PRODUCTION_RESERVATION_REGISTRY_PROOF_MAX_BYTES < len(raw)
    assert len(raw) < PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES
    with pytest.raises(
        ValidationProductionReservationRegistryProofError,
        match="reservation registry proof exceeds its transport bound",
    ):
        module._load_canonical_document(raw)
    _raw, loaded = module._load_canonical_document(
        raw,
        maximum_bytes=PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
        artifact_name="supplied status lineage tail",
    )
    assert loaded["padding"].startswith("x")
