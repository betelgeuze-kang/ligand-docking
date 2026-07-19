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
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    EvidenceAuthorityTrustAnchor,
    build_signed_production_evidence_status_snapshot,
)
from betelgeuze_engine_v2.physics.validation_production_reservation_authenticated_head_receipt import (
    FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256,
    PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES,
    PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_VALIDITY,
    PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_SCHEMA_ID,
    ProductionReservationHeadReceiptAuthorityTrustAnchor,
    ValidationProductionReservationAuthenticatedHeadReceiptError,
    require_validation_production_reservation_authenticated_head_receipt_contract_document,
    validation_production_reservation_authenticated_head_receipt_contract_document,
    validation_production_reservation_authenticated_head_receipt_decision,
    verify_external_production_reservation_authenticated_head_receipt,
)
from tests.unit.test_engine_v2_validation_production_reservation_custody_extension import (
    CHECKED_AT,
    COMMITTED_AT,
    REGISTRY_EPOCH,
    REGISTRY_REALM_IDENTITY_SHA256,
    _current_status_descendant,
)
from tests.unit.test_engine_v2_validation_production_reservation_registry_proof import (
    BACKEND_IDENTITY_SHA256,
    BACKEND_KEY_ID,
    BACKEND_PRIVATE_KEY,
    OBSERVED_AT,
    _scenario_and_proof,
    _seq5_arguments,
    _verification_arguments,
    _verify as _verify_registry_proof,
)
from tests.unit.test_engine_v2_validation_production_review_authorization_custody_extension import (
    CUSTODIAN_IDENTITY,
    EVENT_STATUS_AUTHORITY_PRIVATE_KEY,
    HOST_IDENTITY,
    STATUS_AUTHORITY_IDENTITY,
    STATUS_AUTHORITY_KEY_ID,
    _event_base_reverification_arguments,
)


AUTHORITY_IDENTITY_SHA256 = "41" * 32
AUTHORITY_KEY_ID = "external-head-receipt-authority-2026-07"
AUTHORITY_PRIVATE_KEY = bytes.fromhex("12" * 32)
AUTHORITY_BINARY_SHA256 = "42" * 32
AUTHORITY_SCHEMA_SHA256 = "43" * 32
AUTHORITY_CONFIGURATION_SHA256 = "44" * 32
AUTHORITY_DEPLOYMENT_SHA256 = "45" * 32
REQUEST_CHALLENGE_NONCE_SHA256 = "46" * 32
TRUST_VALID_FROM = "2026-07-19T00:00:00Z"
TRUST_VALID_UNTIL = "2026-07-20T00:00:00Z"
REQUESTED_AT = OBSERVED_AT
HEAD_OBSERVED_AT = OBSERVED_AT + timedelta(minutes=1)
RECEIPT_ISSUED_AT = OBSERVED_AT + timedelta(minutes=2)
CURRENT_STATUS_ISSUED_AT = RECEIPT_ISSUED_AT + timedelta(seconds=30)
EXPIRES_AT = CHECKED_AT + timedelta(minutes=5)
CURRENT_STATUS_CHECKPOINT_SHA256 = "47" * 32


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


def _authority_anchor(
    *,
    authority_identity_sha256: str = AUTHORITY_IDENTITY_SHA256,
    valid_from_utc: str = TRUST_VALID_FROM,
    valid_until_utc: str = TRUST_VALID_UNTIL,
    private_key: bytes = AUTHORITY_PRIVATE_KEY,
) -> ProductionReservationHeadReceiptAuthorityTrustAnchor:
    return ProductionReservationHeadReceiptAuthorityTrustAnchor(
        authority_identity_sha256,
        REGISTRY_REALM_IDENTITY_SHA256,
        REGISTRY_EPOCH,
        AUTHORITY_BINARY_SHA256,
        AUTHORITY_SCHEMA_SHA256,
        AUTHORITY_CONFIGURATION_SHA256,
        AUTHORITY_DEPLOYMENT_SHA256,
        valid_from_utc,
        valid_until_utc,
        ed25519_public_key_bytes(private_key),
    )


def _registry_arguments(bundle: dict[str, object]) -> dict[str, object]:
    arguments = _verification_arguments(bundle)
    checked_at = arguments.pop("checked_at")
    assert checked_at == CHECKED_AT
    return arguments


def _status_tail(registry_arguments: dict[str, object]) -> tuple[dict[str, object], bytes]:
    seq5 = registry_arguments["sequence_five_reverification_arguments"]
    assert isinstance(seq5, dict)
    prefix = seq5["current_raw_sequence_four_prefix"]
    assert isinstance(prefix, dict)
    lineage = prefix["raw_status_lineage_bytes"]
    assert isinstance(lineage, (list, tuple))
    raw = lineage[-1]
    assert isinstance(raw, bytes)
    status = json.loads(raw.decode("ascii"))
    assert isinstance(status, dict)
    return status, raw


def _current_registry_arguments(
    bundle: dict[str, object],
    *,
    issued_at: datetime = CURRENT_STATUS_ISSUED_AT,
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

    bound = _current_status_descendant(scenario, issued_at=OBSERVED_AT)
    status_three = bound["status_lineage"][-1]
    assert isinstance(status_three, dict)
    status_four = build_signed_production_evidence_status_snapshot(
        permit_sha256=scenario["permit"]["permit_sha256"],  # type: ignore[index]
        run_id_sha256=scenario["context"]["run_id_sha256"],  # type: ignore[index]
        lane=scenario["lane"],  # type: ignore[arg-type]
        custodian_identity_sha256=CUSTODIAN_IDENTITY,
        enrolled_host_identity_sha256=HOST_IDENTITY,
        status_sequence=4,
        external_log_checkpoint_sha256=CURRENT_STATUS_CHECKPOINT_SHA256,
        previous_snapshot_sha256=status_three["snapshot_sha256"],
        issued_at=issued_at,
        authority_identity_sha256=STATUS_AUTHORITY_IDENTITY,
        authority_key_id=STATUS_AUTHORITY_KEY_ID,
        signing_key=EVENT_STATUS_AUTHORITY_PRIVATE_KEY,
        revoked_key_rows=revoked_key_rows,
        revoked_artifact_rows=revoked_artifact_rows,
        supersession_rows=supersession_rows,
    )
    current = dict(bound)
    current["status_lineage"] = [
        *bound["status_lineage"],  # type: ignore[misc]
        status_four,
    ]
    current["raw_status_lineage"] = [
        *bound["raw_status_lineage"],  # type: ignore[misc]
        _canonical(status_four),
    ]
    current["base_reverification_arguments"] = _event_base_reverification_arguments(
        scenario["context"],  # type: ignore[arg-type]
        scenario["event_one"],  # type: ignore[arg-type]
        scenario["event_two"],  # type: ignore[arg-type]
        current_status_snapshot_sha256=status_four["snapshot_sha256"],
        current_status_checkpoint_sha256=CURRENT_STATUS_CHECKPOINT_SHA256,
        revoked_authority_key_ids=tuple(
            sorted(row["key_id"] for row in revoked_key_rows)
        ),
    )
    current_bundle = {
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
    return _registry_arguments(current_bundle)


def _resign_receipt(
    document: dict[str, object],
    *,
    authority_key_id: str = AUTHORITY_KEY_ID,
    authority_private_key: bytes = AUTHORITY_PRIVATE_KEY,
) -> tuple[dict[str, object], bytes]:
    projection = {
        key: value
        for key, value in document.items()
        if key not in {"head_receipt_sha256", "head_receipt_authority_signature"}
    }
    receipt_sha256 = _sha256(projection)
    payload = {**projection, "head_receipt_sha256": receipt_sha256}
    signed = {
        **payload,
        "head_receipt_authority_signature": {
            "algorithm": "Ed25519",
            "key_id": authority_key_id,
            "value": sign_ed25519(
                _canonical(payload),
                authority_private_key,
            ),
        },
    }
    return signed, _canonical(signed)


def _receipt_bundle(
    bundle: dict[str, object],
    *,
    authority_key_id: str = AUTHORITY_KEY_ID,
    authority_private_key: bytes = AUTHORITY_PRIVATE_KEY,
    authority_anchor: ProductionReservationHeadReceiptAuthorityTrustAnchor | None = None,
    requested_at: datetime = REQUESTED_AT,
    head_observed_at: datetime = HEAD_OBSERVED_AT,
    receipt_issued_at: datetime = RECEIPT_ISSUED_AT,
    expires_at: datetime = EXPIRES_AT,
    current_status_issued_at: datetime = CURRENT_STATUS_ISSUED_AT,
    current_revoked_key_rows: tuple[dict[str, str], ...] = (),
    current_revoked_artifact_rows: tuple[dict[str, str], ...] = (),
    current_supersession_rows: tuple[dict[str, str], ...] = (),
) -> dict[str, object]:
    proof = _verify_registry_proof(bundle)
    registry_arguments = _registry_arguments(bundle)
    status, raw_status = _status_tail(registry_arguments)
    anchor = authority_anchor or _authority_anchor(private_key=authority_private_key)
    authority_public_key_sha256 = _raw_sha256(anchor.verification_key)
    projection: dict[str, object] = {
        "schema_id": PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_SCHEMA_ID,
        "contract_sha256": FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256,
        "evidence_class": "synthetic_validation_production",
        "artifact_stage": "external_authenticated_reservation_head_status_receipt",
        "lane": proof.lane,
        "registry_proof_sha256": proof.proof_sha256,
        "raw_registry_proof_sha256": proof.raw_proof_sha256,
        "sequence_five_commit_sha256": proof.commit_sha256,
        "raw_sequence_five_commit_sha256": proof.raw_commit_sha256,
        "registry_transaction_sha256": proof.registry_transaction_sha256,
        "registry_realm_identity_sha256": proof.registry_realm_identity_sha256,
        "registry_epoch": proof.registry_epoch,
        "registry_sequence": proof.committed_registry_sequence,
        "native_registry_checkpoint_sha256": proof.committed_native_registry_checkpoint_sha256,
        "registry_state_root_sha256": proof.committed_registry_state_root_sha256,
        "status_tail_snapshot_sha256": status["snapshot_sha256"],
        "raw_status_tail_sha256": _raw_sha256(raw_status),
        "status_tail_sequence": status["status_sequence"],
        "status_tail_external_log_checkpoint_sha256": status[
            "external_log_checkpoint_sha256"
        ],
        "status_tail_issued_at_utc": status["issued_at_utc"],
        "head_receipt_authority_identity_sha256": anchor.authority_identity_sha256,
        "head_receipt_authority_key_id": authority_key_id,
        "head_receipt_authority_public_key_sha256": authority_public_key_sha256,
        "head_receipt_service_binary_sha256": anchor.service_binary_sha256,
        "head_receipt_service_schema_sha256": anchor.service_schema_sha256,
        "head_receipt_service_configuration_sha256": (
            anchor.service_configuration_sha256
        ),
        "head_receipt_service_deployment_sha256": anchor.service_deployment_sha256,
        "request_challenge_nonce_sha256": REQUEST_CHALLENGE_NONCE_SHA256,
        "proof_observed_at_utc": proof.observed_at_utc,
        "requested_at_utc": _utc(requested_at),
        "head_observed_at_utc": _utc(head_observed_at),
        "receipt_issued_at_utc": _utc(receipt_issued_at),
        "expires_at_utc": _utc(expires_at),
        "head_attestation_outcome": "authority_attested_exact_head_and_status_tail",
        "registry_transaction_proof_reverified": True,
        "receipt_authority_signature_verified": True,
        "caller_challenge_match_verified": True,
        "exact_registry_head_and_status_tail_bound": True,
        "authenticated_external_head_status_receipt_verified": True,
        "caller_challenge_freshness_verified": False,
        "caller_challenge_one_use_verified": False,
        "global_latest_registry_head_verified": False,
        "global_latest_status_head_verified": False,
        "external_serializable_registry_commit_verified": False,
        "registry_head_compare_and_set_committed": False,
        "status_head_compare_and_set_committed": False,
        "permit_one_use_slot_consumed": False,
        "authorization_nonce_slot_consumed": False,
        "predecessor_successor_slot_consumed": False,
        "custody_successor_uniqueness_enforced": False,
        "external_registry_non_equivocation_verified": False,
        "later_head_consistency_verified": False,
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
    document, raw = _resign_receipt(
        projection,
        authority_key_id=authority_key_id,
        authority_private_key=authority_private_key,
    )
    return {
        "document": document,
        "raw": raw,
        "registry_arguments": registry_arguments,
        "current_registry_arguments": _current_registry_arguments(
            bundle,
            issued_at=current_status_issued_at,
            revoked_key_rows=current_revoked_key_rows,
            revoked_artifact_rows=current_revoked_artifact_rows,
            supersession_rows=current_supersession_rows,
        ),
        "trusted_keys": {authority_key_id: anchor},
    }


def _verify_receipt(receipt: dict[str, object], **overrides: object):
    document = receipt["document"]
    raw = receipt["raw"]
    assert isinstance(document, dict)
    assert isinstance(raw, bytes)
    values: dict[str, object] = {
        "source": raw,
        "registry_proof_reverification_arguments": receipt[
            "registry_arguments"
        ],
        "current_registry_proof_reverification_arguments": receipt[
            "current_registry_arguments"
        ],
        "expected_head_receipt_sha256": document["head_receipt_sha256"],
        "expected_raw_head_receipt_sha256": _raw_sha256(raw),
        "expected_request_challenge_nonce_sha256": (
            REQUEST_CHALLENGE_NONCE_SHA256
        ),
        "trusted_head_receipt_authority_keys": receipt["trusted_keys"],
        "checked_at": CHECKED_AT,
    }
    values.update(overrides)
    return verify_external_production_reservation_authenticated_head_receipt(
        **values  # type: ignore[arg-type]
    )


def test_contract_is_frozen_verifier_only_and_claim_closed() -> None:
    contract = validation_production_reservation_authenticated_head_receipt_contract_document()
    assert (
        contract["contract_sha256"]
        == FROZEN_VALIDATION_PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_CONTRACT_SHA256
    )
    assert require_validation_production_reservation_authenticated_head_receipt_contract_document(
        contract
    ) == contract
    assert contract["purpose"]["verifier_only"] is True
    assert contract["purpose"]["external_receipt_service_implemented_by_package"] is False
    assert contract["purpose"]["global_latest_head_verification_supported"] is False
    assert contract["purpose"]["later_head_consistency_supported"] is False
    assert contract["trust_and_freshness"][
        "reverification_snapshot_maximum_nodes"
    ] == PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES
    supplied = contract["verified_facts_when_external_receipt_is_supplied"]
    assert supplied["authenticated_external_head_status_receipt_verified"] is True
    assert supplied["post_receipt_current_status_descendant_reverified"] is True
    assert supplied["caller_challenge_freshness_verified"] is False
    assert supplied["caller_challenge_one_use_verified"] is False
    assert supplied["global_latest_registry_head_verified"] is False
    assert supplied["registry_head_compare_and_set_committed"] is False
    decision = validation_production_reservation_authenticated_head_receipt_decision()
    assert decision["verifier_implemented"] is True
    assert decision["external_authenticated_receipt_present"] is False
    assert decision["authenticated_external_head_status_receipt_verified"] is False
    assert decision["production_validation_execution_authorized"] is False


@pytest.mark.parametrize("lane", ["energy_force", "minimization"])
def test_authenticated_exact_head_status_receipt_verifies_both_lanes(
    tmp_path: Path,
    lane: str,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, lane))
    verified = _verify_receipt(receipt)
    assert verified.lane == lane
    assert verified.registry_transaction_proof_reverified is True
    assert verified.receipt_authority_signature_verified is True
    assert verified.caller_challenge_match_verified is True
    assert verified.exact_registry_head_and_status_tail_bound is True
    assert verified.post_receipt_current_status_descendant_reverified is True
    assert verified.current_status_tail_sequence > verified.status_tail_sequence
    assert verified.authenticated_external_head_status_receipt_verified is True
    assert verified.caller_challenge_freshness_verified is False
    assert verified.caller_challenge_one_use_verified is False
    assert verified.global_latest_registry_head_verified is False
    assert verified.global_latest_status_head_verified is False
    assert verified.external_serializable_registry_commit_verified is False
    assert verified.registry_head_compare_and_set_committed is False
    assert verified.status_head_compare_and_set_committed is False
    assert verified.permit_one_use_slot_consumed is False
    assert verified.external_registry_non_equivocation_verified is False
    assert verified.later_head_consistency_verified is False
    assert verified.registry_epoch_transition_continuity_verified is False
    assert verified.production_validation_execution_authorized is False
    assert verified.scientifically_validated is False
    assert verified.claim_safe is False


def test_raw_receipt_challenge_and_registry_proof_reverification_fail_closed(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="raw authenticated head receipt identity is cross-wired",
    ):
        _verify_receipt(receipt, expected_raw_head_receipt_sha256="0" * 64)
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="request challenge is cross-wired",
    ):
        _verify_receipt(
            receipt,
            expected_request_challenge_nonce_sha256="0" * 64,
        )

    registry_arguments = deepcopy(receipt["registry_arguments"])
    registry_arguments["expected_proof_sha256"] = "0" * 64
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="registry transaction proof reverification failed",
    ):
        _verify_receipt(
            receipt,
            registry_proof_reverification_arguments=registry_arguments,
        )


def test_post_receipt_status_must_be_a_strict_reverified_descendant(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "minimization"))
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="not a strict descendant",
    ):
        _verify_receipt(
            receipt,
            current_registry_proof_reverification_arguments=deepcopy(
                receipt["registry_arguments"]
            ),
        )


@pytest.mark.parametrize(
    "field",
    [
        "native_registry_checkpoint_sha256",
        "raw_status_tail_sha256",
        "head_receipt_service_deployment_sha256",
    ],
)
def test_signed_sibling_or_transplanted_projection_is_rejected(
    tmp_path: Path,
    field: str,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "minimization"))
    document = deepcopy(receipt["document"])
    document[field] = "aa" * 32
    signed, raw = _resign_receipt(document)
    tampered = {**receipt, "document": signed, "raw": raw}
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="fields are omitted or transplanted",
    ):
        _verify_receipt(tampered)


def test_authority_key_id_identity_and_material_cannot_alias_prior_roles(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "energy_force")

    key_id_alias = _receipt_bundle(bundle, authority_key_id=BACKEND_KEY_ID)
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="prior trust roles alias",
    ):
        _verify_receipt(key_id_alias)

    identity_anchor = _authority_anchor(
        authority_identity_sha256=BACKEND_IDENTITY_SHA256
    )
    identity_alias = _receipt_bundle(bundle, authority_anchor=identity_anchor)
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="prior trust roles alias",
    ):
        _verify_receipt(identity_alias)

    material_anchor = _authority_anchor(private_key=BACKEND_PRIVATE_KEY)
    material_alias = _receipt_bundle(
        bundle,
        authority_private_key=BACKEND_PRIVATE_KEY,
        authority_anchor=material_anchor,
    )
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="prior trust roles alias",
    ):
        _verify_receipt(material_alias)


def test_prior_role_alias_check_uses_the_verified_argument_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import betelgeuze_engine_v2.physics.validation_production_reservation_authenticated_head_receipt as module

    bundle = _scenario_and_proof(tmp_path, "energy_force")
    material_anchor = _authority_anchor(private_key=BACKEND_PRIVATE_KEY)
    receipt = _receipt_bundle(
        bundle,
        authority_private_key=BACKEND_PRIVATE_KEY,
        authority_anchor=material_anchor,
    )
    original_arguments = receipt["registry_arguments"]
    assert isinstance(original_arguments, dict)
    original_reverify = module._reverify_registry_proof
    call_count = 0

    def mutate_original_after_snapshot(
        arguments: object,
        *,
        checked_at: datetime,
    ):
        nonlocal call_count
        result = original_reverify(arguments, checked_at=checked_at)
        if call_count == 0:
            original_arguments["trusted_registry_backend_keys"] = {
                BACKEND_KEY_ID: object()
            }
        call_count += 1
        return result

    monkeypatch.setattr(
        module,
        "_reverify_registry_proof",
        mutate_original_after_snapshot,
    )
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="prior trust roles alias",
    ):
        _verify_receipt(receipt)


def test_snapshot_rejects_untrusted_copy_hooks_without_executing_them(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "minimization"))

    class CopyHook:
        called = False

        def __deepcopy__(self, memo: object) -> object:
            del memo
            type(self).called = True
            return self

    arguments = dict(receipt["registry_arguments"])
    arguments["source"] = CopyHook()
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="unsupported value",
    ):
        _verify_receipt(
            receipt,
            registry_proof_reverification_arguments=arguments,
        )
    assert CopyHook.called is False

    oversized = dict(receipt["registry_arguments"])
    oversized["source"] = [
        None
    ] * (PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_SNAPSHOT_NODES + 1)
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="list exceeds its snapshot bound",
    ):
        _verify_receipt(
            receipt,
            registry_proof_reverification_arguments=oversized,
        )


def test_post_receipt_status_cannot_substitute_its_trust_domain(
    tmp_path: Path,
) -> None:
    receipt = _receipt_bundle(_scenario_and_proof(tmp_path, "energy_force"))
    current_arguments = deepcopy(receipt["current_registry_arguments"])
    seq5 = current_arguments["sequence_five_reverification_arguments"]
    current_sequence_four = seq5[
        "current_sequence_four_reverification_arguments"
    ]
    base = current_sequence_four["base_reverification_arguments"]
    trusted_authority_keys = base["trusted_authority_keys"]
    trusted_authority_keys["substituted-status-authority"] = (
        EvidenceAuthorityTrustAnchor(
            "48" * 32,
            ed25519_public_key_bytes(bytes.fromhex("34" * 32)),
        )
    )
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="trust domain differs",
    ):
        _verify_receipt(
            receipt,
            current_registry_proof_reverification_arguments=current_arguments,
        )


def test_signature_causal_time_validity_and_claim_promotion_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "minimization")
    receipt = _receipt_bundle(bundle)

    document = deepcopy(receipt["document"])
    signature = document["head_receipt_authority_signature"]
    assert isinstance(signature, dict)
    signature["value"] = "0" * 128
    raw = _canonical(document)
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="signature verification failed",
    ):
        _verify_receipt({**receipt, "document": document, "raw": raw})

    backdated = _receipt_bundle(
        bundle,
        requested_at=COMMITTED_AT,
    )
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="invalid causal time",
    ):
        _verify_receipt(backdated)

    same_second_status = _receipt_bundle(
        bundle,
        current_status_issued_at=RECEIPT_ISSUED_AT,
    )
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="invalid causal time",
    ):
        _verify_receipt(same_second_status)

    overlong = _receipt_bundle(
        bundle,
        expires_at=(
            RECEIPT_ISSUED_AT
            + PRODUCTION_RESERVATION_AUTHENTICATED_HEAD_RECEIPT_MAX_VALIDITY
            + timedelta(seconds=1)
        ),
    )
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="stale or overlong",
    ):
        _verify_receipt(overlong)

    expired_anchor = _authority_anchor(valid_until_utc=_utc(CHECKED_AT))
    expired_key = _receipt_bundle(bundle, authority_anchor=expired_anchor)
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="key is not valid across observation, issue, and check",
    ):
        _verify_receipt(expired_key)

    promoted_document = deepcopy(receipt["document"])
    promoted_document["external_serializable_registry_commit_verified"] = True
    promoted_document["registry_head_compare_and_set_committed"] = True
    promoted, promoted_raw = _resign_receipt(promoted_document)
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="fields are omitted or transplanted",
    ):
        _verify_receipt(
            {**receipt, "document": promoted, "raw": promoted_raw}
        )


@pytest.mark.parametrize("denial_kind", ["key", "artifact", "supersession"])
def test_supplied_reverified_status_tail_denials_apply_to_receipt_authority(
    tmp_path: Path,
    denial_kind: str,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "energy_force")
    kwargs: dict[str, object]
    if denial_kind == "key":
        kwargs = {
            "current_revoked_key_rows": (
                {
                    "role": "external_head_receipt_authority",
                    "key_id": AUTHORITY_KEY_ID,
                    "revoked_at_utc": _utc(OBSERVED_AT),
                    "reason_code": "compromised",
                },
            )
        }
    elif denial_kind == "artifact":
        kwargs = {
            "current_revoked_artifact_rows": (
                {
                    "artifact_kind": "external_head_receipt_authority",
                    "artifact_sha256": AUTHORITY_IDENTITY_SHA256,
                    "revoked_at_utc": _utc(OBSERVED_AT),
                    "reason_code": "compromised",
                },
            )
        }
    else:
        kwargs = {
            "current_supersession_rows": (
                {
                    "artifact_kind": "external_head_receipt_service",
                    "superseded_sha256": AUTHORITY_BINARY_SHA256,
                    "replacement_sha256": "47" * 32,
                    "superseded_at_utc": _utc(OBSERVED_AT),
                },
            )
        }
    receipt = _receipt_bundle(bundle, **kwargs)  # type: ignore[arg-type]
    message = "authority key is revoked" if denial_kind == "key" else "revoked or superseded"
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match=message,
    ):
        _verify_receipt(receipt)


def test_post_receipt_status_can_revoke_the_exact_signed_receipt(
    tmp_path: Path,
) -> None:
    bundle = _scenario_and_proof(tmp_path, "energy_force")
    receipt = _receipt_bundle(bundle)
    document = receipt["document"]
    assert isinstance(document, dict)
    receipt_sha256 = document["head_receipt_sha256"]
    assert isinstance(receipt_sha256, str)
    receipt["current_registry_arguments"] = _current_registry_arguments(
        bundle,
        revoked_artifact_rows=(
            {
                "artifact_kind": "external_authenticated_head_receipt",
                "artifact_sha256": receipt_sha256,
                "revoked_at_utc": _utc(CURRENT_STATUS_ISSUED_AT),
                "reason_code": "compromised",
            },
        ),
    )
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="revoked or superseded",
    ):
        _verify_receipt(receipt)


def test_contract_rejects_bool_alias_and_module_has_no_builder_or_signer() -> None:
    contract = validation_production_reservation_authenticated_head_receipt_contract_document()
    contract["transport"]["maximum_bytes"] = True
    with pytest.raises(
        ValidationProductionReservationAuthenticatedHeadReceiptError,
        match="does not match",
    ):
        require_validation_production_reservation_authenticated_head_receipt_contract_document(
            contract
        )

    import betelgeuze_engine_v2.physics.validation_production_reservation_authenticated_head_receipt as module

    public = set(module.__all__)
    assert not any(name.startswith("build_") for name in public)
    assert not any(name.startswith("sign_") for name in public)
    assert not any("private" in name.lower() for name in public)
