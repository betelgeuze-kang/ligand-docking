from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ed25519_public_key_bytes,
    sign_ed25519,
)
import betelgeuze_engine_v2.physics.validation_production_reservation_later_head_consistency as module
from betelgeuze_engine_v2.physics.validation_production_reservation_later_head_consistency import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
    PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_PROOF_SCHEMA_ID,
    PRODUCTION_RESERVATION_LATER_HEAD_TRANSITION_SCHEMA_ID,
    ProductionReservationLaterHeadConsistencyVerification,
    ValidationProductionReservationLaterHeadConsistencyError,
    require_validation_production_reservation_later_head_consistency_contract_document,
    validation_production_reservation_later_head_consistency_contract_document,
    validation_production_reservation_later_head_consistency_decision,
    verify_external_production_reservation_later_head_consistency_proof,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_registry_proof import (
    production_reservation_sparse_merkle_consumed_leaf_sha256,
)
from tests.unit.test_engine_v2_validation_production_reservation_authenticated_head_receipt import (
    CHECKED_AT,
    CURRENT_STATUS_ISSUED_AT,
    EXPIRES_AT,
    HEAD_OBSERVED_AT as ANCHOR_HEAD_OBSERVED_AT,
    RECEIPT_ISSUED_AT,
    REQUEST_CHALLENGE_NONCE_SHA256,
    _receipt_bundle,
    _scenario_and_proof,
)
from tests.unit.test_engine_v2_validation_production_reservation_registry_proof import (
    BACKEND_BINARY_SHA256,
    BACKEND_CONFIGURATION_SHA256,
    BACKEND_DEPLOYMENT_SHA256,
    BACKEND_IDENTITY_SHA256,
    BACKEND_KEY_ID,
    BACKEND_PRIVATE_KEY,
    BACKEND_SCHEMA_SHA256,
    OBSERVER_DEPLOYMENT_SHA256,
    OBSERVER_IDENTITY_SHA256,
    OBSERVER_KEY_ID,
    OBSERVER_PRIVATE_KEY,
    _backend_anchor,
    _observer_anchor,
    _sparse_state,
)


PROOF_ISSUED_AT = RECEIPT_ISSUED_AT + timedelta(seconds=12)
HEAD_OBSERVED_AT = PROOF_ISSUED_AT + timedelta(seconds=1)


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


def _utc(value: object) -> str:
    assert hasattr(value, "strftime")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")  # type: ignore[union-attr]


def _head_arguments(receipt: dict[str, object]) -> dict[str, object]:
    document = receipt["document"]
    raw = receipt["raw"]
    assert isinstance(document, dict)
    assert isinstance(raw, bytes)
    return {
        "source": raw,
        "registry_proof_reverification_arguments": receipt["registry_arguments"],
        "current_registry_proof_reverification_arguments": receipt[
            "current_registry_arguments"
        ],
        "expected_head_receipt_sha256": document["head_receipt_sha256"],
        "expected_raw_head_receipt_sha256": _raw_sha256(raw),
        "expected_request_challenge_nonce_sha256": (
            REQUEST_CHALLENGE_NONCE_SHA256
        ),
        "trusted_head_receipt_authority_keys": receipt["trusted_keys"],
    }


def _resign_observer(document: dict[str, object]) -> tuple[dict[str, object], bytes]:
    projection = {
        key: value
        for key, value in document.items()
        if key not in {"proof_sha256", "head_observer_signature"}
    }
    proof_sha256 = _sha256(projection)
    payload = {**projection, "proof_sha256": proof_sha256}
    signed = {
        **payload,
        "head_observer_signature": {
            "algorithm": "Ed25519",
            "key_id": OBSERVER_KEY_ID,
            "value": sign_ed25519(_canonical(payload), OBSERVER_PRIVATE_KEY),
        },
    }
    return signed, _canonical(signed)


def _resign_backend_row(row: dict[str, object]) -> dict[str, object]:
    projection = {
        key: value
        for key, value in row.items()
        if key not in {"transition_sha256", "backend_signature"}
    }
    transition_sha256 = _sha256(projection)
    payload = {**projection, "transition_sha256": transition_sha256}
    return {
        **payload,
        "backend_signature": {
            "algorithm": "Ed25519",
            "key_id": BACKEND_KEY_ID,
            "value": sign_ed25519(_canonical(payload), BACKEND_PRIVATE_KEY),
        },
    }


def _consistency_bundle(
    receipt: dict[str, object],
    *,
    transition_count: int = 1,
    branch: str = "main",
    first_commit_at: datetime | None = None,
    proof_issued_at: datetime = PROOF_ISSUED_AT,
    later_head_observed_at: datetime = HEAD_OBSERVED_AT,
) -> dict[str, object]:
    receipt_document = receipt["document"]
    receipt_raw = receipt["raw"]
    registry_arguments = receipt["registry_arguments"]
    assert isinstance(receipt_document, dict)
    assert isinstance(receipt_raw, bytes)
    assert isinstance(registry_arguments, dict)
    registry_raw = registry_arguments["source"]
    assert isinstance(registry_raw, bytes)
    registry_document = json.loads(registry_raw.decode("ascii"))
    assert isinstance(registry_document, dict)
    slot_rows = registry_document["slot_transition_proofs"]
    assert isinstance(slot_rows, list)
    transaction = registry_document["registry_transaction_sha256"]
    assert isinstance(transaction, str)
    leaves: dict[str, str] = {}
    slots: list[tuple[str, str, str]] = []
    for row in slot_rows:
        assert isinstance(row, dict)
        kind = row["slot_kind"]
        slot = row["slot_sha256"]
        consumed_by = row["consumed_by_registry_transaction_sha256"]
        assert isinstance(kind, str)
        assert isinstance(slot, str)
        assert isinstance(consumed_by, str)
        leaves[slot] = production_reservation_sparse_merkle_consumed_leaf_sha256(
            slot_sha256=slot,
            registry_transaction_sha256=consumed_by,
        )
        slots.append((kind, slot, consumed_by))
    anchor_root, _ = _sparse_state(leaves)
    assert anchor_root == registry_document["committed_registry_state_root_sha256"]

    anchor_link = _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_external_reservation_head_anchor_link/1.0.0",
            "head_receipt_sha256": receipt_document["head_receipt_sha256"],
            "raw_head_receipt_sha256": _raw_sha256(receipt_raw),
            "registry_proof_sha256": receipt_document["registry_proof_sha256"],
            "raw_registry_proof_sha256": receipt_document[
                "raw_registry_proof_sha256"
            ],
            "registry_realm_identity_sha256": receipt_document[
                "registry_realm_identity_sha256"
            ],
            "registry_epoch": receipt_document["registry_epoch"],
            "registry_sequence": receipt_document["registry_sequence"],
            "native_registry_checkpoint_sha256": receipt_document[
                "native_registry_checkpoint_sha256"
            ],
            "registry_state_root_sha256": receipt_document[
                "registry_state_root_sha256"
            ],
        }
    )
    backend_public_sha256 = hashlib.sha256(
        ed25519_public_key_bytes(BACKEND_PRIVATE_KEY)
    ).hexdigest()
    previous_sequence = receipt_document["registry_sequence"]
    previous_checkpoint = receipt_document["native_registry_checkpoint_sha256"]
    previous_root = receipt_document["registry_state_root_sha256"]
    previous_link = anchor_link
    assert isinstance(previous_sequence, int)
    assert isinstance(previous_checkpoint, str)
    assert isinstance(previous_root, str)
    transitions: list[dict[str, object]] = []
    for index in range(transition_count):
        new_slot = _sha256({"branch": branch, "later_slot_index": index})
        leaves[new_slot] = _sha256(
            {"branch": branch, "later_leaf_index": index, "state": "committed"}
        )
        committed_root, _ = _sparse_state(leaves)
        registry_transaction = _sha256(
            {"branch": branch, "later_transaction_index": index}
        )
        committed_sequence = previous_sequence + 1
        committed_checkpoint = _sha256(
            {
                "branch": branch,
                "prior_checkpoint": previous_checkpoint,
                "committed_sequence": committed_sequence,
                "committed_root": committed_root,
                "registry_transaction": registry_transaction,
            }
        )
        row = {
            "schema_id": PRODUCTION_RESERVATION_LATER_HEAD_TRANSITION_SCHEMA_ID,
            "transition_index": index,
            "registry_realm_identity_sha256": receipt_document[
                "registry_realm_identity_sha256"
            ],
            "registry_epoch": receipt_document["registry_epoch"],
            "prior_registry_sequence": previous_sequence,
            "committed_registry_sequence": committed_sequence,
            "prior_native_registry_checkpoint_sha256": previous_checkpoint,
            "committed_native_registry_checkpoint_sha256": committed_checkpoint,
            "prior_registry_state_root_sha256": previous_root,
            "committed_registry_state_root_sha256": committed_root,
            "registry_transaction_sha256": registry_transaction,
            "committed_at_utc": _utc(
                (first_commit_at or RECEIPT_ISSUED_AT + timedelta(seconds=5))
                + timedelta(seconds=index)
            ),
            "previous_transition_sha256": previous_link,
            "backend_identity_sha256": BACKEND_IDENTITY_SHA256,
            "backend_key_id": BACKEND_KEY_ID,
            "backend_public_key_sha256": backend_public_sha256,
            "backend_service_binary_sha256": BACKEND_BINARY_SHA256,
            "backend_service_schema_sha256": BACKEND_SCHEMA_SHA256,
            "backend_service_configuration_sha256": (
                BACKEND_CONFIGURATION_SHA256
            ),
            "backend_service_deployment_sha256": BACKEND_DEPLOYMENT_SHA256,
        }
        transition_sha256 = _sha256(row)
        payload = {**row, "transition_sha256": transition_sha256}
        signed_row = {
            **payload,
            "backend_signature": {
                "algorithm": "Ed25519",
                "key_id": BACKEND_KEY_ID,
                "value": sign_ed25519(_canonical(payload), BACKEND_PRIVATE_KEY),
            },
        }
        transitions.append(signed_row)
        previous_sequence = committed_sequence
        previous_checkpoint = committed_checkpoint
        previous_root = committed_root
        previous_link = transition_sha256

    later_root, paths = _sparse_state(
        leaves, path_slots=tuple(slot for _kind, slot, _tx in slots)
    )
    assert later_root == previous_root
    retention = [
        {
            "slot_kind": kind,
            "slot_sha256": slot,
            "consumed_by_registry_transaction_sha256": consumed_by,
            "sibling_sha256s": paths[slot],
        }
        for kind, slot, consumed_by in slots
    ]
    observer_public_sha256 = hashlib.sha256(
        ed25519_public_key_bytes(OBSERVER_PRIVATE_KEY)
    ).hexdigest()
    projection: dict[str, object] = {
        "schema_id": PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_PROOF_SCHEMA_ID,
        "contract_sha256": FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256,
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_same_epoch_later_head_consistency_proof",
        "lane": receipt_document["lane"],
        "anchor_head_receipt_sha256": receipt_document["head_receipt_sha256"],
        "anchor_raw_head_receipt_sha256": _raw_sha256(receipt_raw),
        "anchor_registry_proof_sha256": receipt_document["registry_proof_sha256"],
        "anchor_raw_registry_proof_sha256": receipt_document[
            "raw_registry_proof_sha256"
        ],
        "anchor_sequence_five_commit_sha256": receipt_document[
            "sequence_five_commit_sha256"
        ],
        "anchor_raw_sequence_five_commit_sha256": receipt_document[
            "raw_sequence_five_commit_sha256"
        ],
        "anchor_registry_transaction_sha256": receipt_document[
            "registry_transaction_sha256"
        ],
        "registry_realm_identity_sha256": receipt_document[
            "registry_realm_identity_sha256"
        ],
        "registry_epoch": receipt_document["registry_epoch"],
        "anchor_registry_sequence": receipt_document["registry_sequence"],
        "anchor_native_registry_checkpoint_sha256": receipt_document[
            "native_registry_checkpoint_sha256"
        ],
        "anchor_registry_state_root_sha256": receipt_document[
            "registry_state_root_sha256"
        ],
        "anchor_status_tail_snapshot_sha256": receipt_document[
            "status_tail_snapshot_sha256"
        ],
        "anchor_raw_status_tail_sha256": receipt_document[
            "raw_status_tail_sha256"
        ],
        "anchor_status_tail_sequence": receipt_document["status_tail_sequence"],
        "anchor_status_tail_external_log_checkpoint_sha256": receipt_document[
            "status_tail_external_log_checkpoint_sha256"
        ],
        "later_registry_sequence": previous_sequence,
        "later_native_registry_checkpoint_sha256": previous_checkpoint,
        "later_registry_state_root_sha256": previous_root,
        "checkpoint_transition_rows": transitions,
        "checkpoint_transition_path_sha256": _sha256(transitions),
        "retained_slot_inclusion_proofs": retention,
        "retained_slot_set_sha256": _sha256(retention),
        "head_observer_identity_sha256": OBSERVER_IDENTITY_SHA256,
        "head_observer_key_id": OBSERVER_KEY_ID,
        "head_observer_public_key_sha256": observer_public_sha256,
        "head_observer_deployment_sha256": OBSERVER_DEPLOYMENT_SHA256,
        "proof_issued_at_utc": _utc(proof_issued_at),
        "later_head_observed_at_utc": _utc(later_head_observed_at),
        "expires_at_utc": _utc(EXPIRES_AT),
        "consistency_outcome": (
            "observer_attested_exact_adjacent_same_epoch_path"
        ),
        "authenticated_head_receipt_reverified": True,
        "adjacent_checkpoint_lineage_verified": True,
        "original_consumed_slots_retained_verified": True,
        "observer_signed_later_head_verified": True,
        "caller_expected_later_head_match_verified": True,
        "later_head_consistency_verified": True,
        **module._ACTUAL_FACT_POLICY,
        **module._CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }
    document, raw = _resign_observer(projection)
    backend_trust = {BACKEND_KEY_ID: _backend_anchor()}
    observer_trust = {OBSERVER_KEY_ID: _observer_anchor()}
    return {
        "document": document,
        "raw": raw,
        "head_arguments": _head_arguments(receipt),
        "backend_trust": backend_trust,
        "observer_trust": observer_trust,
        "later_sequence": previous_sequence,
        "later_checkpoint": previous_checkpoint,
        "later_root": previous_root,
    }


def _verify(bundle: dict[str, object], **overrides: object):
    document = bundle["document"]
    raw = bundle["raw"]
    assert isinstance(document, dict)
    assert isinstance(raw, bytes)
    values: dict[str, object] = {
        "source": raw,
        "authenticated_head_receipt_reverification_arguments": bundle[
            "head_arguments"
        ],
        "expected_proof_sha256": document["proof_sha256"],
        "expected_raw_proof_sha256": _raw_sha256(raw),
        "expected_later_registry_sequence": bundle["later_sequence"],
        "expected_later_native_registry_checkpoint_sha256": bundle[
            "later_checkpoint"
        ],
        "expected_later_registry_state_root_sha256": bundle["later_root"],
        "trusted_registry_backend_keys": bundle["backend_trust"],
        "trusted_registry_head_observer_keys": bundle["observer_trust"],
        "checked_at": CHECKED_AT,
    }
    values.update(overrides)
    return verify_external_production_reservation_later_head_consistency_proof(
        **values  # type: ignore[arg-type]
    )


def test_contract_is_frozen_verifier_only_and_claim_closed() -> None:
    contract = validation_production_reservation_later_head_consistency_contract_document()
    assert contract["contract_sha256"] == (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_CONTRACT_SHA256
    )
    assert require_validation_production_reservation_later_head_consistency_contract_document(
        contract
    ) == contract
    assert contract["purpose"]["same_epoch_adjacent_checkpoint_path_supported"] is True
    assert contract["purpose"]["global_non_equivocation_supported"] is False
    assert contract["purpose"]["epoch_transition_continuity_supported"] is False
    assert contract["consistency_path"]["actual_slot_consumption_inferred"] is False
    assert contract["transport"]["maximum_json_integer_digits"] == 20
    assert (
        contract["trust_and_freshness"][
            "later_head_observed_at_is_observer_countersign_completion_time"
        ]
        is True
    )
    decision = validation_production_reservation_later_head_consistency_decision()
    assert decision["later_head_consistency_verified"] is False
    assert decision["external_registry_non_equivocation_verified"] is False
    assert decision["production_validation_execution_authorized"] is False
    assert not any("build" in name or "sign" in name for name in module.__all__)


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_one_step_path_reverifies_anchor_retains_slots_and_stays_claim_closed(
    tmp_path: Path,
    lane: str,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, lane))
    verified = _verify(_consistency_bundle(receipt))
    assert verified.lane == lane
    assert verified.checkpoint_transition_count == 1
    assert verified.authenticated_head_receipt_reverified is True
    assert verified.adjacent_checkpoint_lineage_verified is True
    assert verified.original_consumed_slots_retained_verified is True
    assert verified.later_head_consistency_verified is True
    for field_name in (
        "caller_challenge_freshness_verified",
        "caller_challenge_one_use_verified",
        "global_latest_registry_head_verified",
        "global_latest_status_head_verified",
        "external_serializable_registry_commit_verified",
        "registry_head_compare_and_set_committed",
        "status_head_compare_and_set_committed",
        "permit_one_use_slot_consumed",
        "authorization_nonce_slot_consumed",
        "predecessor_successor_slot_consumed",
        "custody_successor_uniqueness_enforced",
        "external_registry_non_equivocation_verified",
        "registry_epoch_transition_continuity_verified",
        "production_validation_execution_authorized",
        "production_validation_results_collected",
        "scientifically_validated",
        "parameter_fitting_authorized",
        "product_qualified",
        "claim_safe",
    ):
        assert getattr(verified, field_name) is False


def test_multi_step_path_is_exactly_adjacent(tmp_path: Path) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    verified = _verify(_consistency_bundle(receipt, transition_count=3))
    assert verified.checkpoint_transition_count == 3
    assert verified.later_registry_sequence == verified.anchor_registry_sequence + 3


def test_transition_after_head_observation_before_receipt_issue_is_accepted(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    first_commit = ANCHOR_HEAD_OBSERVED_AT + timedelta(seconds=1)
    assert first_commit < RECEIPT_ISSUED_AT
    verified = _verify(
        _consistency_bundle(receipt, first_commit_at=first_commit)
    )
    assert verified.later_head_consistency_verified is True


def test_proof_issued_before_anchor_receipt_is_rejected(tmp_path: Path) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    first_commit = ANCHOR_HEAD_OBSERVED_AT + timedelta(seconds=1)
    proof_issued = RECEIPT_ISSUED_AT - timedelta(seconds=1)
    assert first_commit < proof_issued < RECEIPT_ISSUED_AT
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="invalid causal time",
    ):
        _verify(
            _consistency_bundle(
                receipt,
                first_commit_at=first_commit,
                proof_issued_at=proof_issued,
                later_head_observed_at=RECEIPT_ISSUED_AT,
            )
        )


@pytest.mark.parametrize("mutation", ["reorder", "gap", "backend_signature"])
def test_path_reorder_gap_and_signature_tamper_fail_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "minimization"))
    bundle = _consistency_bundle(receipt, transition_count=2)
    document = deepcopy(bundle["document"])
    rows = document["checkpoint_transition_rows"]
    assert isinstance(rows, list)
    if mutation == "reorder":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "gap":
        rows[1]["prior_registry_sequence"] += 1
    else:
        rows[0]["backend_signature"]["value"] = "0" * 128
    signed, raw = _resign_observer(document)
    with pytest.raises(ValidationProductionReservationLaterHeadConsistencyError):
        _verify({**bundle, "document": signed, "raw": raw})


def test_direct_observer_signature_tamper_fails_closed(tmp_path: Path) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    bundle = _consistency_bundle(receipt)
    document = deepcopy(bundle["document"])
    signature = document["head_observer_signature"]
    assert isinstance(signature, dict)
    signature["value"] = "0" * 128
    raw = _canonical(document)
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="observer signature verification failed",
    ):
        _verify({**bundle, "document": document, "raw": raw})


@pytest.mark.parametrize(
    "mutation",
    ["realm", "epoch", "prior_checkpoint", "prior_root", "previous_link"],
)
def test_adjacency_identity_and_link_mutations_fail_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "minimization"))
    bundle = _consistency_bundle(receipt, transition_count=2)
    document = deepcopy(bundle["document"])
    rows = document["checkpoint_transition_rows"]
    assert isinstance(rows, list)
    if mutation == "realm":
        rows[0]["registry_realm_identity_sha256"] = "0" * 64
    elif mutation == "epoch":
        rows[0]["registry_epoch"] = "other-epoch"
    elif mutation == "prior_checkpoint":
        rows[1]["prior_native_registry_checkpoint_sha256"] = "0" * 64
    elif mutation == "prior_root":
        rows[1]["prior_registry_state_root_sha256"] = "0" * 64
    else:
        rows[1]["previous_transition_sha256"] = "0" * 64
    signed, raw = _resign_observer(document)
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="reordered, gapped, or cross-wired",
    ):
        _verify({**bundle, "document": signed, "raw": raw})


def test_duplicate_transaction_with_valid_backend_signature_fails_closed(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    bundle = _consistency_bundle(receipt, transition_count=2)
    document = deepcopy(bundle["document"])
    rows = document["checkpoint_transition_rows"]
    assert isinstance(rows, list)
    rows[1]["registry_transaction_sha256"] = rows[0][
        "registry_transaction_sha256"
    ]
    rows[1] = _resign_backend_row(rows[1])
    document["checkpoint_transition_path_sha256"] = _sha256(rows)
    signed, raw = _resign_observer(document)
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="duplicate transaction or link",
    ):
        _verify({**bundle, "document": signed, "raw": raw})


def test_later_slot_retention_path_tamper_is_rejected(tmp_path: Path) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    bundle = _consistency_bundle(receipt)
    document = deepcopy(bundle["document"])
    rows = document["retained_slot_inclusion_proofs"]
    assert isinstance(rows, list)
    rows[0]["sibling_sha256s"][0] = "0" * 64
    document["retained_slot_set_sha256"] = _sha256(rows)
    signed, raw = _resign_observer(document)
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="not retained",
    ):
        _verify({**bundle, "document": signed, "raw": raw})


@pytest.mark.parametrize("mutation", ["missing", "reorder", "slot", "transaction"])
def test_slot_retention_structure_mutations_fail_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    bundle = _consistency_bundle(receipt)
    document = deepcopy(bundle["document"])
    rows = document["retained_slot_inclusion_proofs"]
    assert isinstance(rows, list)
    if mutation == "missing":
        rows.pop()
    elif mutation == "reorder":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "slot":
        rows[0]["slot_sha256"] = "0" * 64
    else:
        rows[0]["consumed_by_registry_transaction_sha256"] = "0" * 64
    document["retained_slot_set_sha256"] = _sha256(rows)
    signed, raw = _resign_observer(document)
    with pytest.raises(ValidationProductionReservationLaterHeadConsistencyError):
        _verify({**bundle, "document": signed, "raw": raw})


def test_separately_pinned_sibling_paths_can_verify_but_cross_pin_fails(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "minimization"))
    left = _consistency_bundle(receipt, branch="left")
    right = _consistency_bundle(receipt, branch="right")
    assert _verify(left).external_registry_non_equivocation_verified is False
    assert _verify(right).external_registry_non_equivocation_verified is False
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="caller expectation",
    ):
        _verify(
            right,
            expected_later_native_registry_checkpoint_sha256=left[
                "later_checkpoint"
            ],
        )


def test_trust_substitution_and_caller_head_mismatch_are_rejected(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    bundle = _consistency_bundle(receipt)
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="trust domain differs",
    ):
        _verify(
            bundle,
            trusted_registry_backend_keys={
                BACKEND_KEY_ID: _backend_anchor(valid_until_utc="2026-07-21T00:00:00Z")
            },
        )
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="caller expectation",
    ):
        _verify(bundle, expected_later_registry_state_root_sha256="0" * 64)


def test_caller_sequence_pin_mismatch_is_rejected(tmp_path: Path) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    bundle = _consistency_bundle(receipt)
    sequence = bundle["later_sequence"]
    assert isinstance(sequence, int)
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="caller expectation",
    ):
        _verify(bundle, expected_later_registry_sequence=sequence + 1)
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="must be an exact bounded integer",
    ):
        _verify(bundle, expected_later_registry_sequence=True)


def test_post_consistency_status_can_revoke_exact_proof(tmp_path: Path) -> None:
    scenario = _scenario_and_proof(tmp_path, "minimization")
    initial_receipt = _receipt_bundle(scenario)
    initial = _consistency_bundle(initial_receipt)
    proof_sha256 = initial["document"]["proof_sha256"]
    assert isinstance(proof_sha256, str)
    revoked_receipt = _receipt_bundle(
        scenario,
        current_revoked_artifact_rows=(
            {
                "artifact_kind": "external_later_head_consistency_proof",
                "artifact_sha256": proof_sha256,
                "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                "reason_code": "compromised",
            },
        ),
    )
    revoked = _consistency_bundle(revoked_receipt)
    assert revoked["document"]["proof_sha256"] == proof_sha256
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="revoked or superseded",
    ):
        _verify(revoked)


@pytest.mark.parametrize(
    "identity_name",
    [
        "anchor_link",
        "transition",
        "transaction",
        "checkpoint",
        "root",
        "backend_deployment",
        "observer_deployment",
        "path",
        "retention",
    ],
)
@pytest.mark.parametrize("denial_kind", ["revoked", "superseded"])
def test_post_consistency_status_denies_every_later_path_identity(
    tmp_path: Path,
    identity_name: str,
    denial_kind: str,
) -> None:
    scenario = _scenario_and_proof(tmp_path, "minimization")
    receipt = _receipt_bundle(scenario)
    initial = _consistency_bundle(receipt)
    document = initial["document"]
    assert isinstance(document, dict)
    rows = document["checkpoint_transition_rows"]
    assert isinstance(rows, list)
    transition = rows[0]
    assert isinstance(transition, dict)
    identities = {
        "anchor_link": transition["previous_transition_sha256"],
        "transition": transition["transition_sha256"],
        "transaction": transition["registry_transaction_sha256"],
        "checkpoint": transition["committed_native_registry_checkpoint_sha256"],
        "root": transition["committed_registry_state_root_sha256"],
        "backend_deployment": BACKEND_DEPLOYMENT_SHA256,
        "observer_deployment": OBSERVER_DEPLOYMENT_SHA256,
        "path": document["checkpoint_transition_path_sha256"],
        "retention": document["retained_slot_set_sha256"],
    }
    identity = identities[identity_name]
    assert isinstance(identity, str)
    if denial_kind == "revoked":
        denial_arguments: dict[str, object] = {
            "current_revoked_artifact_rows": (
                {
                    "artifact_kind": f"later_head_{identity_name}",
                    "artifact_sha256": identity,
                    "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                    "reason_code": "compromised",
                },
            )
        }
    else:
        denial_arguments = {
            "current_supersession_rows": (
                {
                    "artifact_kind": f"later_head_{identity_name}",
                    "superseded_sha256": identity,
                    "replacement_sha256": "ab" * 32,
                    "superseded_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                },
            )
        }
    denied_receipt = _receipt_bundle(scenario, **denial_arguments)  # type: ignore[arg-type]
    denied = _consistency_bundle(denied_receipt)
    assert denied["document"] == document
    with pytest.raises(ValidationProductionReservationLaterHeadConsistencyError):
        _verify(denied)


@pytest.mark.parametrize(
    ("role", "key_id"),
    [
        ("external_registry_backend", BACKEND_KEY_ID),
        ("external_registry_head_observer", OBSERVER_KEY_ID),
    ],
)
def test_post_consistency_status_revokes_backend_and_observer_keys(
    tmp_path: Path,
    role: str,
    key_id: str,
) -> None:
    scenario = _scenario_and_proof(tmp_path, "energy_force")
    receipt = _receipt_bundle(
        scenario,
        current_revoked_key_rows=(
            {
                "role": role,
                "key_id": key_id,
                "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                "reason_code": "compromised",
            },
        ),
    )
    with pytest.raises(ValidationProductionReservationLaterHeadConsistencyError):
        _verify(_consistency_bundle(receipt))


def test_post_consistency_status_must_be_strictly_later_than_proof(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(
        _scenario_and_proof(tmp_path, "energy_force"),
        current_status_issued_at=PROOF_ISSUED_AT,
    )
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="invalid causal time",
    ):
        _verify(_consistency_bundle(receipt))


def test_claim_promotion_copy_hook_and_duplicate_json_fail_closed(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "minimization"))
    bundle = _consistency_bundle(receipt)
    document = deepcopy(bundle["document"])
    document["production_validation_execution_authorized"] = True
    signed, raw = _resign_observer(document)
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="omitted or transplanted",
    ):
        _verify({**bundle, "document": signed, "raw": raw})

    class CopyHook:
        called = False

        def __deepcopy__(self, memo: object) -> object:
            del memo
            type(self).called = True
            return self

    head_arguments = dict(bundle["head_arguments"])
    head_arguments["source"] = CopyHook()
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="unsupported value",
    ):
        _verify(
            bundle,
            authenticated_head_receipt_reverification_arguments=head_arguments,
        )
    assert CopyHook.called is False

    valid_raw = bundle["raw"]
    assert isinstance(valid_raw, bytes)
    duplicate = b'{"schema_id":"duplicate",' + valid_raw[1:]
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="duplicate JSON key",
    ):
        _verify(bundle, source=duplicate, expected_raw_proof_sha256=_raw_sha256(duplicate))


def test_integer_digit_and_transport_bounds_fail_before_json_conversion(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    bundle = _consistency_bundle(receipt)
    oversized_integer = b'{"n":' + b"9" * 21 + b"}"
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="not canonical ASCII JSON",
    ):
        _verify(
            bundle,
            source=oversized_integer,
            expected_raw_proof_sha256=_raw_sha256(oversized_integer),
        )

    oversized_transport = (
        b"{" + b" " * module.PRODUCTION_RESERVATION_LATER_HEAD_CONSISTENCY_MAX_BYTES
    )
    with pytest.raises(
        ValidationProductionReservationLaterHeadConsistencyError,
        match="exceeds its transport bound",
    ):
        _verify(
            bundle,
            source=oversized_transport,
            expected_raw_proof_sha256=_raw_sha256(oversized_transport),
        )


def test_verification_dto_cannot_be_forged_directly() -> None:
    with pytest.raises(TypeError):
        ProductionReservationLaterHeadConsistencyVerification(  # type: ignore[call-arg]
            proof_sha256="0" * 64
        )
