from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)
import betelgeuze_engine_v2.physics.validation_production_reservation_epoch_transition_continuity as module
from betelgeuze_engine_v2.physics.validation_production_reservation_epoch_transition_continuity import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256,
    PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SCHEMA_ID,
    PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE,
    PRODUCTION_RESERVATION_EPOCH_TRANSITION_POLICY_SCHEMA_ID,
    PRODUCTION_RESERVATION_EPOCH_TRANSITION_PROOF_SCHEMA_ID,
    PRODUCTION_RESERVATION_EPOCH_TRANSITION_VOTE_SCHEMA_ID,
    ProductionReservationEpochTransitionVerification,
    ValidationProductionReservationEpochTransitionError,
    require_validation_production_reservation_epoch_transition_contract_document,
    validation_production_reservation_epoch_transition_contract_document,
    validation_production_reservation_epoch_transition_decision,
    verify_external_production_reservation_epoch_transition_proof,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_witness_quorum_non_equivocation import (
    ProductionReservationNonEquivocationWitnessTrustAnchor,
)
from tests.unit.test_engine_v2_validation_production_reservation_authenticated_head_receipt import (
    CHECKED_AT,
    CURRENT_STATUS_ISSUED_AT,
)
from tests.unit.test_engine_v2_validation_production_reservation_custody_extension import (
    REGISTRY_EPOCH,
    REGISTRY_REALM_IDENTITY_SHA256,
)
from tests.unit.test_engine_v2_validation_production_reservation_witness_quorum_non_equivocation import (
    PROOF_EXPIRES_AT as PREVIOUS_PROOF_EXPIRES_AT,
    _proof_bundle as _previous_proof_bundle,
    _verify as _verify_previous,
)


PREVIOUS_EPOCH_ORDINAL = 27
NEXT_EPOCH_ORDINAL = 28
NEXT_REGISTRY_EPOCH = "external-registry-epoch-2026-08"
TRANSITION_NONCE_SHA256 = hashlib.sha256(
    b"engine-v2-adjacent-epoch-transition-nonce"
).hexdigest()
VOTE_OBSERVED_BASE = CURRENT_STATUS_ISSUED_AT + timedelta(seconds=1)
PROOF_ISSUED_AT = CURRENT_STATUS_ISSUED_AT + timedelta(seconds=8)
PROOF_OBSERVED_AT = PROOF_ISSUED_AT + timedelta(seconds=1)
PROOF_EXPIRES_AT = CHECKED_AT + timedelta(minutes=2)
VOTE_EXPIRES_AT = PREVIOUS_PROOF_EXPIRES_AT
POLICY_VALID_FROM = CHECKED_AT - timedelta(minutes=10)
POLICY_VALID_UNTIL = CHECKED_AT + timedelta(minutes=10)
TRUST_VALID_FROM = CHECKED_AT - timedelta(hours=1)
TRUST_VALID_UNTIL = CHECKED_AT + timedelta(hours=1)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(*parts: object) -> str:
    return _sha256(list(parts))


def _utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_witness_material(
    *,
    member_count: int = 4,
    registry_realm_identity_sha256: str = REGISTRY_REALM_IDENTITY_SHA256,
    registry_epoch: str = NEXT_REGISTRY_EPOCH,
    valid_from: datetime = TRUST_VALID_FROM,
    valid_until: datetime = TRUST_VALID_UNTIL,
) -> tuple[
    dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor],
    dict[str, bytes],
]:
    trust: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor] = {}
    private_keys: dict[str, bytes] = {}
    for index in range(member_count):
        key_id = f"next-epoch-witness-{index:02d}"
        private_key = bytes([0x71 + index]) * 32
        trust[key_id] = ProductionReservationNonEquivocationWitnessTrustAnchor(
            witness_identity_sha256=_digest("next-witness", index),
            operator_identity_sha256=_digest("next-operator", index),
            fault_domain_identity_sha256=_digest("next-fault-domain", index),
            registry_realm_identity_sha256=registry_realm_identity_sha256,
            registry_epoch=registry_epoch,
            service_binary_sha256=_digest("next-binary", index),
            service_schema_sha256=_digest("next-schema", index),
            service_configuration_sha256=_digest("next-configuration", index),
            service_deployment_sha256=_digest("next-deployment", index),
            valid_from_utc=_utc(valid_from),
            valid_until_utc=_utc(valid_until),
            verification_key=ed25519_public_key_bytes(private_key),
        )
        private_keys[key_id] = private_key
    return trust, private_keys


def _previous_arguments(bundle: dict[str, object]) -> dict[str, object]:
    document = bundle["document"]
    raw = bundle["raw"]
    assert isinstance(document, dict)
    assert isinstance(raw, bytes)
    return {
        "source": raw,
        "later_head_consistency_reverification_arguments": bundle["later_arguments"],
        "expected_proof_sha256": document["proof_sha256"],
        "expected_raw_proof_sha256": _raw_sha256(raw),
        "expected_witness_quorum_policy_sha256": bundle["policy_sha256"],
        "trusted_non_equivocation_witness_keys": bundle["trust"],
    }


def _vote_rows(
    *,
    vote_side: str,
    trust: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor],
    private_keys: dict[str, bytes],
    signer_count: int,
    policy_sha256: str,
    member_set_sha256: str,
    statement: dict[str, object],
    previous: object,
    observed_offset: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for vote_index, (key_id, anchor) in enumerate(
        list(trust.items())[:signer_count]
    ):
        observed = VOTE_OBSERVED_BASE + timedelta(
            seconds=observed_offset + vote_index
        )
        row: dict[str, object] = {
            "schema_id": PRODUCTION_RESERVATION_EPOCH_TRANSITION_VOTE_SCHEMA_ID,
            "vote_side": vote_side,
            "vote_index": vote_index,
            "policy_member_index": vote_index,
            "signing_witness_policy_sha256": policy_sha256,
            "signing_member_set_sha256": member_set_sha256,
            "transition_statement_sha256": statement[
                "transition_statement_sha256"
            ],
            "transition_nonce_sha256": statement["transition_nonce_sha256"],
            "lane": previous.lane,
            "registry_realm_identity_sha256": (
                previous.registry_realm_identity_sha256
            ),
            "previous_registry_epoch": previous.registry_epoch,
            "previous_registry_epoch_ordinal": statement[
                "previous_registry_epoch_ordinal"
            ],
            "previous_terminal_registry_sequence": (
                previous.later_registry_sequence
            ),
            "previous_terminal_native_registry_checkpoint_sha256": (
                previous.later_native_registry_checkpoint_sha256
            ),
            "previous_terminal_registry_state_root_sha256": (
                previous.later_registry_state_root_sha256
            ),
            "next_registry_epoch": statement["next_registry_epoch"],
            "next_registry_epoch_ordinal": statement[
                "next_registry_epoch_ordinal"
            ],
            "next_genesis_registry_sequence": (
                PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE
            ),
            "next_genesis_native_registry_checkpoint_sha256": statement[
                "next_genesis_native_registry_checkpoint_sha256"
            ],
            "next_genesis_registry_state_root_sha256": (
                previous.later_registry_state_root_sha256
            ),
            "witness_key_id": key_id,
            "witness_identity_sha256": anchor.witness_identity_sha256,
            "operator_identity_sha256": anchor.operator_identity_sha256,
            "fault_domain_identity_sha256": anchor.fault_domain_identity_sha256,
            "witness_public_key_sha256": _raw_sha256(anchor.verification_key),
            "witness_service_binary_sha256": anchor.service_binary_sha256,
            "witness_service_schema_sha256": anchor.service_schema_sha256,
            "witness_service_configuration_sha256": (
                anchor.service_configuration_sha256
            ),
            "witness_service_deployment_sha256": anchor.service_deployment_sha256,
            "witness_log_sequence": 200 + observed_offset + vote_index,
            "witness_log_checkpoint_sha256": _digest(
                "epoch-transition-vote-log",
                vote_side,
                key_id,
                statement["transition_statement_sha256"],
            ),
            "witness_observed_at_utc": _utc(observed),
            "expires_at_utc": _utc(VOTE_EXPIRES_AT),
            "exclusive_vote_scope": "registry_realm_adjacent_epoch_transition",
            "exclusive_vote_protocol": (
                "one_successor_epoch_per_terminal_epoch_head"
            ),
            "terminal_and_genesis_observed": True,
            "no_conflicting_successor_attested": True,
            "vote_outcome": (
                "conditional_exact_adjacent_epoch_transition_vote_recorded"
            ),
        }
        vote_sha256 = _sha256(row)
        payload = {**row, "vote_sha256": vote_sha256}
        rows.append(
            {
                **payload,
                "witness_signature": {
                    "algorithm": "Ed25519",
                    "key_id": key_id,
                    "value": sign_ed25519(
                        _canonical(payload),
                        private_keys[key_id],
                    ),
                },
            }
        )
    return rows


def _proof_bundle(
    tmp_path: Path,
    lane: str,
    *,
    previous_signer_count: int = 3,
    next_signer_count: int = 3,
    next_threshold: int = 3,
    next_maximum_faulty: int = 1,
    next_epoch: str = NEXT_REGISTRY_EPOCH,
    next_ordinal: int = NEXT_EPOCH_ORDINAL,
    transition_nonce_sha256: str = TRANSITION_NONCE_SHA256,
    next_realm: str = REGISTRY_REALM_IDENTITY_SHA256,
) -> dict[str, object]:
    previous_bundle = _previous_proof_bundle(tmp_path, lane)
    previous = _verify_previous(previous_bundle)
    previous_arguments = _previous_arguments(previous_bundle)
    previous_trust = previous_bundle["trust"]
    assert isinstance(previous_trust, dict)
    previous_private_keys = previous_bundle["private_keys"]
    assert isinstance(previous_private_keys, dict)
    next_trust, next_private_keys = _next_witness_material(
        registry_realm_identity_sha256=next_realm,
        registry_epoch=next_epoch,
    )
    next_member_rows = [
        module._transition_policy_member_row(
            member_index=index,
            key_id=key_id,
            anchor=anchor,
            registry_epoch_ordinal=next_ordinal,
        )
        for index, (key_id, anchor) in enumerate(next_trust.items())
    ]
    next_member_set_sha256 = _sha256(next_member_rows)
    intersection = 2 * next_threshold - len(next_trust)
    next_policy_projection: dict[str, object] = {
        "schema_id": PRODUCTION_RESERVATION_EPOCH_TRANSITION_POLICY_SCHEMA_ID,
        "policy_id": "s0-adjacent-epoch-transition-policy-2026-08",
        "registry_realm_identity_sha256": next_realm,
        "registry_epoch": next_epoch,
        "registry_epoch_ordinal": next_ordinal,
        "member_count": len(next_trust),
        "member_set_sha256": next_member_set_sha256,
        "quorum_threshold": next_threshold,
        "maximum_faulty_witness_count": next_maximum_faulty,
        "minimum_quorum_intersection_count": intersection,
        "minimum_honest_quorum_intersection_count": (
            intersection - next_maximum_faulty
        ),
        "member_rows": next_member_rows,
        "exclusive_vote_scope": "registry_realm_adjacent_epoch_transition",
        "exclusive_vote_protocol": (
            "one_successor_epoch_per_terminal_epoch_head"
        ),
        "fault_assumption": (
            "at_most_f_independent_failure_domains_may_equivocate"
        ),
        "quorum_rule": "two_quorums_intersect_above_fault_bound",
        "valid_from_utc": _utc(POLICY_VALID_FROM),
        "valid_until_utc": _utc(POLICY_VALID_UNTIL),
    }
    next_policy_sha256 = _sha256(next_policy_projection)
    next_policy = {
        **next_policy_projection,
        "policy_sha256": next_policy_sha256,
    }
    previous_member_rows = [
        module.witness_quorum._policy_member_row(
            member_index=index,
            key_id=key_id,
            anchor=anchor,
        )
        for index, (key_id, anchor) in enumerate(previous_trust.items())
    ]
    previous_member_set_sha256 = _sha256(previous_member_rows)
    genesis_projection = module._genesis_projection(
        previous=previous,
        previous_epoch_ordinal=PREVIOUS_EPOCH_ORDINAL,
        next_epoch=next_epoch,
        next_epoch_ordinal=next_ordinal,
        transition_nonce_sha256=transition_nonce_sha256,
        previous_policy_sha256=previous.witness_quorum_policy_sha256,
        previous_member_set_sha256=previous_member_set_sha256,
        next_policy_sha256=next_policy_sha256,
        next_member_set_sha256=next_member_set_sha256,
    )
    next_genesis_checkpoint_sha256 = _sha256(genesis_projection)
    statement = module._transition_statement(
        previous=previous,
        previous_epoch_ordinal=PREVIOUS_EPOCH_ORDINAL,
        next_epoch=next_epoch,
        next_epoch_ordinal=next_ordinal,
        transition_nonce_sha256=transition_nonce_sha256,
        previous_policy_sha256=previous.witness_quorum_policy_sha256,
        previous_member_set_sha256=previous_member_set_sha256,
        next_policy_sha256=next_policy_sha256,
        next_member_set_sha256=next_member_set_sha256,
        next_genesis_checkpoint_sha256=next_genesis_checkpoint_sha256,
    )
    previous_votes = _vote_rows(
        vote_side="previous_epoch_terminal",
        trust=previous_trust,
        private_keys=previous_private_keys,
        signer_count=previous_signer_count,
        policy_sha256=previous.witness_quorum_policy_sha256,
        member_set_sha256=previous_member_set_sha256,
        statement=statement,
        previous=previous,
        observed_offset=0,
    )
    next_votes = _vote_rows(
        vote_side="next_epoch_genesis",
        trust=next_trust,
        private_keys=next_private_keys,
        signer_count=next_signer_count,
        policy_sha256=next_policy_sha256,
        member_set_sha256=next_member_set_sha256,
        statement=statement,
        previous=previous,
        observed_offset=3,
    )
    previous_signer_rows = [row["witness_key_id"] for row in previous_votes]
    next_signer_rows = [row["witness_key_id"] for row in next_votes]
    projection: dict[str, object] = {
        "schema_id": PRODUCTION_RESERVATION_EPOCH_TRANSITION_PROOF_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
        ),
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_adjacent_registry_epoch_transition_certificate",
        "lane": previous.lane,
        "registry_realm_identity_sha256": previous.registry_realm_identity_sha256,
        "previous_witness_quorum_proof_sha256": previous.proof_sha256,
        "previous_raw_witness_quorum_proof_sha256": previous.raw_proof_sha256,
        "previous_witness_quorum_policy_sha256": (
            previous.witness_quorum_policy_sha256
        ),
        "previous_member_set_sha256": previous_member_set_sha256,
        "previous_member_count": previous.witness_member_count,
        "previous_quorum_threshold": previous.quorum_threshold,
        "previous_maximum_faulty_witness_count": (
            previous.maximum_faulty_witness_count
        ),
        "previous_registry_epoch": previous.registry_epoch,
        "previous_registry_epoch_ordinal": PREVIOUS_EPOCH_ORDINAL,
        "previous_terminal_registry_sequence": previous.later_registry_sequence,
        "previous_terminal_native_registry_checkpoint_sha256": (
            previous.later_native_registry_checkpoint_sha256
        ),
        "previous_terminal_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "next_epoch_transition_policy": next_policy,
        "next_epoch_transition_policy_sha256": next_policy_sha256,
        "next_member_set_sha256": next_member_set_sha256,
        "next_member_count": len(next_trust),
        "next_quorum_threshold": next_threshold,
        "next_maximum_faulty_witness_count": next_maximum_faulty,
        "next_minimum_quorum_intersection_count": intersection,
        "next_minimum_honest_quorum_intersection_count": (
            intersection - next_maximum_faulty
        ),
        "next_registry_epoch": next_epoch,
        "next_registry_epoch_ordinal": next_ordinal,
        "next_genesis_registry_sequence": (
            PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SEQUENCE
        ),
        "next_genesis_native_registry_checkpoint_sha256": (
            next_genesis_checkpoint_sha256
        ),
        "next_genesis_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "transition_nonce_sha256": transition_nonce_sha256,
        "transition_statement": statement,
        "transition_statement_sha256": statement["transition_statement_sha256"],
        "previous_epoch_vote_rows": previous_votes,
        "previous_epoch_vote_set_sha256": _sha256(previous_votes),
        "previous_epoch_signer_key_ids": previous_signer_rows,
        "previous_epoch_signer_set_sha256": _sha256(previous_signer_rows),
        "next_epoch_vote_rows": next_votes,
        "next_epoch_vote_set_sha256": _sha256(next_votes),
        "next_epoch_signer_key_ids": next_signer_rows,
        "next_epoch_signer_set_sha256": _sha256(next_signer_rows),
        "proof_issued_at_utc": _utc(PROOF_ISSUED_AT),
        "proof_observed_at_utc": _utc(PROOF_OBSERVED_AT),
        "expires_at_utc": _utc(PROOF_EXPIRES_AT),
        "certificate_outcome": (
            "conditional_exact_adjacent_epoch_terminal_to_genesis_continuity_verified"
        ),
        **{name: True for name in module._TRUE_FACT_FIELDS},
        **module._FALSE_FACT_POLICY,
        **module._CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }
    proof_sha256 = _sha256(projection)
    document = {**projection, "proof_sha256": proof_sha256}
    raw = _canonical(document)
    return {
        "document": document,
        "raw": raw,
        "previous_bundle": previous_bundle,
        "previous_arguments": previous_arguments,
        "previous": previous,
        "next_trust": next_trust,
        "next_private_keys": next_private_keys,
        "next_policy_sha256": next_policy_sha256,
        "next_genesis_checkpoint_sha256": next_genesis_checkpoint_sha256,
        "transition_statement_sha256": statement["transition_statement_sha256"],
        "next_epoch": next_epoch,
        "next_ordinal": next_ordinal,
        "transition_nonce_sha256": transition_nonce_sha256,
    }


def _finalize(document: dict[str, object]) -> bytes:
    previous_votes = document["previous_epoch_vote_rows"]
    next_votes = document["next_epoch_vote_rows"]
    assert isinstance(previous_votes, list)
    assert isinstance(next_votes, list)
    document["previous_epoch_vote_set_sha256"] = _sha256(previous_votes)
    previous_signers = [row["witness_key_id"] for row in previous_votes]
    document["previous_epoch_signer_key_ids"] = previous_signers
    document["previous_epoch_signer_set_sha256"] = _sha256(previous_signers)
    document["next_epoch_vote_set_sha256"] = _sha256(next_votes)
    next_signers = [row["witness_key_id"] for row in next_votes]
    document["next_epoch_signer_key_ids"] = next_signers
    document["next_epoch_signer_set_sha256"] = _sha256(next_signers)
    projection = {
        key: value for key, value in document.items() if key != "proof_sha256"
    }
    document["proof_sha256"] = _sha256(projection)
    return _canonical(document)


def _resign_vote(
    document: dict[str, object],
    *,
    row_set: str,
    vote_index: int,
    private_key: bytes,
) -> None:
    rows = document[row_set]
    assert isinstance(rows, list)
    signed = rows[vote_index]
    assert isinstance(signed, dict)
    signature = signed["witness_signature"]
    assert isinstance(signature, dict)
    key_id = signature["key_id"]
    row = {
        key: value
        for key, value in signed.items()
        if key not in {"vote_sha256", "witness_signature"}
    }
    vote_sha256 = _sha256(row)
    payload = {**row, "vote_sha256": vote_sha256}
    rows[vote_index] = {
        **payload,
        "witness_signature": {
            "algorithm": "Ed25519",
            "key_id": key_id,
            "value": sign_ed25519(_canonical(payload), private_key),
        },
    }


def _verify(bundle: dict[str, object], **overrides: object):
    document = bundle["document"]
    raw = bundle["raw"]
    previous = bundle["previous"]
    assert isinstance(document, dict)
    assert isinstance(raw, bytes)
    values: dict[str, object] = {
        "source": raw,
        "previous_epoch_witness_quorum_reverification_arguments": bundle[
            "previous_arguments"
        ],
        "expected_proof_sha256": document["proof_sha256"],
        "expected_raw_proof_sha256": _raw_sha256(raw),
        "expected_registry_realm_identity_sha256": (
            previous.registry_realm_identity_sha256
        ),
        "expected_previous_epoch_ordinal": PREVIOUS_EPOCH_ORDINAL,
        "expected_next_registry_epoch": bundle["next_epoch"],
        "expected_next_epoch_ordinal": bundle["next_ordinal"],
        "expected_transition_nonce_sha256": bundle["transition_nonce_sha256"],
        "expected_transition_statement_sha256": bundle[
            "transition_statement_sha256"
        ],
        "expected_next_genesis_native_registry_checkpoint_sha256": bundle[
            "next_genesis_checkpoint_sha256"
        ],
        "expected_next_genesis_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "expected_next_epoch_transition_policy_sha256": bundle[
            "next_policy_sha256"
        ],
        "trusted_next_epoch_witness_keys": bundle["next_trust"],
        "checked_at": CHECKED_AT,
    }
    values.update(overrides)
    return verify_external_production_reservation_epoch_transition_proof(
        **values  # type: ignore[arg-type]
    )


def test_contract_is_frozen_verifier_only_scoped_and_claim_closed() -> None:
    contract = validation_production_reservation_epoch_transition_contract_document()
    assert contract["contract_sha256"] == (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
    )
    assert contract["contract_sha256"] != "0" * 64
    assert (
        require_validation_production_reservation_epoch_transition_contract_document(
            contract
        )
        == contract
    )
    assert contract["purpose"]["transition_successor_uniqueness_supported"] is False
    assert contract["purpose"]["witness_locking_enforced_by_verifier"] is False
    decision = validation_production_reservation_epoch_transition_decision()
    assert decision["registry_epoch_transition_continuity_verified"] is False
    assert decision["external_registry_non_equivocation_verified"] is False
    assert decision["claim_safe"] is False
    assert not any("build" in name or "sign" in name for name in module.__all__)


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_joint_adjacent_transition_reverifies_previous_and_stays_claim_closed(
    tmp_path: Path,
    lane: str,
) -> None:
    verified = _verify(_proof_bundle(tmp_path, lane))
    assert verified.lane == lane
    assert verified.previous_registry_epoch_ordinal == PREVIOUS_EPOCH_ORDINAL
    assert verified.next_registry_epoch_ordinal == NEXT_EPOCH_ORDINAL
    assert verified.next_genesis_registry_sequence == 0
    assert (
        verified.next_genesis_registry_state_root_sha256
        == verified.previous_terminal_registry_state_root_sha256
    )
    assert verified.previous_quorum_signer_count == 3
    assert verified.next_quorum_signer_count == 3
    assert verified.registry_epoch_transition_continuity_verified is True
    assert verified.transition_successor_uniqueness_enforced is False
    assert verified.external_registry_non_equivocation_verified is False
    assert verified.claim_safe is False


def test_genesis_checkpoint_and_transition_statement_match_golden_projection(
    tmp_path: Path,
) -> None:
    bundle = _proof_bundle(tmp_path, "minimization")
    document = bundle["document"]
    previous = bundle["previous"]
    assert isinstance(document, dict)
    next_policy = document["next_epoch_transition_policy"]
    assert isinstance(next_policy, dict)
    genesis_projection = {
        "schema_id": PRODUCTION_RESERVATION_EPOCH_TRANSITION_GENESIS_SCHEMA_ID,
        "epoch_transition_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_EPOCH_TRANSITION_CONTRACT_SHA256
        ),
        "lane": previous.lane,
        "registry_realm_identity_sha256": previous.registry_realm_identity_sha256,
        "previous_registry_epoch": previous.registry_epoch,
        "previous_registry_epoch_ordinal": PREVIOUS_EPOCH_ORDINAL,
        "previous_terminal_registry_sequence": previous.later_registry_sequence,
        "previous_terminal_native_registry_checkpoint_sha256": (
            previous.later_native_registry_checkpoint_sha256
        ),
        "previous_terminal_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "next_registry_epoch": NEXT_REGISTRY_EPOCH,
        "next_registry_epoch_ordinal": NEXT_EPOCH_ORDINAL,
        "next_genesis_registry_sequence": 0,
        "next_genesis_registry_state_root_sha256": (
            previous.later_registry_state_root_sha256
        ),
        "transition_nonce_sha256": TRANSITION_NONCE_SHA256,
        "previous_witness_quorum_policy_sha256": (
            previous.witness_quorum_policy_sha256
        ),
        "previous_member_set_sha256": previous.member_set_sha256,
        "next_witness_transition_policy_sha256": next_policy["policy_sha256"],
        "next_member_set_sha256": next_policy["member_set_sha256"],
        "state_root_carried_forward_unchanged": True,
        "epoch_ordinal_delta": 1,
    }
    assert document["next_genesis_native_registry_checkpoint_sha256"] == _sha256(
        genesis_projection
    )
    assert document["transition_statement_sha256"] == _sha256(
        {
            key: value
            for key, value in document["transition_statement"].items()
            if key != "transition_statement_sha256"
        }
    )


@pytest.mark.parametrize("next_ordinal", [27, 29, 0])
def test_same_skipped_and_rollback_epoch_ordinals_fail_closed(
    tmp_path: Path,
    next_ordinal: int,
) -> None:
    bundle = _proof_bundle(
        tmp_path,
        "energy_force",
        next_ordinal=next_ordinal,
    )
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="exactly adjacent|exact bounded integer",
    ):
        _verify(bundle)


def test_epoch_identity_reuse_realm_transplant_and_state_reset_fail_closed(
    tmp_path: Path,
) -> None:
    reuse_path = tmp_path / "reuse"
    reuse_path.mkdir()
    reuse = _proof_bundle(
        reuse_path,
        "energy_force",
        next_epoch=REGISTRY_EPOCH,
    )
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="reuses",
    ):
        _verify(reuse)

    realm_path = tmp_path / "realm"
    realm_path.mkdir()
    other_realm = _digest("other-registry-realm")
    realm_bundle = _proof_bundle(
        realm_path,
        "minimization",
        next_realm=other_realm,
    )
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="trust scope|realm",
    ):
        _verify(realm_bundle)

    reset_path = tmp_path / "reset"
    reset_path.mkdir()
    reset = _proof_bundle(reset_path, "energy_force")
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="resets or rewrites",
    ):
        _verify(
            reset,
            expected_next_genesis_registry_state_root_sha256=_digest(
                "reset-state-root"
            ),
        )


def test_wrong_derived_genesis_and_transition_pins_fail_closed(tmp_path: Path) -> None:
    bundle = _proof_bundle(tmp_path, "minimization")
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="not derived",
    ):
        _verify(
            bundle,
            expected_next_genesis_native_registry_checkpoint_sha256=_digest(
                "wrong-genesis"
            ),
        )
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="statement identity",
    ):
        _verify(
            bundle,
            expected_transition_statement_sha256=_digest("wrong-statement"),
        )


def test_both_previous_and_next_vote_sets_require_full_threshold(tmp_path: Path) -> None:
    previous_path = tmp_path / "previous-q-minus-one"
    previous_path.mkdir()
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="previous_epoch_terminal vote set",
    ):
        _verify(
            _proof_bundle(
                previous_path,
                "energy_force",
                previous_signer_count=2,
            )
        )
    next_path = tmp_path / "next-q-minus-one"
    next_path.mkdir()
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="next_epoch_genesis vote set",
    ):
        _verify(
            _proof_bundle(
                next_path,
                "minimization",
                next_signer_count=2,
            )
        )


def test_next_policy_pin_and_fault_intersection_fail_closed(tmp_path: Path) -> None:
    pin_path = tmp_path / "policy-pin"
    pin_path.mkdir()
    pinned = _proof_bundle(pin_path, "energy_force")
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="policy identity is cross-wired",
    ):
        _verify(
            pinned,
            expected_next_epoch_transition_policy_sha256="0" * 64,
        )

    intersection_path = tmp_path / "policy-intersection"
    intersection_path.mkdir()
    invalid = _proof_bundle(
        intersection_path,
        "minimization",
        next_threshold=2,
        next_signer_count=3,
    )
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="fault-intersection bound",
    ):
        _verify(invalid)


def test_signed_vote_scope_tamper_signature_tamper_and_reorder_fail_closed(
    tmp_path: Path,
) -> None:
    scope_path = tmp_path / "scope"
    scope_path.mkdir()
    scope_bundle = _proof_bundle(scope_path, "energy_force")
    scope_document = deepcopy(scope_bundle["document"])
    next_votes = scope_document["next_epoch_vote_rows"]
    assert isinstance(next_votes, list)
    next_votes[0]["next_genesis_registry_state_root_sha256"] = _digest(
        "signed-reset"
    )
    private_keys = scope_bundle["next_private_keys"]
    assert isinstance(private_keys, dict)
    _resign_vote(
        scope_document,
        row_set="next_epoch_vote_rows",
        vote_index=0,
        private_key=private_keys["next-epoch-witness-00"],
    )
    scope_raw = _finalize(scope_document)
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="scope is reordered or cross-wired",
    ):
        _verify(
            scope_bundle,
            source=scope_raw,
            expected_proof_sha256=scope_document["proof_sha256"],
            expected_raw_proof_sha256=_raw_sha256(scope_raw),
        )

    signature_path = tmp_path / "signature"
    signature_path.mkdir()
    signature_bundle = _proof_bundle(signature_path, "minimization")
    signature_document = deepcopy(signature_bundle["document"])
    previous_votes = signature_document["previous_epoch_vote_rows"]
    assert isinstance(previous_votes, list)
    signature = previous_votes[0]["witness_signature"]
    assert isinstance(signature, dict)
    signature["value"] = "0" * 128
    signature_raw = _finalize(signature_document)
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="signature verification failed",
    ):
        _verify(
            signature_bundle,
            source=signature_raw,
            expected_proof_sha256=signature_document["proof_sha256"],
            expected_raw_proof_sha256=_raw_sha256(signature_raw),
        )

    reorder_path = tmp_path / "reorder"
    reorder_path.mkdir()
    reorder_bundle = _proof_bundle(reorder_path, "energy_force")
    reorder_document = deepcopy(reorder_bundle["document"])
    reorder_votes = reorder_document["next_epoch_vote_rows"]
    assert isinstance(reorder_votes, list)
    reorder_votes[0], reorder_votes[1] = reorder_votes[1], reorder_votes[0]
    reorder_raw = _finalize(reorder_document)
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="scope is reordered or cross-wired",
    ):
        _verify(
            reorder_bundle,
            source=reorder_raw,
            expected_proof_sha256=reorder_document["proof_sha256"],
            expected_raw_proof_sha256=_raw_sha256(reorder_raw),
        )


def test_signed_vote_numeric_types_and_proof_causal_order_fail_closed(
    tmp_path: Path,
) -> None:
    numeric_path = tmp_path / "numeric"
    numeric_path.mkdir()
    numeric_bundle = _proof_bundle(numeric_path, "energy_force")
    numeric_document = deepcopy(numeric_bundle["document"])
    next_votes = numeric_document["next_epoch_vote_rows"]
    assert isinstance(next_votes, list)
    next_votes[0]["next_genesis_registry_sequence"] = False
    private_keys = numeric_bundle["next_private_keys"]
    assert isinstance(private_keys, dict)
    _resign_vote(
        numeric_document,
        row_set="next_epoch_vote_rows",
        vote_index=0,
        private_key=private_keys["next-epoch-witness-00"],
    )
    numeric_raw = _finalize(numeric_document)
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="exact bounded integer",
    ):
        _verify(
            numeric_bundle,
            source=numeric_raw,
            expected_proof_sha256=numeric_document["proof_sha256"],
            expected_raw_proof_sha256=_raw_sha256(numeric_raw),
        )

    causal_path = tmp_path / "causal"
    causal_path.mkdir()
    causal_bundle = _proof_bundle(causal_path, "minimization")
    causal_document = deepcopy(causal_bundle["document"])
    causal_document["proof_issued_at_utc"] = _utc(VOTE_OBSERVED_BASE)
    causal_raw = _finalize(causal_document)
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="invalid causal time",
    ):
        _verify(
            causal_bundle,
            source=causal_raw,
            expected_proof_sha256=causal_document["proof_sha256"],
            expected_raw_proof_sha256=_raw_sha256(causal_raw),
        )


def test_sibling_vote_transplant_is_rejected_but_uniqueness_is_not_claimed(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first"
    first_path.mkdir()
    first = _proof_bundle(first_path, "minimization")
    second_path = tmp_path / "second"
    second_path.mkdir()
    second = _proof_bundle(
        second_path,
        "minimization",
        transition_nonce_sha256=_digest("sibling-transition"),
    )
    assert _verify(first).transition_successor_uniqueness_enforced is False
    assert _verify(second).transition_successor_uniqueness_enforced is False

    transplanted = deepcopy(first["document"])
    transplanted_rows = transplanted["next_epoch_vote_rows"]
    sibling_rows = second["document"]["next_epoch_vote_rows"]
    assert isinstance(transplanted_rows, list)
    assert isinstance(sibling_rows, list)
    transplanted_rows[0] = deepcopy(sibling_rows[0])
    raw = _finalize(transplanted)
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="scope is reordered or cross-wired",
    ):
        _verify(
            first,
            source=raw,
            expected_proof_sha256=transplanted["proof_sha256"],
            expected_raw_proof_sha256=_raw_sha256(raw),
        )


def test_next_roster_alias_with_previous_roster_fails_closed(tmp_path: Path) -> None:
    bundle = _proof_bundle(tmp_path, "energy_force")
    next_trust = dict(bundle["next_trust"])
    previous_bundle = bundle["previous_bundle"]
    previous_trust = previous_bundle["trust"]
    previous_anchor = previous_trust["external-witness-00"]
    next_anchor = next_trust["next-epoch-witness-00"]
    next_trust["next-epoch-witness-00"] = replace(
        next_anchor,
        operator_identity_sha256=previous_anchor.operator_identity_sha256,
    )
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="overlaps an upstream role",
    ):
        _verify(bundle, trusted_next_epoch_witness_keys=next_trust)


def test_outer_identity_duplicate_json_and_transport_bounds_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = _proof_bundle(tmp_path, "minimization")
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="raw epoch-transition proof identity",
    ):
        _verify(bundle, expected_raw_proof_sha256="0" * 64)
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="logical SHA-256",
    ):
        _verify(bundle, expected_proof_sha256="0" * 64)
    duplicate = bundle["raw"].replace(b"{", b'{"schema_id":"duplicate",', 1)
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="duplicate JSON key",
    ):
        _verify(
            bundle,
            source=duplicate,
            expected_raw_proof_sha256=_raw_sha256(duplicate),
        )
    overlong = b"{" + b" " * module.PRODUCTION_RESERVATION_EPOCH_TRANSITION_MAX_BYTES
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="transport bound",
    ):
        _verify(
            bundle,
            source=overlong,
            expected_raw_proof_sha256=_raw_sha256(overlong),
        )


def test_previous_proof_is_freshly_reverified_and_cannot_be_crosswired(
    tmp_path: Path,
) -> None:
    bundle = _proof_bundle(tmp_path, "energy_force")
    arguments = deepcopy(bundle["previous_arguments"])
    arguments["expected_proof_sha256"] = "0" * 64
    with pytest.raises(
        ValidationProductionReservationEpochTransitionError,
        match="previous epoch witness-quorum proof reverification failed",
    ):
        _verify(
            bundle,
            previous_epoch_witness_quorum_reverification_arguments=arguments,
        )


def test_verification_dto_cannot_be_constructed_or_used_as_authorization() -> None:
    with pytest.raises(TypeError):
        ProductionReservationEpochTransitionVerification(  # type: ignore[call-arg]
            proof_sha256="0" * 64
        )
    assert not hasattr(
        ProductionReservationEpochTransitionVerification,
        "production_authorization_token",
    )
