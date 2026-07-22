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
import betelgeuze_engine_v2.physics.validation_production_reservation_witness_quorum_non_equivocation as module
from betelgeuze_engine_v2.physics.validation_production_reservation_witness_quorum_non_equivocation import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256,
    PRODUCTION_RESERVATION_WITNESS_QUORUM_POLICY_SCHEMA_ID,
    PRODUCTION_RESERVATION_WITNESS_QUORUM_PROOF_SCHEMA_ID,
    PRODUCTION_RESERVATION_WITNESS_STATEMENT_SCHEMA_ID,
    ProductionReservationNonEquivocationWitnessTrustAnchor,
    ProductionReservationWitnessQuorumVerification,
    ValidationProductionReservationWitnessQuorumError,
    require_validation_production_reservation_witness_quorum_contract_document,
    validation_production_reservation_witness_quorum_contract_document,
    validation_production_reservation_witness_quorum_decision,
    verify_external_production_reservation_witness_quorum_proof,
)
from tests.unit.test_engine_v2_validation_production_reservation_authenticated_head_receipt import (
    CHECKED_AT,
    CURRENT_STATUS_ISSUED_AT,
    RECEIPT_ISSUED_AT,
    _receipt_bundle,
    _scenario_and_proof,
)
from tests.unit.test_engine_v2_validation_production_reservation_later_head_consistency import (
    BACKEND_IDENTITY_SHA256,
    HEAD_OBSERVED_AT,
    _consistency_bundle,
    _verify as _verify_later,
)
from tests.unit.test_engine_v2_validation_production_reservation_custody_extension import (
    REGISTRY_EPOCH,
    REGISTRY_REALM_IDENTITY_SHA256,
)


WITNESS_OBSERVED_BASE = HEAD_OBSERVED_AT + timedelta(seconds=1)
PROOF_ISSUED_AT = HEAD_OBSERVED_AT + timedelta(seconds=4)
PROOF_OBSERVED_AT = PROOF_ISSUED_AT + timedelta(seconds=1)
STATEMENT_EXPIRES_AT = CHECKED_AT + timedelta(minutes=4)
PROOF_EXPIRES_AT = CHECKED_AT + timedelta(minutes=3)
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


def _utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(*parts: object) -> str:
    return _sha256(list(parts))


def _witness_material(
    *,
    member_count: int = 4,
    valid_from: datetime = TRUST_VALID_FROM,
    valid_until: datetime = TRUST_VALID_UNTIL,
) -> tuple[
    dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor],
    dict[str, bytes],
]:
    trust: dict[str, ProductionReservationNonEquivocationWitnessTrustAnchor] = {}
    private_keys: dict[str, bytes] = {}
    for index in range(member_count):
        key_id = f"external-witness-{index:02d}"
        private_key = bytes([0x61 + index]) * 32
        trust[key_id] = ProductionReservationNonEquivocationWitnessTrustAnchor(
            witness_identity_sha256=_digest("witness", index),
            operator_identity_sha256=_digest("operator", index),
            fault_domain_identity_sha256=_digest("fault-domain", index),
            registry_realm_identity_sha256=REGISTRY_REALM_IDENTITY_SHA256,
            registry_epoch=REGISTRY_EPOCH,
            service_binary_sha256=_digest("binary", index),
            service_schema_sha256=_digest("schema", index),
            service_configuration_sha256=_digest("configuration", index),
            service_deployment_sha256=_digest("deployment", index),
            valid_from_utc=_utc(valid_from),
            valid_until_utc=_utc(valid_until),
            verification_key=ed25519_public_key_bytes(private_key),
        )
        private_keys[key_id] = private_key
    return trust, private_keys


def _later_arguments(bundle: dict[str, object]) -> dict[str, object]:
    document = bundle["document"]
    raw = bundle["raw"]
    assert isinstance(document, dict)
    assert isinstance(raw, bytes)
    return {
        "source": raw,
        "authenticated_head_receipt_reverification_arguments": bundle["head_arguments"],
        "expected_proof_sha256": document["proof_sha256"],
        "expected_raw_proof_sha256": _raw_sha256(raw),
        "expected_later_registry_sequence": bundle["later_sequence"],
        "expected_later_native_registry_checkpoint_sha256": bundle["later_checkpoint"],
        "expected_later_registry_state_root_sha256": bundle["later_root"],
        "trusted_registry_backend_keys": bundle["backend_trust"],
        "trusted_registry_head_observer_keys": bundle["observer_trust"],
    }


def _proof_bundle(
    tmp_path: Path,
    lane: str,
    *,
    branch: str = "main",
    receipt: dict[str, object] | None = None,
    threshold: int = 3,
    maximum_faulty: int = 1,
    signer_count: int | None = None,
    witness_member_count: int = 4,
    statement_expires_at: datetime = STATEMENT_EXPIRES_AT,
    proof_issued_at: datetime = PROOF_ISSUED_AT,
    proof_observed_at: datetime = PROOF_OBSERVED_AT,
    proof_expires_at: datetime = PROOF_EXPIRES_AT,
    policy_valid_from: datetime = POLICY_VALID_FROM,
    policy_valid_until: datetime = POLICY_VALID_UNTIL,
    trust_valid_from: datetime = TRUST_VALID_FROM,
    trust_valid_until: datetime = TRUST_VALID_UNTIL,
) -> dict[str, object]:
    active_receipt = receipt or _receipt_bundle(_scenario_and_proof(tmp_path, lane))
    later_bundle = _consistency_bundle(
        active_receipt, transition_count=2, branch=branch
    )
    later_arguments = _later_arguments(later_bundle)
    later = _verify_later(later_bundle)
    trust, private_keys = _witness_material(
        member_count=witness_member_count,
        valid_from=trust_valid_from,
        valid_until=trust_valid_until,
    )
    member_rows = [
        module._policy_member_row(member_index=index, key_id=key_id, anchor=anchor)
        for index, (key_id, anchor) in enumerate(trust.items())
    ]
    member_set_sha256 = _sha256(member_rows)
    intersection = 2 * threshold - len(trust)
    policy_projection: dict[str, object] = {
        "schema_id": PRODUCTION_RESERVATION_WITNESS_QUORUM_POLICY_SCHEMA_ID,
        "policy_id": "s0-fixed-anchor-witness-policy-2026-07",
        "registry_realm_identity_sha256": later.registry_realm_identity_sha256,
        "registry_epoch": later.registry_epoch,
        "member_count": len(trust),
        "member_set_sha256": member_set_sha256,
        "quorum_threshold": threshold,
        "maximum_faulty_witness_count": maximum_faulty,
        "minimum_quorum_intersection_count": intersection,
        "minimum_honest_quorum_intersection_count": intersection - maximum_faulty,
        "member_rows": member_rows,
        "exclusive_vote_scope": "fixed_policy_realm_epoch_anchor",
        "exclusive_vote_protocol": (
            "one_common_lineage_per_fixed_policy_realm_epoch_anchor"
        ),
        "fault_assumption": ("at_most_f_independent_failure_domains_may_equivocate"),
        "quorum_rule": "two_quorums_intersect_above_fault_bound",
        "valid_from_utc": _utc(policy_valid_from),
        "valid_until_utc": _utc(policy_valid_until),
    }
    policy_sha256 = _sha256(policy_projection)
    policy = {**policy_projection, "policy_sha256": policy_sha256}
    lineage = module._verified_lineage_bindings(
        later_arguments=later_arguments,
        later=later,
        policy=policy,
    )
    signer_total = threshold if signer_count is None else signer_count
    statement_rows: list[dict[str, object]] = []
    for statement_index, (key_id, anchor) in enumerate(
        list(trust.items())[:signer_total]
    ):
        observed = WITNESS_OBSERVED_BASE + timedelta(seconds=statement_index)
        row: dict[str, object] = {
            "schema_id": PRODUCTION_RESERVATION_WITNESS_STATEMENT_SCHEMA_ID,
            "statement_index": statement_index,
            "policy_member_index": statement_index,
            "witness_quorum_policy_sha256": policy_sha256,
            "member_set_sha256": member_set_sha256,
            "fork_scope_sha256": lineage["fork_scope_sha256"],
            "common_lineage_statement_sha256": lineage[
                "common_lineage_statement_sha256"
            ],
            "caller_request_challenge_nonce_sha256": lineage[
                "caller_request_challenge_nonce_sha256"
            ],
            "lane": later.lane,
            "registry_realm_identity_sha256": later.registry_realm_identity_sha256,
            "registry_epoch": later.registry_epoch,
            "anchor_head_receipt_sha256": later.anchor_head_receipt_sha256,
            "later_head_consistency_proof_sha256": later.proof_sha256,
            "later_raw_head_consistency_proof_sha256": later.raw_proof_sha256,
            "anchor_registry_sequence": later.anchor_registry_sequence,
            "anchor_native_registry_checkpoint_sha256": (
                later.anchor_native_registry_checkpoint_sha256
            ),
            "anchor_registry_state_root_sha256": later.anchor_registry_state_root_sha256,
            "later_registry_sequence": later.later_registry_sequence,
            "later_native_registry_checkpoint_sha256": (
                later.later_native_registry_checkpoint_sha256
            ),
            "later_registry_state_root_sha256": later.later_registry_state_root_sha256,
            "checkpoint_transition_path_sha256": (
                later.checkpoint_transition_path_sha256
            ),
            "checkpoint_transition_count": lineage["checkpoint_transition_count"],
            "checkpoint_transition_vector_sha256": lineage[
                "checkpoint_transition_vector_sha256"
            ],
            "retained_slot_set_sha256": lineage["retained_slot_set_sha256"],
            "covered_sequence_start": later.anchor_registry_sequence + 1,
            "covered_sequence_end": later.later_registry_sequence,
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
            "witness_log_sequence": 100 + statement_index,
            "witness_log_checkpoint_sha256": _digest(
                "witness-log", key_id, lineage["common_lineage_statement_sha256"]
            ),
            "witness_observed_at_utc": _utc(observed),
            "expires_at_utc": _utc(statement_expires_at),
            "exclusive_vote_scope": "fixed_policy_realm_epoch_anchor",
            "exclusive_vote_protocol": (
                "one_common_lineage_per_fixed_policy_realm_epoch_anchor"
            ),
            "complete_sequence_range_observed": True,
            "no_conflicting_checkpoint_attested": True,
            "statement_outcome": (
                "conditional_fixed_policy_common_lineage_vote_recorded"
            ),
        }
        statement_sha256 = _sha256(row)
        payload = {**row, "statement_sha256": statement_sha256}
        statement_rows.append(
            {
                **payload,
                "witness_signature": {
                    "algorithm": "Ed25519",
                    "key_id": key_id,
                    "value": sign_ed25519(_canonical(payload), private_keys[key_id]),
                },
            }
        )
    signer_rows = [row["witness_key_id"] for row in statement_rows]
    projection: dict[str, object] = {
        "schema_id": PRODUCTION_RESERVATION_WITNESS_QUORUM_PROOF_SCHEMA_ID,
        "contract_sha256": FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256,
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_fixed_policy_witness_quorum_certificate",
        "lane": later.lane,
        "later_head_consistency_proof_sha256": later.proof_sha256,
        "later_raw_head_consistency_proof_sha256": later.raw_proof_sha256,
        "anchor_head_receipt_sha256": later.anchor_head_receipt_sha256,
        "registry_realm_identity_sha256": later.registry_realm_identity_sha256,
        "registry_epoch": later.registry_epoch,
        "anchor_registry_sequence": later.anchor_registry_sequence,
        "anchor_native_registry_checkpoint_sha256": (
            later.anchor_native_registry_checkpoint_sha256
        ),
        "anchor_registry_state_root_sha256": later.anchor_registry_state_root_sha256,
        "later_registry_sequence": later.later_registry_sequence,
        "later_native_registry_checkpoint_sha256": (
            later.later_native_registry_checkpoint_sha256
        ),
        "later_registry_state_root_sha256": later.later_registry_state_root_sha256,
        "checkpoint_transition_path_sha256": later.checkpoint_transition_path_sha256,
        "checkpoint_transition_count": lineage["checkpoint_transition_count"],
        "checkpoint_transition_vector": lineage["checkpoint_transition_vector"],
        "checkpoint_transition_vector_sha256": lineage[
            "checkpoint_transition_vector_sha256"
        ],
        "retained_slot_set_sha256": lineage["retained_slot_set_sha256"],
        "caller_request_challenge_nonce_sha256": lineage[
            "caller_request_challenge_nonce_sha256"
        ],
        "fork_scope": lineage["fork_scope"],
        "fork_scope_sha256": lineage["fork_scope_sha256"],
        "common_lineage_statement": lineage["common_lineage_statement"],
        "common_lineage_statement_sha256": lineage["common_lineage_statement_sha256"],
        "witness_quorum_policy": policy,
        "witness_quorum_policy_sha256": policy_sha256,
        "member_set_sha256": member_set_sha256,
        "witness_member_count": len(trust),
        "quorum_threshold": threshold,
        "maximum_faulty_witness_count": maximum_faulty,
        "minimum_quorum_intersection_count": intersection,
        "minimum_honest_quorum_intersection_count": intersection - maximum_faulty,
        "witness_statement_rows": statement_rows,
        "witness_statement_set_sha256": _sha256(statement_rows),
        "quorum_signer_key_ids": signer_rows,
        "quorum_signer_set_sha256": _sha256(signer_rows),
        "proof_issued_at_utc": _utc(proof_issued_at),
        "proof_observed_at_utc": _utc(proof_observed_at),
        "expires_at_utc": _utc(proof_expires_at),
        "certificate_outcome": (
            "conditional_fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified"
        ),
        "later_head_consistency_reverified": True,
        "fixed_policy_membership_reverified": True,
        "quorum_threshold_satisfied": True,
        "quorum_intersection_above_fault_bound_verified": True,
        "exclusive_vote_statement_signatures_verified": True,
        "fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified": True,
        **module._ACTUAL_FACT_POLICY,
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
        "later_bundle": later_bundle,
        "later_arguments": later_arguments,
        "receipt": active_receipt,
        "trust": trust,
        "private_keys": private_keys,
        "policy_sha256": policy_sha256,
    }


def _finalize_proof(document: dict[str, object]) -> tuple[dict[str, object], bytes]:
    rows = document["witness_statement_rows"]
    assert isinstance(rows, list)
    document["witness_statement_set_sha256"] = _sha256(rows)
    signer_rows = [row["witness_key_id"] for row in rows]
    document["quorum_signer_key_ids"] = signer_rows
    document["quorum_signer_set_sha256"] = _sha256(signer_rows)
    projection = {
        key: value for key, value in document.items() if key != "proof_sha256"
    }
    document["proof_sha256"] = _sha256(projection)
    return document, _canonical(document)


def _resign_statement(
    document: dict[str, object],
    *,
    statement_index: int,
    private_key: bytes,
) -> None:
    rows = document["witness_statement_rows"]
    assert isinstance(rows, list)
    signed = rows[statement_index]
    assert isinstance(signed, dict)
    signature = signed["witness_signature"]
    assert isinstance(signature, dict)
    key_id = signature["key_id"]
    row = {
        key: value
        for key, value in signed.items()
        if key not in {"statement_sha256", "witness_signature"}
    }
    statement_sha256 = _sha256(row)
    payload = {**row, "statement_sha256": statement_sha256}
    rows[statement_index] = {
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
    assert isinstance(document, dict)
    assert isinstance(raw, bytes)
    values: dict[str, object] = {
        "source": raw,
        "later_head_consistency_reverification_arguments": bundle["later_arguments"],
        "expected_proof_sha256": document["proof_sha256"],
        "expected_raw_proof_sha256": _raw_sha256(raw),
        "expected_witness_quorum_policy_sha256": bundle["policy_sha256"],
        "trusted_non_equivocation_witness_keys": bundle["trust"],
        "checked_at": CHECKED_AT,
    }
    values.update(overrides)
    return verify_external_production_reservation_witness_quorum_proof(
        **values  # type: ignore[arg-type]
    )


def test_contract_is_frozen_verifier_only_anchor_scoped_and_claim_closed() -> None:
    contract = validation_production_reservation_witness_quorum_contract_document()
    assert contract["contract_sha256"] == (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
    )
    assert contract["contract_sha256"] != "0" * 64
    assert (
        require_validation_production_reservation_witness_quorum_contract_document(
            contract
        )
        == contract
    )
    assert contract["purpose"]["declared_fault_bound_observed_by_verifier"] is False
    assert (
        contract["purpose"]["individual_certificate_proves_non_equivocation"] is False
    )
    assert contract["purpose"]["realm_wide_non_equivocation_supported"] is False
    decision = validation_production_reservation_witness_quorum_decision()
    assert (
        decision["fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified"]
        is False
    )
    assert decision["external_registry_non_equivocation_verified"] is False
    assert decision["claim_safe"] is False
    assert not any("build" in name or "sign" in name for name in module.__all__)


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_fixed_policy_quorum_reverifies_exact_anchor_and_stays_claim_closed(
    tmp_path: Path,
    lane: str,
) -> None:
    verified = _verify(_proof_bundle(tmp_path, lane))
    assert verified.lane == lane
    assert verified.witness_member_count == 4
    assert verified.quorum_threshold == 3
    assert verified.maximum_faulty_witness_count == 1
    assert verified.minimum_quorum_intersection_count == 2
    assert verified.minimum_honest_quorum_intersection_count == 1
    assert verified.quorum_signer_count == 3
    assert (
        verified.fixed_policy_same_epoch_anchor_scoped_quorum_certificate_verified
        is True
    )
    for field_name in (*module._ACTUAL_FACT_POLICY, *module._CLAIM_POLICY):
        assert getattr(verified, field_name) is False


def test_anchor_and_common_lineage_match_independent_golden_projections(
    tmp_path: Path,
) -> None:
    bundle = _proof_bundle(tmp_path, "energy_force")
    document = bundle["document"]
    later_arguments = bundle["later_arguments"]
    assert isinstance(document, dict)
    assert isinstance(later_arguments, dict)
    later = _verify_later(bundle["later_bundle"])
    head_arguments = later_arguments[
        "authenticated_head_receipt_reverification_arguments"
    ]
    assert isinstance(head_arguments, dict)

    fork_projection = {
        "schema_id": (
            "betelgeuze.engine_v2_external_reservation_witness_fork_scope/1.0.0"
        ),
        "witness_quorum_contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_WITNESS_QUORUM_CONTRACT_SHA256
        ),
        "witness_quorum_policy_sha256": document[
            "witness_quorum_policy_sha256"
        ],
        "member_set_sha256": document["member_set_sha256"],
        "lane": later.lane,
        "registry_realm_identity_sha256": later.registry_realm_identity_sha256,
        "registry_epoch": later.registry_epoch,
        "anchor_head_receipt_sha256": later.anchor_head_receipt_sha256,
        "anchor_raw_head_receipt_sha256": later.anchor_raw_head_receipt_sha256,
        "anchor_registry_proof_sha256": later.anchor_registry_proof_sha256,
        "anchor_raw_registry_proof_sha256": later.anchor_raw_registry_proof_sha256,
        "anchor_registry_sequence": later.anchor_registry_sequence,
        "anchor_native_registry_checkpoint_sha256": (
            later.anchor_native_registry_checkpoint_sha256
        ),
        "anchor_registry_state_root_sha256": later.anchor_registry_state_root_sha256,
        "caller_request_challenge_nonce_sha256": head_arguments[
            "expected_request_challenge_nonce_sha256"
        ],
    }
    fork_scope_sha256 = _sha256(fork_projection)
    assert fork_scope_sha256 == (
        "9acf96938722a7410938b6d17f8b178428d180a1121665dcbed64768b0e67158"
    )
    assert document["fork_scope"] == {
        **fork_projection,
        "fork_scope_sha256": fork_scope_sha256,
    }
    assert document["fork_scope_sha256"] == fork_scope_sha256

    common_projection = {
        "schema_id": (
            "betelgeuze.engine_v2_external_reservation_common_lineage_statement/1.0.0"
        ),
        "fork_scope_sha256": fork_scope_sha256,
        "later_head_consistency_proof_sha256": later.proof_sha256,
        "later_raw_head_consistency_proof_sha256": later.raw_proof_sha256,
        "covered_sequence_start": later.anchor_registry_sequence + 1,
        "covered_sequence_end": later.later_registry_sequence,
        "later_native_registry_checkpoint_sha256": (
            later.later_native_registry_checkpoint_sha256
        ),
        "later_registry_state_root_sha256": later.later_registry_state_root_sha256,
        "checkpoint_transition_count": later.checkpoint_transition_count,
        "checkpoint_transition_path_sha256": (
            later.checkpoint_transition_path_sha256
        ),
        "checkpoint_transition_vector_sha256": document[
            "checkpoint_transition_vector_sha256"
        ],
        "retained_slot_set_sha256": later.retained_slot_set_sha256,
        "lineage_outcome": "exact_same_epoch_descendant_path_attested",
    }
    common_lineage_sha256 = _sha256(common_projection)
    assert common_lineage_sha256 == (
        "2707006b57b915d3177bd4a67bda446cb2893582c26a92ae9cc4e03eb5488a76"
    )
    assert document["common_lineage_statement"] == {
        **common_projection,
        "common_lineage_statement_sha256": common_lineage_sha256,
    }
    assert document["common_lineage_statement_sha256"] == common_lineage_sha256


def test_q_minus_one_and_invalid_intersection_policies_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="threshold",
    ):
        _verify(
            _proof_bundle(
                tmp_path,
                "energy_force",
                signer_count=2,
            )
        )
    for threshold, maximum_faulty in ((2, 1), (3, 2)):
        case_path = tmp_path / f"policy-{threshold}-{maximum_faulty}"
        case_path.mkdir()
        with pytest.raises(
            ValidationProductionReservationWitnessQuorumError,
            match="fault-intersection bound",
        ):
            _verify(
                _proof_bundle(
                    case_path,
                    "minimization",
                    threshold=threshold,
                    maximum_faulty=maximum_faulty,
                    signer_count=3,
                )
            )


def test_fixed_roster_dynamic_add_and_remove_fail_closed(tmp_path: Path) -> None:
    five_member_path = tmp_path / "five-member-policy"
    five_member_path.mkdir()
    five_member_bundle = _proof_bundle(
        five_member_path,
        "energy_force",
        threshold=4,
        signer_count=4,
        witness_member_count=5,
    )
    reduced_trust = dict(five_member_bundle["trust"])
    reduced_trust.pop("external-witness-04")
    assert len(reduced_trust) == 4
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="fault-intersection bound",
    ):
        _verify(
            five_member_bundle,
            trusted_non_equivocation_witness_keys=reduced_trust,
        )

    four_member_path = tmp_path / "four-member-policy"
    four_member_path.mkdir()
    four_member_bundle = _proof_bundle(four_member_path, "minimization")
    expanded_trust = dict(four_member_bundle["trust"])
    five_member_trust, _private_keys = _witness_material(member_count=5)
    expanded_trust["external-witness-04"] = five_member_trust[
        "external-witness-04"
    ]
    assert len(expanded_trust) == 5
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="fault-intersection bound",
    ):
        _verify(
            four_member_bundle,
            trusted_non_equivocation_witness_keys=expanded_trust,
        )


@pytest.mark.parametrize(
    "alias_kind",
    ["fault_domain", "deployment", "public_key", "cross_role", "upstream"],
)
def test_witness_role_aliases_and_upstream_reuse_fail_closed(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    bundle = _proof_bundle(tmp_path, "energy_force")
    trust = dict(bundle["trust"])
    keys = list(trust)
    first = trust[keys[0]]
    second = trust[keys[1]]
    if alias_kind == "fault_domain":
        second = replace(
            second,
            fault_domain_identity_sha256=first.fault_domain_identity_sha256,
        )
    elif alias_kind == "deployment":
        second = replace(
            second,
            service_deployment_sha256=first.service_deployment_sha256,
        )
    elif alias_kind == "public_key":
        second = replace(second, verification_key=first.verification_key)
    elif alias_kind == "cross_role":
        second = replace(
            second,
            operator_identity_sha256=first.service_deployment_sha256,
        )
    else:
        second = replace(second, witness_identity_sha256=BACKEND_IDENTITY_SHA256)
    trust[keys[1]] = second
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="alias|upstream trust role|separated",
    ):
        _verify(bundle, trusted_non_equivocation_witness_keys=trust)


@pytest.mark.parametrize(
    "field_name", ["registry_realm_identity_sha256", "registry_epoch"]
)
def test_witness_trust_domain_transplant_fails_closed(
    tmp_path: Path,
    field_name: str,
) -> None:
    bundle = _proof_bundle(tmp_path, "minimization")
    trust = dict(bundle["trust"])
    key_id = next(iter(trust))
    anchor = trust[key_id]
    replacement = "0" * 64 if field_name.endswith("sha256") else "other-epoch"
    trust[key_id] = replace(anchor, **{field_name: replacement})
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="scope or membership",
    ):
        _verify(bundle, trusted_non_equivocation_witness_keys=trust)


def test_signature_scope_duplicate_signer_and_policy_pin_attacks_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = _proof_bundle(tmp_path, "energy_force")
    document = deepcopy(bundle["document"])
    rows = document["witness_statement_rows"]
    assert isinstance(rows, list)
    rows[0]["witness_signature"]["value"] = "0" * 128
    document, raw = _finalize_proof(document)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="signature verification failed",
    ):
        _verify(
            bundle,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=document["proof_sha256"],
        )

    document = deepcopy(bundle["document"])
    rows = document["witness_statement_rows"]
    assert isinstance(rows, list)
    rows[0]["common_lineage_statement_sha256"] = "0" * 64
    private_keys = bundle["private_keys"]
    assert isinstance(private_keys, dict)
    _resign_statement(
        document,
        statement_index=0,
        private_key=private_keys[rows[0]["witness_key_id"]],
    )
    document, raw = _finalize_proof(document)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="scope is reordered or cross-wired",
    ):
        _verify(
            bundle,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=document["proof_sha256"],
        )

    document = deepcopy(bundle["document"])
    rows = document["witness_statement_rows"]
    assert isinstance(rows, list)
    rows[2] = deepcopy(rows[1])
    rows[2]["statement_index"] = 2
    _resign_statement(
        document,
        statement_index=2,
        private_key=private_keys[rows[2]["witness_key_id"]],
    )
    document, raw = _finalize_proof(document)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="cross-wired|alias or duplicate",
    ):
        _verify(
            bundle,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=document["proof_sha256"],
        )

    document = deepcopy(bundle["document"])
    rows = document["witness_statement_rows"]
    assert isinstance(rows, list)
    original_key_id = rows[0]["witness_key_id"]
    rows[0]["witness_key_id"] = "unknown-witness"
    rows[0]["witness_signature"]["key_id"] = "unknown-witness"
    _resign_statement(
        document,
        statement_index=0,
        private_key=private_keys[original_key_id],
    )
    document, raw = _finalize_proof(document)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="not trusted",
    ):
        _verify(
            bundle,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=document["proof_sha256"],
        )

    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="policy identity",
    ):
        _verify(bundle, expected_witness_quorum_policy_sha256="0" * 64)

    document = deepcopy(bundle["document"])
    rows = document["witness_statement_rows"]
    assert isinstance(rows, list)
    untrusted = deepcopy(rows[-1])
    untrusted["statement_index"] = len(rows)
    untrusted["witness_signature"]["key_id"] = "untrusted-witness"
    rows.append(untrusted)
    document, raw = _finalize_proof(document)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="not trusted by the fixed policy",
    ):
        _verify(
            bundle,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=document["proof_sha256"],
        )


def test_unselected_fixed_roster_key_and_artifact_denials_fail_closed(
    tmp_path: Path,
) -> None:
    scenario = _scenario_and_proof(tmp_path, "minimization")
    trust, _private_keys = _witness_material()
    unselected_key_id = list(trust)[-1]
    unselected_anchor = trust[unselected_key_id]
    revoked_key_receipt = _receipt_bundle(
        scenario,
        current_revoked_key_rows=(
            {
                "role": "external_non_equivocation_witness",
                "key_id": unselected_key_id,
                "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                "reason_code": "compromised",
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="fixed-policy non-equivocation witness key is revoked",
    ):
        _verify(
            _proof_bundle(
                tmp_path,
                "minimization",
                receipt=revoked_key_receipt,
            )
        )

    revoked_artifact_receipt = _receipt_bundle(
        scenario,
        current_revoked_artifact_rows=(
            {
                "artifact_kind": "external_witness_configuration",
                "artifact_sha256": unselected_anchor.service_configuration_sha256,
                "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                "reason_code": "compromised",
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="proof identity is revoked or superseded",
    ):
        _verify(
            _proof_bundle(
                tmp_path,
                "minimization",
                receipt=revoked_artifact_receipt,
            )
        )


@pytest.mark.parametrize(
    "attack",
    [
        "reorder",
        "expire",
        "bool_member_count",
        "bool_member_index",
        "bool_quorum_intersection",
        "float_honest_intersection",
    ],
)
def test_fixed_roster_order_validity_and_exact_count_fail_closed(
    tmp_path: Path,
    attack: str,
) -> None:
    bundle = _proof_bundle(tmp_path, "energy_force")
    document = deepcopy(bundle["document"])
    trust = dict(bundle["trust"])
    policy = document["witness_quorum_policy"]
    assert isinstance(policy, dict)
    member_rows = policy["member_rows"]
    assert isinstance(member_rows, list)
    if attack == "reorder":
        member_rows[0], member_rows[1] = member_rows[1], member_rows[0]
    elif attack == "expire":
        key_id = list(trust)[-1]
        anchor = trust[key_id]
        expired_at = POLICY_VALID_UNTIL - timedelta(seconds=1)
        trust[key_id] = replace(anchor, valid_until_utc=_utc(expired_at))
        member_rows[-1] = module._policy_member_row(
            member_index=len(member_rows) - 1,
            key_id=key_id,
            anchor=trust[key_id],
        )
    elif attack == "bool_member_count":
        policy["member_count"] = True
    elif attack == "bool_member_index":
        member_rows[0]["member_index"] = False
    elif attack == "bool_quorum_intersection":
        policy["minimum_quorum_intersection_count"] = True
    else:
        policy["minimum_honest_quorum_intersection_count"] = 1.0
    member_set_sha256 = _sha256(member_rows)
    policy["member_set_sha256"] = member_set_sha256
    policy_projection = {
        key: value for key, value in policy.items() if key != "policy_sha256"
    }
    policy_sha256 = _sha256(policy_projection)
    policy["policy_sha256"] = policy_sha256
    document["witness_quorum_policy_sha256"] = policy_sha256
    document["member_set_sha256"] = member_set_sha256
    document, raw = _finalize_proof(document)
    with pytest.raises(ValidationProductionReservationWitnessQuorumError):
        _verify(
            bundle,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=document["proof_sha256"],
            expected_witness_quorum_policy_sha256=policy_sha256,
            trusted_non_equivocation_witness_keys=trust,
        )


def test_same_anchor_sibling_certificates_verify_only_as_conditional_attestations(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "minimization"))
    left = _verify(
        _proof_bundle(tmp_path, "minimization", branch="left", receipt=receipt)
    )
    right = _verify(
        _proof_bundle(tmp_path, "minimization", branch="right", receipt=receipt)
    )
    assert left.fork_scope_sha256 == right.fork_scope_sha256
    assert left.common_lineage_statement_sha256 != right.common_lineage_statement_sha256
    assert left.external_registry_non_equivocation_verified is False
    assert right.external_registry_non_equivocation_verified is False
    assert left.exclusive_vote_enforcement_verified is False
    assert right.independent_witness_journal_consistency_verified is False


def test_different_anchor_changes_fork_scope_and_rejects_signed_row_transplant(
    tmp_path: Path,
) -> None:
    scenario = _scenario_and_proof(tmp_path, "minimization")
    left_receipt = _receipt_bundle(scenario)
    right_receipt = _receipt_bundle(
        scenario,
        receipt_issued_at=RECEIPT_ISSUED_AT + timedelta(seconds=1),
    )
    left = _proof_bundle(
        tmp_path,
        "minimization",
        receipt=left_receipt,
    )
    right = _proof_bundle(
        tmp_path,
        "minimization",
        receipt=right_receipt,
    )
    left_verified = _verify(left)
    right_verified = _verify(right)
    assert left_verified.fork_scope_sha256 != right_verified.fork_scope_sha256

    transplanted = deepcopy(right["document"])
    left_document = left["document"]
    assert isinstance(transplanted, dict)
    assert isinstance(left_document, dict)
    transplanted_rows = transplanted["witness_statement_rows"]
    left_rows = left_document["witness_statement_rows"]
    assert isinstance(transplanted_rows, list)
    assert isinstance(left_rows, list)
    transplanted_rows[0] = deepcopy(left_rows[0])
    transplanted, raw = _finalize_proof(transplanted)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="scope is reordered or cross-wired",
    ):
        _verify(
            right,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=transplanted["proof_sha256"],
        )


def test_proof_expiry_cannot_outlive_signed_statement_expiry(tmp_path: Path) -> None:
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="invalid causal time",
    ):
        _verify(
            _proof_bundle(
                tmp_path,
                "energy_force",
                proof_expires_at=STATEMENT_EXPIRES_AT + timedelta(seconds=1),
            )
        )


def test_strict_status_and_expiry_boundaries_fail_closed(tmp_path: Path) -> None:
    status_path = tmp_path / "status-boundary"
    status_path.mkdir()
    scenario = _scenario_and_proof(status_path, "energy_force")
    receipt = _receipt_bundle(
        scenario,
        current_status_issued_at=PROOF_OBSERVED_AT,
    )
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="invalid causal time",
    ):
        _verify(
            _proof_bundle(
                status_path,
                "energy_force",
                receipt=receipt,
            )
        )

    expiry_path = tmp_path / "expiry-boundary"
    expiry_path.mkdir()
    bundle = _proof_bundle(expiry_path, "minimization")
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="invalid causal time",
    ):
        _verify(bundle, checked_at=PROOF_EXPIRES_AT)


def test_one_second_over_time_window_limits_fails_closed(tmp_path: Path) -> None:
    proof_validity_path = tmp_path / "proof-validity"
    proof_validity_path.mkdir()
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="proof is overlong",
    ):
        _verify(
            _proof_bundle(
                proof_validity_path,
                "energy_force",
                proof_expires_at=(
                    PROOF_ISSUED_AT
                    + module.PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_VALIDITY
                    + timedelta(seconds=1)
                ),
            )
        )

    proof_age_path = tmp_path / "proof-age"
    proof_age_path.mkdir()
    over_age_observed = (
        CHECKED_AT
        - module.PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_AGE
        - timedelta(seconds=1)
    )
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="proof is stale",
    ):
        _verify(
            _proof_bundle(
                proof_age_path,
                "minimization",
                proof_issued_at=over_age_observed,
                proof_observed_at=over_age_observed,
            )
        )

    statement_validity_path = tmp_path / "statement-validity"
    statement_validity_path.mkdir()
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="invalid time or key validity",
    ):
        _verify(
            _proof_bundle(
                statement_validity_path,
                "energy_force",
                statement_expires_at=(
                    WITNESS_OBSERVED_BASE
                    + module.PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_VALIDITY
                    + timedelta(seconds=1)
                ),
            )
        )

    policy_validity_path = tmp_path / "policy-validity"
    policy_validity_path.mkdir()
    trust_from = CHECKED_AT - timedelta(days=2)
    trust_until = CHECKED_AT + timedelta(days=2)
    policy_from = CHECKED_AT - timedelta(hours=12)
    policy_until = (
        policy_from
        + module.PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_POLICY_VALIDITY
        + timedelta(seconds=1)
    )
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="policy scope or membership is cross-wired",
    ):
        _verify(
            _proof_bundle(
                policy_validity_path,
                "minimization",
                policy_valid_from=policy_from,
                policy_valid_until=policy_until,
                trust_valid_from=trust_from,
                trust_valid_until=trust_until,
            )
        )


def test_post_quorum_status_denies_non_signing_roster_key(tmp_path: Path) -> None:
    scenario = _scenario_and_proof(tmp_path, "energy_force")
    receipt = _receipt_bundle(
        scenario,
        current_revoked_key_rows=(
            {
                "role": "external_non_equivocation_witness",
                "key_id": "external-witness-03",
                "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                "reason_code": "compromised",
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="witness key is revoked",
    ):
        _verify(_proof_bundle(tmp_path, "energy_force", receipt=receipt))


def test_post_quorum_status_denies_non_signing_roster_deployment(
    tmp_path: Path,
) -> None:
    scenario = _scenario_and_proof(tmp_path, "minimization")
    receipt = _receipt_bundle(
        scenario,
        current_supersession_rows=(
            {
                "artifact_kind": "external_witness_deployment",
                "superseded_sha256": _digest("deployment", 3),
                "replacement_sha256": _digest("replacement-deployment", 3),
                "superseded_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="revoked or superseded",
    ):
        _verify(_proof_bundle(tmp_path, "minimization", receipt=receipt))


def test_post_quorum_status_denies_certificate_and_lineage_identities(
    tmp_path: Path,
) -> None:
    scenario = _scenario_and_proof(tmp_path, "energy_force")
    baseline = _proof_bundle(
        tmp_path,
        "energy_force",
        receipt=_receipt_bundle(scenario),
    )
    document = baseline["document"]
    baseline_raw = baseline["raw"]
    assert isinstance(document, dict)
    assert isinstance(baseline_raw, bytes)
    statements = document["witness_statement_rows"]
    assert isinstance(statements, list)
    first_statement = statements[0]
    assert isinstance(first_statement, dict)
    denied_identities = (
        ("external_witness_quorum_proof", document["proof_sha256"]),
        ("external_witness_quorum_raw_proof", _raw_sha256(baseline_raw)),
        (
            "external_witness_quorum_policy",
            document["witness_quorum_policy_sha256"],
        ),
        ("external_witness_statement", first_statement["statement_sha256"]),
        (
            "external_witness_log_checkpoint",
            first_statement["witness_log_checkpoint_sha256"],
        ),
        ("external_witness_member_set", document["member_set_sha256"]),
        ("external_witness_fork_scope", document["fork_scope_sha256"]),
        (
            "external_witness_common_lineage",
            document["common_lineage_statement_sha256"],
        ),
    )
    for artifact_kind, artifact_sha256 in denied_identities:
        receipt = _receipt_bundle(
            scenario,
            current_revoked_artifact_rows=(
                {
                    "artifact_kind": artifact_kind,
                    "artifact_sha256": artifact_sha256,
                    "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                    "reason_code": "compromised",
                },
            ),
        )
        denied = _proof_bundle(tmp_path, "energy_force", receipt=receipt)
        denied_document = denied["document"]
        assert isinstance(denied_document, dict)
        assert denied_document["proof_sha256"] == document["proof_sha256"]
        with pytest.raises(
            ValidationProductionReservationWitnessQuorumError,
            match="proof identity is revoked or superseded",
        ):
            _verify(denied)


def test_claim_promotion_duplicate_json_and_transport_bounds_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = _proof_bundle(tmp_path, "minimization")
    document = deepcopy(bundle["document"])
    document["claim_safe"] = True
    document, raw = _finalize_proof(document)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="omitted or transplanted",
    ):
        _verify(
            bundle,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=document["proof_sha256"],
        )

    document = deepcopy(bundle["document"])
    document["contract_sha256"] = "0" * 64
    document, raw = _finalize_proof(document)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="omitted or transplanted",
    ):
        _verify(
            bundle,
            source=raw,
            expected_raw_proof_sha256=_raw_sha256(raw),
            expected_proof_sha256=document["proof_sha256"],
        )

    valid_raw = bundle["raw"]
    assert isinstance(valid_raw, bytes)
    duplicate = b'{"schema_id":"duplicate",' + valid_raw[1:]
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="duplicate JSON key",
    ):
        _verify(
            bundle, source=duplicate, expected_raw_proof_sha256=_raw_sha256(duplicate)
        )

    oversized_integer = b'{"n":' + b"9" * 21 + b"}"
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="not canonical ASCII JSON",
    ):
        _verify(
            bundle,
            source=oversized_integer,
            expected_raw_proof_sha256=_raw_sha256(oversized_integer),
        )

    oversized_transport = (
        b"{" + b" " * module.PRODUCTION_RESERVATION_WITNESS_QUORUM_MAX_BYTES
    )
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="exceeds its transport bound",
    ):
        _verify(
            bundle,
            source=oversized_transport,
            expected_raw_proof_sha256=_raw_sha256(oversized_transport),
        )


def test_caller_pinned_outer_logical_and_raw_identities_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = _proof_bundle(tmp_path, "energy_force")
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="raw witness-quorum proof identity is cross-wired",
    ):
        _verify(bundle, expected_raw_proof_sha256="0" * 64)
    with pytest.raises(
        ValidationProductionReservationWitnessQuorumError,
        match="logical SHA-256 verification failed",
    ):
        _verify(bundle, expected_proof_sha256="0" * 64)


def test_verification_dto_cannot_be_constructed_through_public_initializer() -> None:
    with pytest.raises(TypeError):
        ProductionReservationWitnessQuorumVerification(  # type: ignore[call-arg]
            proof_sha256="0" * 64
        )


def test_nested_numeric_fields_require_exact_integers(tmp_path: Path) -> None:
    bundle = _proof_bundle(tmp_path, "minimization")
    private_keys = bundle["private_keys"]
    assert isinstance(private_keys, dict)
    for field_name, replacement in (
        ("statement_index", False),
        ("anchor_registry_sequence", 1.0),
        ("later_registry_sequence", True),
        ("checkpoint_transition_count", 2.0),
        ("covered_sequence_start", True),
        ("covered_sequence_end", 1.0),
        ("witness_log_sequence", True),
    ):
        document = deepcopy(bundle["document"])
        rows = document["witness_statement_rows"]
        assert isinstance(rows, list)
        rows[0][field_name] = replacement
        _resign_statement(
            document,
            statement_index=0,
            private_key=private_keys[rows[0]["witness_key_id"]],
        )
        document, raw = _finalize_proof(document)
        with pytest.raises(
            ValidationProductionReservationWitnessQuorumError,
            match="exact bounded integer",
        ):
            _verify(
                bundle,
                source=raw,
                expected_raw_proof_sha256=_raw_sha256(raw),
                expected_proof_sha256=document["proof_sha256"],
            )


def test_verification_dto_is_explicitly_not_an_authorization_token() -> None:
    forged = object.__new__(ProductionReservationWitnessQuorumVerification)
    object.__setattr__(forged, "claim_safe", True)
    assert forged.claim_safe is True

    contract = validation_production_reservation_witness_quorum_contract_document()
    assert contract["purpose"]["verification_result_is_not_an_authorization_token"]
    assert contract["purpose"]["downstream_raw_proof_reverification_required"]
    assert validation_production_reservation_witness_quorum_decision()["claim_safe"] is False
