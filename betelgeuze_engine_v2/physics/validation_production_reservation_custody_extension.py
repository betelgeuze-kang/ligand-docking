"""Claim-closed atomic-reservation custody sequence-five companion.

This additive module leaves custody-v1 and the review/authorization sequence
three/four extension unchanged.  It binds one exact lane-local durable nonce
record to the complete raw sequence-one-through-four prefix, then verifies
registry and checkpoint-witness signatures over a claimed external commit.
Those signatures are attestations, not independent proof of serializable
compare-and-set, one-use consumption, or successor uniqueness.  The package
does not provide or provision that registry, its keys, a commit proof, an
environment receipt, execution, results, or any scientific/product claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    ed25519_public_key_bytes,
    sign_ed25519,
    verify_ed25519,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_nonce_reservation import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
    ReferenceMinimizationValidationNonceReservation,
    ReferenceMinimizationValidationNonceReservationError,
    verify_reference_minimization_validation_nonce_reservation_record,
)
from betelgeuze_engine_v2.physics.reference_validation_nonce_reservation import (
    FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
    REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
    ReferenceValidationNonceReservation,
    ReferenceValidationNonceReservationError,
    verify_reference_validation_nonce_reservation_record,
)
from betelgeuze_engine_v2.physics.validation_production_evidence_custody import (
    CustodyRoleTrustAnchor,
    PRODUCTION_EVIDENCE_CLASS,
)
from betelgeuze_engine_v2.physics.validation_production_review_authorization_custody_extension import (
    FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256,
    PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_LANES,
    ProductionReviewAuthorizationCustodyExtensionEventVerification,
    ValidationProductionReviewAuthorizationCustodyExtensionError,
    verify_signed_production_authorization_custody_extension_event,
)


VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SCHEMA_ID = "betelgeuze.engine_v2_validation_production_reservation_custody_extension_contract/7.0.0"
VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_ID = (
    "engine_v2_synthetic_validation_production_reservation_custody_extension/7.0.0"
)
VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_VERSION = "7.0.0"
VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_FROZEN_AT_UTC = (
    "2026-07-24T19:10:00Z"
)
PRODUCTION_RESERVATION_INTENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_production_reservation_intent/1.0.0"
)
PRODUCTION_ATOMIC_RESERVATION_COMMIT_SCHEMA_ID = (
    "betelgeuze.engine_v2_production_atomic_reservation_commit/1.0.0"
)
PRODUCTION_RESERVATION_CUSTODY_SIGNATURE_ALGORITHM = "ed25519"
PRODUCTION_RESERVATION_CUSTODY_SEQUENCE = 5
PRODUCTION_RESERVATION_INTENT_MAX_VALIDITY = timedelta(hours=1)
PRODUCTION_RESERVATION_STATUS_MAX_AGE = timedelta(hours=24)
PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES = 4 * 1024 * 1024
PRODUCTION_RESERVATION_MAX_RECORD_BYTES = 65_536
PRODUCTION_RESERVATION_MAX_TRUST_ANCHORS = 4096
PRODUCTION_RESERVATION_MAX_STATUS_LINEAGE_ITEMS = 64
PRODUCTION_RESERVATION_MAX_JSON_DEPTH = 128
PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE = 2**63 - 1

FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256 = (
    "ae9968d6a92b2b841fb4d50dab084fa5e6c410bb48a9b8b81045508c5f13196e"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V6 = (
    "728d02fe4da6eb0fabf152d915bff62c154141efbeb7ca9a8b8141dd029b8ef2"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V5 = (
    "e477d99e9ce339657fd5e3965c06d4a49155a415f27ca0e3624e8cccabb2a32b"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V4 = (
    "9ccec88f2901af355aa41bc34aaf72c5629a9f2e8e94438198a94770a2c0ccf9"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V3 = (
    "52583222d95cf342d5a2aa5db575cf6936343cbc12e69982903362408d3f481f"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V2 = (
    "cf1eafa05f58320ae71a2e2a781dc801d0dcedb326d29b310c8a734daae63069"
)
FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V1 = (
    "b9f63eefaf4277a1e93463a6192fc03e2d2cc99aaddd7748ad4da5e3e58b7ce9"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,200}$")
_VERIFICATION_SEAL = object()
_CLAIM_POLICY = {
    "production_validation_execution_authorized": False,
    "production_validation_results_collected": False,
    "force_or_energy_validated": False,
    "minimization_validated": False,
    "scientifically_validated": False,
    "parameter_fitting_proposal_authorized": False,
    "parameter_fitting_authorized": False,
    "benchmark_validated": False,
    "product_qualified": False,
    "customer_execution_enabled": False,
    "claim_safe": False,
}
_BLOCKERS = (
    "external_serializable_reservation_registry_not_provisioned",
    "reservation_registry_authority_key_not_provisioned",
    "reservation_checkpoint_witness_key_not_provisioned",
    "production_reservation_intent_not_provisioned",
    "production_atomic_reservation_commit_not_provisioned",
    "production_permit_one_use_commit_not_observed",
    "external_custody_successor_uniqueness_not_observed",
    "external_registry_non_equivocation_proof_not_provisioned",
    "registry_epoch_transition_continuity_not_provisioned",
    "same_uid_local_reservation_replacement_resistance_not_established",
    "environment_and_later_custody_stages_not_implemented",
    "production_validation_result_not_collected",
    "two_production_cpu_hosts_missing",
    "independent_human_result_review_missing",
)
_RAW_SEQUENCE_FOUR_PREFIX_FIELDS = {
    "raw_authorization_carrier_bytes",
    "raw_authorization_receipt_bytes",
    "raw_review_attestation_bytes",
    "raw_pre_execution_review_carrier_bytes",
    "raw_sequence_three_custody_event_bytes",
    "raw_permit_bytes",
    "raw_status_lineage_bytes",
    "raw_sequence_one_custody_event_bytes",
    "raw_sequence_two_custody_event_bytes",
    "raw_sequence_four_custody_event_bytes",
}
_SEQUENCE_FOUR_REVERIFICATION_ARGUMENT_FIELDS = {
    "base_reverification_arguments",
    "stage3_reverification_arguments",
    "sequence_three_event_reverification_arguments",
    "stage4_reverification_arguments",
    "sequence_four_event_reverification_arguments",
}
_SIGNED_PREFIX_BYTE_FIELDS = _RAW_SEQUENCE_FOUR_PREFIX_FIELDS - {
    "raw_status_lineage_bytes",
}
_LANE_RESERVATION_IDENTITIES = {
    "energy_force": (
        REFERENCE_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
        FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
    ),
    "minimization": (
        REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_SCHEMA_ID,
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256,
    ),
}


class ValidationProductionReservationCustodyExtensionError(ValueError):
    """The reservation intent, commit, trust, prefix, or contract is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation custody value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_token(value: object, *, name: str) -> str:
    if type(value) is not str or not _TOKEN_RE.fullmatch(value):
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be a bounded token"
        )
    return value


def _require_exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if (
        type(value) is not int
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        bound = "" if maximum is None else f" and <= {maximum}"
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be an exact integer >= {minimum}{bound}"
        )
    return value


def _require_lane(value: object) -> str:
    if value not in PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_LANES:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation custody lane is unsupported"
        )
    return str(value)


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be timezone-aware"
        )
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must use second resolution"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if type(value) is not str:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be second-resolution UTC"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be second-resolution UTC"
        ) from exc
    return parsed


def _json_depth(value: object, *, depth: int = 0) -> int:
    if depth > PRODUCTION_RESERVATION_MAX_JSON_DEPTH:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation custody JSON exceeds its depth bound"
        )
    if type(value) is dict:
        return max(
            [depth] + [_json_depth(item, depth=depth + 1) for item in value.values()]
        )
    if type(value) in (list, tuple):
        return max([depth] + [_json_depth(item, depth=depth + 1) for item in value])
    return depth


def _require_bounded_json_nesting(raw: bytes, *, name: str) -> None:
    """Reject excessive container depth before invoking the JSON decoder."""

    depth = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 0x5C:
                escaped = True
            elif byte == 0x22:
                in_string = False
            continue
        if byte == 0x22:
            in_string = True
        elif byte in (0x7B, 0x5B):
            depth += 1
            if depth > PRODUCTION_RESERVATION_MAX_JSON_DEPTH:
                raise ValidationProductionReservationCustodyExtensionError(
                    f"{name} exceeds the fixed JSON nesting bound"
                )
        elif byte in (0x7D, 0x5D):
            depth -= 1
            if depth < 0:
                break


def _load_canonical_document(
    source: object,
    *,
    name: str,
    maximum: int = PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES,
) -> tuple[bytes, dict[str, Any]]:
    if type(source) is not bytes or not source or len(source) > maximum:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be non-empty bounded bytes"
        )
    _require_bounded_json_nesting(source, name=name)

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValidationProductionReservationCustodyExtensionError(
                    f"{name} contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        loaded = json.loads(source.decode("ascii"), object_pairs_hook=reject_duplicates)
    except ValidationProductionReservationCustodyExtensionError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be canonical ASCII JSON"
        ) from exc
    if type(loaded) is not dict or source != _canonical_bytes(loaded):
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} must be exact canonical JSON bytes"
        )
    _json_depth(loaded)
    return source, loaded


def _exact_raw_prefix(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != _RAW_SEQUENCE_FOUR_PREFIX_FIELDS:
        raise ValidationProductionReservationCustodyExtensionError(
            "raw sequence-four prefix fields are not exact"
        )
    prefix = dict(value)
    for name in _SIGNED_PREFIX_BYTE_FIELDS:
        source = prefix[name]
        if type(source) is not bytes or not source:
            raise ValidationProductionReservationCustodyExtensionError(
                f"{name} must be non-empty bytes"
            )
    lineage = prefix["raw_status_lineage_bytes"]
    if (
        type(lineage) not in (list, tuple)
        or not lineage
        or len(lineage) > PRODUCTION_RESERVATION_MAX_STATUS_LINEAGE_ITEMS
        or any(type(item) is not bytes or not item for item in lineage)
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "raw status lineage must be a non-empty bounded bytes sequence"
        )
    prefix["raw_status_lineage_bytes"] = tuple(lineage)
    return prefix


def _exact_sequence_four_arguments(value: object) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != _SEQUENCE_FOUR_REVERIFICATION_ARGUMENT_FIELDS
        or any(type(item) is not dict for item in value.values())
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "sequence-four reverification argument fields are not exact"
        )
    return dict(value)


def _verify_sequence_four(
    *,
    raw_prefix: object,
    reverification_arguments: object,
    expected_run_context: dict[str, object],
    checked_at: datetime,
) -> tuple[
    ProductionReviewAuthorizationCustodyExtensionEventVerification,
    dict[str, object],
    dict[str, object],
]:
    prefix = _exact_raw_prefix(raw_prefix)
    arguments = _exact_sequence_four_arguments(reverification_arguments)
    if type(expected_run_context) is not dict:
        raise ValidationProductionReservationCustodyExtensionError(
            "expected run context must be an exact dict"
        )
    try:
        verification = verify_signed_production_authorization_custody_extension_event(
            prefix["raw_sequence_four_custody_event_bytes"],  # type: ignore[arg-type]
            raw_authorization_carrier_bytes=prefix["raw_authorization_carrier_bytes"],  # type: ignore[arg-type]
            raw_authorization_receipt_bytes=prefix["raw_authorization_receipt_bytes"],  # type: ignore[arg-type]
            raw_review_attestation_bytes=prefix["raw_review_attestation_bytes"],  # type: ignore[arg-type]
            raw_pre_execution_review_carrier_bytes=prefix[
                "raw_pre_execution_review_carrier_bytes"
            ],  # type: ignore[arg-type]
            raw_sequence_three_custody_event_bytes=prefix[
                "raw_sequence_three_custody_event_bytes"
            ],  # type: ignore[arg-type]
            raw_permit_bytes=prefix["raw_permit_bytes"],  # type: ignore[arg-type]
            raw_status_lineage_bytes=prefix["raw_status_lineage_bytes"],  # type: ignore[arg-type]
            raw_sequence_one_custody_event_bytes=prefix[
                "raw_sequence_one_custody_event_bytes"
            ],  # type: ignore[arg-type]
            raw_sequence_two_custody_event_bytes=prefix[
                "raw_sequence_two_custody_event_bytes"
            ],  # type: ignore[arg-type]
            expected_run_context=expected_run_context,
            base_reverification_arguments=arguments["base_reverification_arguments"],  # type: ignore[arg-type]
            stage3_reverification_arguments=arguments[
                "stage3_reverification_arguments"
            ],  # type: ignore[arg-type]
            sequence_three_event_reverification_arguments=arguments[
                "sequence_three_event_reverification_arguments"
            ],  # type: ignore[arg-type]
            stage4_reverification_arguments=arguments[
                "stage4_reverification_arguments"
            ],  # type: ignore[arg-type]
            event_reverification_arguments=arguments[
                "sequence_four_event_reverification_arguments"
            ],  # type: ignore[arg-type]
            checked_at=checked_at,
        )
    except ValidationProductionReviewAuthorizationCustodyExtensionError as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "raw sequence-one-through-four prefix re-verification failed"
        ) from exc
    return verification, prefix, arguments


def _status_document(prefix: dict[str, object]) -> dict[str, Any]:
    lineage = prefix["raw_status_lineage_bytes"]
    if type(lineage) is not tuple or not lineage:
        raise ValidationProductionReservationCustodyExtensionError(
            "verified status lineage is unavailable"
        )
    _raw, document = _load_canonical_document(
        lineage[-1],
        name="current raw status snapshot",
    )
    _require_exact_int(
        document.get("status_sequence"), name="status sequence", minimum=1
    )
    return document


def _contract_bundle_contains_extension(run_context: dict[str, object]) -> None:
    if type(run_context) is not dict:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation run context must be an exact built-in dict"
        )
    rows = run_context.get("contract_bundle_sha256_rows")
    if type(rows) is dict:
        observed = rows.get(
            VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_ID
        )
    elif type(rows) in (list, tuple):
        matches = [
            row
            for row in rows
            if type(row) is dict
            and row.get("contract_id")
            == VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_ID
        ]
        observed = matches[0].get("sha256") if len(matches) == 1 else None
    else:
        observed = None
    if observed != (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "production permit bundle does not bind the reservation extension"
        )


def _verify_lane_reservation_record(
    *,
    lane: str,
    raw_reservation_record_bytes: object,
    expected_authorization_nonce_sha256: str,
) -> (
    ReferenceValidationNonceReservation
    | ReferenceMinimizationValidationNonceReservation
):
    if (
        type(raw_reservation_record_bytes) is not bytes
        or not raw_reservation_record_bytes
        or len(raw_reservation_record_bytes) > PRODUCTION_RESERVATION_MAX_RECORD_BYTES
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "raw lane reservation record must be bounded bytes"
        )
    try:
        if lane == "energy_force":
            return verify_reference_validation_nonce_reservation_record(
                raw_reservation_record_bytes,
                expected_authorization_nonce_sha256=(
                    expected_authorization_nonce_sha256
                ),
            )
        return verify_reference_minimization_validation_nonce_reservation_record(
            raw_reservation_record_bytes,
            expected_authorization_nonce_sha256=expected_authorization_nonce_sha256,
        )
    except (
        ReferenceValidationNonceReservationError,
        ReferenceMinimizationValidationNonceReservationError,
    ) as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "raw lane reservation record verification failed"
        ) from exc


def _cross_bind_reservation(
    *,
    lane: str,
    record: ReferenceValidationNonceReservation
    | ReferenceMinimizationValidationNonceReservation,
    sequence_four: ProductionReviewAuthorizationCustodyExtensionEventVerification,
    prefix: dict[str, object],
    run_context: dict[str, object],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _raw_authorization, authorization = _load_canonical_document(
        prefix["raw_authorization_receipt_bytes"],
        name="raw upstream authorization receipt",
    )
    _raw_carrier, authorization_carrier = _load_canonical_document(
        prefix["raw_authorization_carrier_bytes"],
        name="raw production authorization carrier",
    )
    _raw_permit, permit = _load_canonical_document(
        prefix["raw_permit_bytes"],
        name="raw production permit",
    )
    expected_schema, expected_contract = _LANE_RESERVATION_IDENTITIES[lane]
    record_document = record.to_dict()
    expected_pairs = {
        "schema_id": expected_schema,
        "contract_sha256": expected_contract,
        "authorization_receipt_sha256": (
            sequence_four.upstream_authorization_receipt_sha256
        ),
        "review_attestation_sha256": sequence_four.upstream_review_attestation_sha256,
        "authorization_operator_identity_sha256": (
            authorization_carrier.get("upstream_authorization_operator_identity_sha256")
        ),
        "authorization_nonce_sha256": sequence_four.authorization_nonce_sha256,
        "code_commit_sha": run_context.get("code_commit_sha"),
        "runner_source_sha256": authorization.get("runner_source_sha256"),
        "execution_environment_contract_sha256": authorization.get(
            "execution_environment_contract_sha256"
        ),
        "result_receipt_contract_sha256": authorization.get(
            "result_receipt_contract_sha256"
        ),
        "authorization_issued_at_utc": authorization.get("issued_at_utc"),
        "authorization_expires_at_utc": authorization.get("expires_at_utc"),
    }
    if any(
        _canonical_bytes(record_document.get(name)) != _canonical_bytes(expected)
        for name, expected in expected_pairs.items()
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "lane reservation record is cross-wired to sequence four"
        )
    expected_dependencies = authorization.get("dependency_artifact_sha256_rows")
    if _canonical_bytes(record_document.get("dependency_artifact_sha256_rows")) != (
        _canonical_bytes(expected_dependencies)
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "lane reservation dependencies are cross-wired"
        )
    if (
        authorization_carrier.get("upstream_authorization_receipt_sha256")
        != record.authorization_receipt_sha256
        or permit.get("authorization_nonce_sha256") != record.authorization_nonce_sha256
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation authorization or permit nonce is cross-wired"
        )
    return authorization, authorization_carrier, permit


def _slot_sha256(
    *,
    realm_identity_sha256: str,
    kind: str,
    value: object,
) -> str:
    return _sha256(
        {
            "registry_realm_identity_sha256": realm_identity_sha256,
            "slot_kind": kind,
            "slot_value": value,
        }
    )


def _closed_claims(payload: Mapping[str, Any]) -> None:
    if any(
        payload.get(name) is not expected for name, expected in _CLAIM_POLICY.items()
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation custody artifact attempts claim promotion"
        )


@dataclass(frozen=True, slots=True)
class ProductionReservationRegistryTrustAnchor:
    registry_identity_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "registry_identity_sha256",
            _require_sha256(
                self.registry_identity_sha256,
                name="reservation registry identity",
            ),
        )
        object.__setattr__(
            self,
            "registry_realm_identity_sha256",
            _require_sha256(
                self.registry_realm_identity_sha256,
                name="reservation registry trust realm identity",
            ),
        )
        object.__setattr__(
            self,
            "registry_epoch",
            _require_token(
                self.registry_epoch,
                name="reservation registry trust epoch",
            ),
        )
        if type(self.verification_key) is not bytes or len(self.verification_key) != 32:
            raise ValidationProductionReservationCustodyExtensionError(
                "reservation registry trust key must be 32 public-key bytes"
            )


@dataclass(frozen=True, slots=True)
class ProductionReservationWitnessTrustAnchor:
    witness_identity_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "witness_identity_sha256",
            _require_sha256(
                self.witness_identity_sha256,
                name="reservation checkpoint witness identity",
            ),
        )
        object.__setattr__(
            self,
            "registry_realm_identity_sha256",
            _require_sha256(
                self.registry_realm_identity_sha256,
                name="reservation witness trust realm identity",
            ),
        )
        object.__setattr__(
            self,
            "registry_epoch",
            _require_token(
                self.registry_epoch,
                name="reservation witness trust epoch",
            ),
        )
        if type(self.verification_key) is not bytes or len(self.verification_key) != 32:
            raise ValidationProductionReservationCustodyExtensionError(
                "reservation witness trust key must be 32 public-key bytes"
            )


@dataclass(frozen=True, slots=True, init=False)
class ProductionReservationIntentVerification:
    intent_sha256: str
    raw_intent_sha256: str
    raw_intent_byte_count: int
    lane: str
    permit_sha256: str
    study_id_sha256: str
    run_id_sha256: str
    authorization_nonce_sha256: str
    prior_custody_event_sha256: str
    prior_raw_custody_event_sha256: str
    reservation_record_sha256: str
    raw_reservation_record_sha256: str
    raw_reservation_record_byte_count: int
    current_status_snapshot_sha256: str
    current_status_checkpoint_sha256: str
    current_status_sequence: int
    external_launch_nonce_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    expected_prior_registry_sequence: int
    expected_prior_registry_checkpoint_sha256: str
    registry_authority_identity_sha256: str
    registry_authority_key_id: str
    registry_authority_public_key_sha256: str
    checkpoint_witness_identity_sha256: str
    checkpoint_witness_key_id: str
    checkpoint_witness_public_key_sha256: str
    from_role: str
    from_role_identity_sha256: str
    from_key_id: str
    from_public_key_sha256: str
    signed_at_utc: str
    expires_at_utc: str
    reservation_intent_verified: bool = True
    production_validation_execution_authorized: bool = False
    production_validation_results_collected: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _new_intent_verification(
    **values: object,
) -> ProductionReservationIntentVerification:
    instance = object.__new__(ProductionReservationIntentVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    object.__setattr__(instance, "reservation_intent_verified", True)
    object.__setattr__(instance, "production_validation_execution_authorized", False)
    object.__setattr__(instance, "production_validation_results_collected", False)
    object.__setattr__(instance, "scientifically_validated", False)
    object.__setattr__(instance, "parameter_fitting_authorized", False)
    object.__setattr__(instance, "product_qualified", False)
    object.__setattr__(instance, "claim_safe", False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def _intent_projection(
    *,
    sequence_four: ProductionReviewAuthorizationCustodyExtensionEventVerification,
    raw_sequence_four_bytes: bytes,
    record: ReferenceValidationNonceReservation
    | ReferenceMinimizationValidationNonceReservation,
    raw_reservation_record_bytes: bytes,
    run_context: dict[str, object],
    status_document: dict[str, Any],
    external_launch_nonce_sha256: str,
    registry_realm_identity_sha256: str,
    registry_epoch: str,
    expected_prior_registry_sequence: int,
    expected_prior_registry_checkpoint_sha256: str,
    expected_registry_authority_identity_sha256: str,
    expected_registry_authority_key_id: str,
    expected_registry_authority_public_key_sha256: str,
    expected_checkpoint_witness_identity_sha256: str,
    expected_checkpoint_witness_key_id: str,
    expected_checkpoint_witness_public_key_sha256: str,
    signed_at_utc: str,
    expires_at_utc: str,
) -> dict[str, Any]:
    return {
        "schema_id": PRODUCTION_RESERVATION_INTENT_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        ),
        "evidence_class": PRODUCTION_EVIDENCE_CLASS,
        "artifact_stage": "reservation",
        "requested_custody_sequence": PRODUCTION_RESERVATION_CUSTODY_SEQUENCE,
        "lane": sequence_four.lane,
        "permit_sha256": sequence_four.permit_sha256,
        "study_id_sha256": sequence_four.study_id_sha256,
        "run_id_sha256": sequence_four.run_id_sha256,
        "authorization_nonce_sha256": sequence_four.authorization_nonce_sha256,
        "run_context_sha256": _sha256(run_context),
        "process_launch_identity_sha256": sequence_four.process_launch_identity_sha256,
        "prior_custody_event_sha256": sequence_four.custody_event_sha256,
        "prior_raw_custody_event_sha256": _raw_sha256(raw_sequence_four_bytes),
        "prior_custody_received_at_utc": sequence_four.received_at_utc,
        "reservation_record_schema_id": _LANE_RESERVATION_IDENTITIES[
            sequence_four.lane
        ][0],
        "reservation_contract_sha256": _LANE_RESERVATION_IDENTITIES[sequence_four.lane][
            1
        ],
        "reservation_record_sha256": record.reservation_record_sha256,
        "raw_reservation_record_sha256": _raw_sha256(raw_reservation_record_bytes),
        "raw_reservation_record_byte_count": len(raw_reservation_record_bytes),
        "reservation_reserved_at_utc": record.reserved_at_utc,
        "lane_record_claims_local_atomic_persistence": True,
        "local_nonce_record_atomic_persistence_independently_verified": False,
        "local_nonce_record_is_external_serializable_cas": False,
        "upstream_review_attestation_sha256": (
            sequence_four.upstream_review_attestation_sha256
        ),
        "upstream_authorization_receipt_sha256": (
            sequence_four.upstream_authorization_receipt_sha256
        ),
        "current_status_snapshot_sha256": status_document.get("snapshot_sha256"),
        "current_status_checkpoint_sha256": status_document.get(
            "external_log_checkpoint_sha256"
        ),
        "current_status_sequence": status_document.get("status_sequence"),
        "external_launch_nonce_sha256": _require_sha256(
            external_launch_nonce_sha256,
            name="external launch nonce",
        ),
        "registry_realm_identity_sha256": _require_sha256(
            registry_realm_identity_sha256,
            name="reservation registry realm identity",
        ),
        "registry_epoch": _require_token(
            registry_epoch,
            name="reservation registry epoch",
        ),
        "expected_prior_registry_sequence": _require_exact_int(
            expected_prior_registry_sequence,
            name="expected prior registry sequence",
            maximum=PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE - 1,
        ),
        "expected_prior_registry_checkpoint_sha256": _require_sha256(
            expected_prior_registry_checkpoint_sha256,
            name="expected prior registry checkpoint",
        ),
        "registry_authority_identity_sha256": _require_sha256(
            expected_registry_authority_identity_sha256,
            name="expected reservation registry authority identity",
        ),
        "registry_authority_key_id": _require_token(
            expected_registry_authority_key_id,
            name="expected reservation registry authority key id",
        ),
        "registry_authority_public_key_sha256": _require_sha256(
            expected_registry_authority_public_key_sha256,
            name="expected reservation registry authority public key",
        ),
        "checkpoint_witness_identity_sha256": _require_sha256(
            expected_checkpoint_witness_identity_sha256,
            name="expected reservation checkpoint witness identity",
        ),
        "checkpoint_witness_key_id": _require_token(
            expected_checkpoint_witness_key_id,
            name="expected reservation checkpoint witness key id",
        ),
        "checkpoint_witness_public_key_sha256": _require_sha256(
            expected_checkpoint_witness_public_key_sha256,
            name="expected reservation checkpoint witness public key",
        ),
        "permit_uniqueness_slot_sha256": _slot_sha256(
            realm_identity_sha256=registry_realm_identity_sha256,
            kind="permit",
            value=sequence_four.permit_sha256,
        ),
        "authorization_nonce_uniqueness_slot_sha256": _slot_sha256(
            realm_identity_sha256=registry_realm_identity_sha256,
            kind="authorization_nonce",
            value=sequence_four.authorization_nonce_sha256,
        ),
        "predecessor_successor_uniqueness_slot_sha256": _slot_sha256(
            realm_identity_sha256=registry_realm_identity_sha256,
            kind="predecessor_logical_and_raw",
            value={
                "logical_sha256": sequence_four.custody_event_sha256,
                "raw_sha256": _raw_sha256(raw_sequence_four_bytes),
            },
        ),
        "from_role": sequence_four.to_role,
        "from_role_identity_sha256": sequence_four.to_role_identity_sha256,
        "from_key_id": sequence_four.to_key_id,
        "from_public_key_sha256": sequence_four.to_public_key_sha256,
        "signed_at_utc": signed_at_utc,
        "expires_at_utc": expires_at_utc,
        "full_raw_sequence_one_through_four_reverified": True,
        "lane_reservation_record_reverified": True,
        "external_registry_commit_present": False,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }


def _intent_times(
    *,
    projection: dict[str, Any],
    authorization_document: dict[str, Any],
    authorization_carrier_document: dict[str, Any],
    permit_document: dict[str, Any],
    status_document: dict[str, Any],
) -> None:
    received = _parse_utc(
        projection["prior_custody_received_at_utc"],
        name="sequence-four received_at",
    )
    reserved = _parse_utc(
        projection["reservation_reserved_at_utc"],
        name="reservation reserved_at",
    )
    signed = _parse_utc(projection["signed_at_utc"], name="intent signed_at")
    expires = _parse_utc(projection["expires_at_utc"], name="intent expires_at")
    authorization_expires = _parse_utc(
        authorization_document.get("expires_at_utc"),
        name="upstream authorization expires_at",
    )
    carrier_expires = _parse_utc(
        authorization_carrier_document.get("expires_at_utc"),
        name="production authorization carrier expires_at",
    )
    permit_expires = _parse_utc(
        permit_document.get("expires_at_utc"),
        name="production permit expires_at",
    )
    status_issued = _parse_utc(
        status_document.get("issued_at_utc"),
        name="current status issued_at",
    )
    if not received <= reserved <= signed < expires:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent causal time ordering is invalid"
        )
    if expires - signed > PRODUCTION_RESERVATION_INTENT_MAX_VALIDITY:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent validity exceeds its bound"
        )
    if expires > min(authorization_expires, carrier_expires, permit_expires):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent escapes an ancestor validity window"
        )
    if status_issued > signed or (
        signed - status_issued > PRODUCTION_RESERVATION_STATUS_MAX_AGE
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent status fence is stale or future-dated"
        )


def _require_intent_authority_separation(projection: dict[str, Any]) -> None:
    identity_values = {
        projection["from_role_identity_sha256"],
        projection["registry_authority_identity_sha256"],
        projection["checkpoint_witness_identity_sha256"],
    }
    key_id_values = {
        projection["from_key_id"],
        projection["registry_authority_key_id"],
        projection["checkpoint_witness_key_id"],
    }
    public_key_values = {
        projection["from_public_key_sha256"],
        projection["registry_authority_public_key_sha256"],
        projection["checkpoint_witness_public_key_sha256"],
    }
    if (
        len(identity_values) != 3
        or len(key_id_values) != 3
        or len(public_key_values) != 3
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent custody, registry, and witness roles are not separated"
        )


def _intent_signature_anchor(
    *,
    payload: dict[str, Any],
    signature: object,
    trusted_custody_keys: object,
) -> CustodyRoleTrustAnchor:
    if (
        type(trusted_custody_keys) is not dict
        or not trusted_custody_keys
        or len(trusted_custody_keys) > PRODUCTION_RESERVATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent custody trust map is invalid"
        )
    if type(signature) is not dict or set(signature) != {
        "algorithm",
        "key_id",
        "value",
    }:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent signature fields are invalid"
        )
    if signature["algorithm"] != PRODUCTION_RESERVATION_CUSTODY_SIGNATURE_ALGORITHM:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent signature algorithm is unsupported"
        )
    key_id = _require_token(signature["key_id"], name="reservation intent key id")
    anchor = trusted_custody_keys.get(key_id)
    if type(anchor) is not CustodyRoleTrustAnchor:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent custody key is not trusted"
        )
    try:
        valid = verify_ed25519(
            _canonical_bytes(payload),
            signature["value"],
            anchor.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent Ed25519 verifier is unavailable"
        ) from exc
    if not valid:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent signature verification failed"
        )
    return anchor


def build_signed_production_reservation_intent(
    *,
    raw_sequence_four_prefix: dict[str, object],
    sequence_four_reverification_arguments: dict[str, object],
    raw_reservation_record_bytes: bytes,
    expected_run_context: dict[str, object],
    external_launch_nonce_sha256: str,
    registry_realm_identity_sha256: str,
    registry_epoch: str,
    expected_prior_registry_sequence: int,
    expected_prior_registry_checkpoint_sha256: str,
    expected_registry_authority_identity_sha256: str,
    expected_registry_authority_key_id: str,
    expected_registry_authority_public_key_sha256: str,
    expected_checkpoint_witness_identity_sha256: str,
    expected_checkpoint_witness_key_id: str,
    expected_checkpoint_witness_public_key_sha256: str,
    from_signing_key: bytes,
    signed_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Build a seq5 intent after re-verifying seq1-4 and the local record."""

    _contract_bundle_contains_extension(expected_run_context)
    sequence_four, prefix, arguments = _verify_sequence_four(
        raw_prefix=raw_sequence_four_prefix,
        reverification_arguments=sequence_four_reverification_arguments,
        expected_run_context=expected_run_context,
        checked_at=signed_at,
    )
    lane = _require_lane(sequence_four.lane)
    record = _verify_lane_reservation_record(
        lane=lane,
        raw_reservation_record_bytes=raw_reservation_record_bytes,
        expected_authorization_nonce_sha256=sequence_four.authorization_nonce_sha256,
    )
    authorization, authorization_carrier, permit = _cross_bind_reservation(
        lane=lane,
        record=record,
        sequence_four=sequence_four,
        prefix=prefix,
        run_context=expected_run_context,
    )
    status = _status_document(prefix)
    base_arguments = arguments["base_reverification_arguments"]
    trusted_custody_keys = base_arguments.get("trusted_custody_keys")  # type: ignore[union-attr]
    if type(trusted_custody_keys) is not dict:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent custody trust is unavailable"
        )
    anchor = trusted_custody_keys.get(sequence_four.to_key_id)
    if type(anchor) is not CustodyRoleTrustAnchor:
        raise ValidationProductionReservationCustodyExtensionError(
            "sequence-four receiver custody key is unavailable"
        )
    if (
        anchor.custody_role != sequence_four.to_role
        or anchor.role_identity_sha256 != sequence_four.to_role_identity_sha256
        or _raw_sha256(anchor.verification_key) != sequence_four.to_public_key_sha256
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent signer breaks sequence-four custody continuity"
        )
    if type(from_signing_key) is not bytes or len(from_signing_key) != 32:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent signing key must be 32 private-key bytes"
        )
    try:
        public_key = ed25519_public_key_bytes(from_signing_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent key derivation failed"
        ) from exc
    if public_key != anchor.verification_key:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent private key differs from the sequence-four receiver"
        )
    projection = _intent_projection(
        sequence_four=sequence_four,
        raw_sequence_four_bytes=prefix["raw_sequence_four_custody_event_bytes"],  # type: ignore[arg-type]
        record=record,
        raw_reservation_record_bytes=raw_reservation_record_bytes,
        run_context=expected_run_context,
        status_document=status,
        external_launch_nonce_sha256=external_launch_nonce_sha256,
        registry_realm_identity_sha256=registry_realm_identity_sha256,
        registry_epoch=registry_epoch,
        expected_prior_registry_sequence=expected_prior_registry_sequence,
        expected_prior_registry_checkpoint_sha256=(
            expected_prior_registry_checkpoint_sha256
        ),
        expected_registry_authority_identity_sha256=(
            expected_registry_authority_identity_sha256
        ),
        expected_registry_authority_key_id=expected_registry_authority_key_id,
        expected_registry_authority_public_key_sha256=(
            expected_registry_authority_public_key_sha256
        ),
        expected_checkpoint_witness_identity_sha256=(
            expected_checkpoint_witness_identity_sha256
        ),
        expected_checkpoint_witness_key_id=expected_checkpoint_witness_key_id,
        expected_checkpoint_witness_public_key_sha256=(
            expected_checkpoint_witness_public_key_sha256
        ),
        signed_at_utc=_format_utc(signed_at, name="reservation intent signed_at"),
        expires_at_utc=_format_utc(expires_at, name="reservation intent expires_at"),
    )
    _require_intent_authority_separation(projection)
    _intent_times(
        projection=projection,
        authorization_document=authorization,
        authorization_carrier_document=authorization_carrier,
        permit_document=permit,
        status_document=status,
    )
    payload = dict(projection)
    payload["intent_sha256"] = _sha256(projection)
    try:
        signature_value = sign_ed25519(_canonical_bytes(payload), from_signing_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent signing failed"
        ) from exc
    payload["signature"] = {
        "algorithm": PRODUCTION_RESERVATION_CUSTODY_SIGNATURE_ALGORITHM,
        "key_id": sequence_four.to_key_id,
        "value": signature_value,
    }
    if (
        len(_canonical_bytes(payload))
        > PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent exceeds its signed transport bound"
        )
    return payload


def verify_signed_production_reservation_intent(
    source: bytes,
    *,
    raw_sequence_four_prefix: dict[str, object],
    sequence_four_reverification_arguments: dict[str, object],
    raw_reservation_record_bytes: bytes,
    expected_run_context: dict[str, object],
    expected_intent_sha256: str,
    expected_external_launch_nonce_sha256: str,
    expected_registry_realm_identity_sha256: str,
    expected_registry_epoch: str,
    expected_prior_registry_sequence: int,
    expected_prior_registry_checkpoint_sha256: str,
    expected_registry_authority_identity_sha256: str,
    expected_registry_authority_key_id: str,
    expected_registry_authority_public_key_sha256: str,
    expected_checkpoint_witness_identity_sha256: str,
    expected_checkpoint_witness_key_id: str,
    expected_checkpoint_witness_public_key_sha256: str,
    checked_at: datetime,
) -> ProductionReservationIntentVerification:
    """Verify seq5 intent only after rebuilding its complete raw ancestry."""

    raw_intent, loaded = _load_canonical_document(
        source,
        name="raw production reservation intent",
    )
    signature = loaded.pop("signature", None)
    intent_sha256 = loaded.pop("intent_sha256", None)
    expected_intent = _require_sha256(
        expected_intent_sha256,
        name="expected reservation intent",
    )
    if intent_sha256 != expected_intent or intent_sha256 != _sha256(loaded):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent logical SHA-256 verification failed"
        )
    _contract_bundle_contains_extension(expected_run_context)
    sequence_four, prefix, arguments = _verify_sequence_four(
        raw_prefix=raw_sequence_four_prefix,
        reverification_arguments=sequence_four_reverification_arguments,
        expected_run_context=expected_run_context,
        checked_at=checked_at,
    )
    lane = _require_lane(sequence_four.lane)
    record = _verify_lane_reservation_record(
        lane=lane,
        raw_reservation_record_bytes=raw_reservation_record_bytes,
        expected_authorization_nonce_sha256=sequence_four.authorization_nonce_sha256,
    )
    authorization, authorization_carrier, permit = _cross_bind_reservation(
        lane=lane,
        record=record,
        sequence_four=sequence_four,
        prefix=prefix,
        run_context=expected_run_context,
    )
    status = _status_document(prefix)
    expected_projection = _intent_projection(
        sequence_four=sequence_four,
        raw_sequence_four_bytes=prefix["raw_sequence_four_custody_event_bytes"],  # type: ignore[arg-type]
        record=record,
        raw_reservation_record_bytes=raw_reservation_record_bytes,
        run_context=expected_run_context,
        status_document=status,
        external_launch_nonce_sha256=expected_external_launch_nonce_sha256,
        registry_realm_identity_sha256=expected_registry_realm_identity_sha256,
        registry_epoch=expected_registry_epoch,
        expected_prior_registry_sequence=expected_prior_registry_sequence,
        expected_prior_registry_checkpoint_sha256=(
            expected_prior_registry_checkpoint_sha256
        ),
        expected_registry_authority_identity_sha256=(
            expected_registry_authority_identity_sha256
        ),
        expected_registry_authority_key_id=expected_registry_authority_key_id,
        expected_registry_authority_public_key_sha256=(
            expected_registry_authority_public_key_sha256
        ),
        expected_checkpoint_witness_identity_sha256=(
            expected_checkpoint_witness_identity_sha256
        ),
        expected_checkpoint_witness_key_id=expected_checkpoint_witness_key_id,
        expected_checkpoint_witness_public_key_sha256=(
            expected_checkpoint_witness_public_key_sha256
        ),
        signed_at_utc=loaded.get("signed_at_utc"),  # type: ignore[arg-type]
        expires_at_utc=loaded.get("expires_at_utc"),  # type: ignore[arg-type]
    )
    _require_intent_authority_separation(expected_projection)
    if _canonical_bytes(loaded) != _canonical_bytes(expected_projection):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent fields are omitted, aliased, or transplanted"
        )
    _closed_claims(loaded)
    _intent_times(
        projection=expected_projection,
        authorization_document=authorization,
        authorization_carrier_document=authorization_carrier,
        permit_document=permit,
        status_document=status,
    )
    checked = _parse_utc(
        _format_utc(checked_at, name="reservation intent checked_at"),
        name="reservation intent checked_at",
    )
    if checked < _parse_utc(loaded["signed_at_utc"], name="intent signed_at"):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent is not yet valid"
        )
    if checked >= _parse_utc(loaded["expires_at_utc"], name="intent expires_at"):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent is expired"
        )
    base_arguments = arguments["base_reverification_arguments"]
    trusted_custody_keys = base_arguments.get("trusted_custody_keys")  # type: ignore[union-attr]
    anchor = _intent_signature_anchor(
        payload={**loaded, "intent_sha256": intent_sha256},
        signature=signature,
        trusted_custody_keys=trusted_custody_keys,
    )
    if (
        anchor.custody_role != sequence_four.to_role
        or anchor.role_identity_sha256 != sequence_four.to_role_identity_sha256
        or loaded["from_key_id"] != sequence_four.to_key_id
        or loaded["from_public_key_sha256"] != _raw_sha256(anchor.verification_key)
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation intent signer breaks sequence-four custody continuity"
        )
    return _new_intent_verification(
        intent_sha256=intent_sha256,
        raw_intent_sha256=_raw_sha256(raw_intent),
        raw_intent_byte_count=len(raw_intent),
        lane=lane,
        permit_sha256=sequence_four.permit_sha256,
        study_id_sha256=sequence_four.study_id_sha256,
        run_id_sha256=sequence_four.run_id_sha256,
        authorization_nonce_sha256=sequence_four.authorization_nonce_sha256,
        prior_custody_event_sha256=sequence_four.custody_event_sha256,
        prior_raw_custody_event_sha256=_raw_sha256(
            prefix["raw_sequence_four_custody_event_bytes"]  # type: ignore[arg-type]
        ),
        reservation_record_sha256=record.reservation_record_sha256,
        raw_reservation_record_sha256=_raw_sha256(raw_reservation_record_bytes),
        raw_reservation_record_byte_count=len(raw_reservation_record_bytes),
        current_status_snapshot_sha256=loaded["current_status_snapshot_sha256"],
        current_status_checkpoint_sha256=loaded["current_status_checkpoint_sha256"],
        current_status_sequence=loaded["current_status_sequence"],
        external_launch_nonce_sha256=loaded["external_launch_nonce_sha256"],
        registry_realm_identity_sha256=loaded["registry_realm_identity_sha256"],
        registry_epoch=loaded["registry_epoch"],
        expected_prior_registry_sequence=loaded["expected_prior_registry_sequence"],
        expected_prior_registry_checkpoint_sha256=loaded[
            "expected_prior_registry_checkpoint_sha256"
        ],
        registry_authority_identity_sha256=loaded[
            "registry_authority_identity_sha256"
        ],
        registry_authority_key_id=loaded["registry_authority_key_id"],
        registry_authority_public_key_sha256=loaded[
            "registry_authority_public_key_sha256"
        ],
        checkpoint_witness_identity_sha256=loaded[
            "checkpoint_witness_identity_sha256"
        ],
        checkpoint_witness_key_id=loaded["checkpoint_witness_key_id"],
        checkpoint_witness_public_key_sha256=loaded[
            "checkpoint_witness_public_key_sha256"
        ],
        from_role=loaded["from_role"],
        from_role_identity_sha256=loaded["from_role_identity_sha256"],
        from_key_id=loaded["from_key_id"],
        from_public_key_sha256=loaded["from_public_key_sha256"],
        signed_at_utc=loaded["signed_at_utc"],
        expires_at_utc=loaded["expires_at_utc"],
    )


@dataclass(frozen=True, slots=True, init=False)
class ProductionAtomicReservationCommitVerification:
    commit_sha256: str
    raw_commit_sha256: str
    raw_commit_byte_count: int
    intent_sha256: str
    raw_intent_sha256: str
    lane: str
    permit_sha256: str
    study_id_sha256: str
    run_id_sha256: str
    authorization_nonce_sha256: str
    prior_custody_event_sha256: str
    prior_raw_custody_event_sha256: str
    continuing_custody_role: str
    continuing_custody_role_identity_sha256: str
    continuing_custody_key_id: str
    continuing_custody_public_key_sha256: str
    reservation_record_sha256: str
    raw_reservation_record_sha256: str
    external_launch_nonce_sha256: str
    registry_realm_identity_sha256: str
    registry_epoch: str
    prior_registry_sequence: int
    committed_registry_sequence: int
    prior_registry_checkpoint_sha256: str
    committed_registry_checkpoint_sha256: str
    registry_transaction_sha256: str
    registry_authority_identity_sha256: str
    registry_authority_key_id: str
    registry_authority_public_key_sha256: str
    checkpoint_witness_identity_sha256: str
    checkpoint_witness_key_id: str
    checkpoint_witness_public_key_sha256: str
    committed_at_utc: str
    current_status_snapshot_sha256: str
    current_status_checkpoint_sha256: str
    current_status_sequence: int
    reservation_intent_verified: bool = True
    full_raw_sequence_one_through_four_reverified: bool = True
    current_status_descendant_reverified: bool = True
    registry_signature_verified: bool = True
    checkpoint_witness_signature_verified: bool = True
    external_serializable_registry_commit_attestation_verified: bool = True
    serializable_transaction_isolation_attested: bool = True
    status_head_compare_and_set_commit_attested: bool = True
    permit_one_use_slot_consumption_attested: bool = True
    authorization_nonce_slot_consumption_attested: bool = True
    predecessor_successor_slot_consumption_attested: bool = True
    append_only_commit_persistence_attested: bool = True
    checkpoint_witness_observed_commit_attested: bool = True
    external_serializable_registry_commit_verified: bool = False
    status_head_compare_and_set_committed: bool = False
    permit_one_use_slot_consumed: bool = False
    authorization_nonce_slot_consumed: bool = False
    predecessor_successor_slot_consumed: bool = False
    custody_successor_uniqueness_enforced: bool = False
    external_registry_non_equivocation_verified: bool = False
    registry_epoch_transition_continuity_verified: bool = False
    production_validation_execution_authorized: bool = False
    production_validation_results_collected: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _new_commit_verification(
    **values: object,
) -> ProductionAtomicReservationCommitVerification:
    instance = object.__new__(ProductionAtomicReservationCommitVerification)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    for name in (
        "reservation_intent_verified",
        "full_raw_sequence_one_through_four_reverified",
        "current_status_descendant_reverified",
        "registry_signature_verified",
        "checkpoint_witness_signature_verified",
        "external_serializable_registry_commit_attestation_verified",
        "serializable_transaction_isolation_attested",
        "status_head_compare_and_set_commit_attested",
        "permit_one_use_slot_consumption_attested",
        "authorization_nonce_slot_consumption_attested",
        "predecessor_successor_slot_consumption_attested",
        "append_only_commit_persistence_attested",
        "checkpoint_witness_observed_commit_attested",
    ):
        object.__setattr__(instance, name, True)
    for name in (
        "production_validation_execution_authorized",
        "production_validation_results_collected",
        "scientifically_validated",
        "parameter_fitting_authorized",
        "product_qualified",
        "claim_safe",
        "external_serializable_registry_commit_verified",
        "status_head_compare_and_set_committed",
        "permit_one_use_slot_consumed",
        "authorization_nonce_slot_consumed",
        "predecessor_successor_slot_consumed",
        "custody_successor_uniqueness_enforced",
        "external_registry_non_equivocation_verified",
        "registry_epoch_transition_continuity_verified",
    ):
        object.__setattr__(instance, name, False)
    object.__setattr__(instance, "_verification_seal", _VERIFICATION_SEAL)
    return instance


def _exact_registry_trust_map(
    value: object,
) -> dict[str, ProductionReservationRegistryTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_RESERVATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation registry trust map is invalid"
        )
    identities: set[str] = set()
    materials: set[bytes] = set()
    normalized: dict[str, ProductionReservationRegistryTrustAnchor] = {}
    for key_id, anchor in value.items():
        key = _require_token(key_id, name="reservation registry key id")
        if type(anchor) is not ProductionReservationRegistryTrustAnchor:
            raise ValidationProductionReservationCustodyExtensionError(
                "reservation registry trust map contains an invalid anchor"
            )
        if (
            anchor.registry_identity_sha256 in identities
            or anchor.verification_key in materials
        ):
            raise ValidationProductionReservationCustodyExtensionError(
                "reservation registry trust map contains an alias"
            )
        identities.add(anchor.registry_identity_sha256)
        materials.add(anchor.verification_key)
        normalized[key] = anchor
    return normalized


def _exact_witness_trust_map(
    value: object,
) -> dict[str, ProductionReservationWitnessTrustAnchor]:
    if (
        type(value) is not dict
        or not value
        or len(value) > PRODUCTION_RESERVATION_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation checkpoint witness trust map is invalid"
        )
    identities: set[str] = set()
    materials: set[bytes] = set()
    normalized: dict[str, ProductionReservationWitnessTrustAnchor] = {}
    for key_id, anchor in value.items():
        key = _require_token(key_id, name="reservation witness key id")
        if type(anchor) is not ProductionReservationWitnessTrustAnchor:
            raise ValidationProductionReservationCustodyExtensionError(
                "reservation witness trust map contains an invalid anchor"
            )
        if (
            anchor.witness_identity_sha256 in identities
            or anchor.verification_key in materials
        ):
            raise ValidationProductionReservationCustodyExtensionError(
                "reservation witness trust map contains an alias"
            )
        identities.add(anchor.witness_identity_sha256)
        materials.add(anchor.verification_key)
        normalized[key] = anchor
    return normalized


def _require_signature_fields(value: object, *, name: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {"algorithm", "key_id", "value"}:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} signature fields are invalid"
        )
    if value["algorithm"] != PRODUCTION_RESERVATION_CUSTODY_SIGNATURE_ALGORITHM:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} signature algorithm is unsupported"
        )
    _require_token(value["key_id"], name=f"{name} key id")
    if type(value["value"]) is not str:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} signature value is invalid"
        )
    return dict(value)


def _registry_transaction_sha256(
    *,
    intent: ProductionReservationIntentVerification,
) -> str:
    return _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_reservation_registry_transaction/1.0.0",
            "registry_realm_identity_sha256": intent.registry_realm_identity_sha256,
            "registry_epoch": intent.registry_epoch,
            "prior_registry_sequence": intent.expected_prior_registry_sequence,
            "prior_registry_checkpoint_sha256": (
                intent.expected_prior_registry_checkpoint_sha256
            ),
            "intent_sha256": intent.intent_sha256,
            "raw_intent_sha256": intent.raw_intent_sha256,
            "external_launch_nonce_sha256": intent.external_launch_nonce_sha256,
            "permit_uniqueness_slot_sha256": _slot_sha256(
                realm_identity_sha256=intent.registry_realm_identity_sha256,
                kind="permit",
                value=intent.permit_sha256,
            ),
            "authorization_nonce_uniqueness_slot_sha256": _slot_sha256(
                realm_identity_sha256=intent.registry_realm_identity_sha256,
                kind="authorization_nonce",
                value=intent.authorization_nonce_sha256,
            ),
            "predecessor_successor_uniqueness_slot_sha256": _slot_sha256(
                realm_identity_sha256=intent.registry_realm_identity_sha256,
                kind="predecessor_logical_and_raw",
                value={
                    "logical_sha256": intent.prior_custody_event_sha256,
                    "raw_sha256": intent.prior_raw_custody_event_sha256,
                },
            ),
        }
    )


def _registry_checkpoint_sha256(
    *,
    intent: ProductionReservationIntentVerification,
    registry_transaction_sha256: str,
    committed_registry_sequence: int,
    committed_at_utc: str,
) -> str:
    return _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_reservation_registry_checkpoint/1.0.0",
            "registry_realm_identity_sha256": intent.registry_realm_identity_sha256,
            "registry_epoch": intent.registry_epoch,
            "prior_registry_sequence": intent.expected_prior_registry_sequence,
            "committed_registry_sequence": committed_registry_sequence,
            "prior_registry_checkpoint_sha256": (
                intent.expected_prior_registry_checkpoint_sha256
            ),
            "registry_transaction_sha256": registry_transaction_sha256,
            "committed_at_utc": committed_at_utc,
        }
    )


def _commit_projection(
    *,
    intent: ProductionReservationIntentVerification,
    committed_at_utc: str,
) -> dict[str, Any]:
    prior_sequence = _require_exact_int(
        intent.expected_prior_registry_sequence,
        name="prior registry sequence",
        maximum=PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE - 1,
    )
    committed_sequence = prior_sequence + 1
    transaction_sha256 = _registry_transaction_sha256(intent=intent)
    checkpoint_sha256 = _registry_checkpoint_sha256(
        intent=intent,
        registry_transaction_sha256=transaction_sha256,
        committed_registry_sequence=committed_sequence,
        committed_at_utc=committed_at_utc,
    )
    return {
        "schema_id": PRODUCTION_ATOMIC_RESERVATION_COMMIT_SCHEMA_ID,
        "contract_sha256": (
            FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
        ),
        "evidence_class": PRODUCTION_EVIDENCE_CLASS,
        "artifact_stage": "atomic_reservation_commit",
        "custody_sequence": PRODUCTION_RESERVATION_CUSTODY_SEQUENCE,
        "lane": intent.lane,
        "permit_sha256": intent.permit_sha256,
        "study_id_sha256": intent.study_id_sha256,
        "run_id_sha256": intent.run_id_sha256,
        "authorization_nonce_sha256": intent.authorization_nonce_sha256,
        "prior_custody_event_sha256": intent.prior_custody_event_sha256,
        "prior_raw_custody_event_sha256": intent.prior_raw_custody_event_sha256,
        "continuing_custody_role": intent.from_role,
        "continuing_custody_role_identity_sha256": intent.from_role_identity_sha256,
        "continuing_custody_key_id": intent.from_key_id,
        "continuing_custody_public_key_sha256": intent.from_public_key_sha256,
        "reservation_record_sha256": intent.reservation_record_sha256,
        "raw_reservation_record_sha256": intent.raw_reservation_record_sha256,
        "intent_sha256": intent.intent_sha256,
        "raw_intent_sha256": intent.raw_intent_sha256,
        "raw_intent_byte_count": intent.raw_intent_byte_count,
        "external_launch_nonce_sha256": intent.external_launch_nonce_sha256,
        "registry_realm_identity_sha256": intent.registry_realm_identity_sha256,
        "registry_epoch": intent.registry_epoch,
        "prior_registry_sequence": prior_sequence,
        "committed_registry_sequence": committed_sequence,
        "prior_registry_checkpoint_sha256": (
            intent.expected_prior_registry_checkpoint_sha256
        ),
        "registry_transaction_sha256": transaction_sha256,
        "committed_registry_checkpoint_sha256": checkpoint_sha256,
        "status_fence_snapshot_sha256": intent.current_status_snapshot_sha256,
        "status_fence_checkpoint_sha256": intent.current_status_checkpoint_sha256,
        "status_fence_sequence": intent.current_status_sequence,
        "permit_uniqueness_slot_sha256": _slot_sha256(
            realm_identity_sha256=intent.registry_realm_identity_sha256,
            kind="permit",
            value=intent.permit_sha256,
        ),
        "authorization_nonce_uniqueness_slot_sha256": _slot_sha256(
            realm_identity_sha256=intent.registry_realm_identity_sha256,
            kind="authorization_nonce",
            value=intent.authorization_nonce_sha256,
        ),
        "predecessor_successor_uniqueness_slot_sha256": _slot_sha256(
            realm_identity_sha256=intent.registry_realm_identity_sha256,
            kind="predecessor_logical_and_raw",
            value={
                "logical_sha256": intent.prior_custody_event_sha256,
                "raw_sha256": intent.prior_raw_custody_event_sha256,
            },
        ),
        "registry_authority_identity_sha256": _require_sha256(
            intent.registry_authority_identity_sha256,
            name="reservation registry authority identity",
        ),
        "registry_authority_key_id": _require_token(
            intent.registry_authority_key_id,
            name="reservation registry authority key id",
        ),
        "registry_authority_public_key_sha256": _require_sha256(
            intent.registry_authority_public_key_sha256,
            name="reservation registry authority public key",
        ),
        "checkpoint_witness_identity_sha256": _require_sha256(
            intent.checkpoint_witness_identity_sha256,
            name="reservation checkpoint witness identity",
        ),
        "checkpoint_witness_key_id": _require_token(
            intent.checkpoint_witness_key_id,
            name="reservation checkpoint witness key id",
        ),
        "checkpoint_witness_public_key_sha256": _require_sha256(
            intent.checkpoint_witness_public_key_sha256,
            name="reservation checkpoint witness public key",
        ),
        "committed_at_utc": committed_at_utc,
        "sequence_five_commit_attestation_artifact": True,
        "registry_attested_outcome": "committed",
        "registry_attests_serializable_transaction_isolation": True,
        "registry_attests_status_head_compare_and_set_commit": True,
        "registry_attests_permit_one_use_slot_consumption": True,
        "registry_attests_authorization_nonce_slot_consumption": True,
        "registry_attests_predecessor_successor_slot_consumption": True,
        "registry_attests_append_only_commit_persistence": True,
        "checkpoint_witness_attests_observed_commit": True,
        "external_serializable_registry_commit_independently_verified": False,
        "status_head_compare_and_set_committed": False,
        "permit_one_use_slot_consumed": False,
        "authorization_nonce_slot_consumed": False,
        "predecessor_successor_slot_consumed": False,
        "custody_successor_uniqueness_enforced": False,
        "external_registry_backend_implemented_by_this_package": False,
        "same_uid_local_reservation_replacement_resistance_established": False,
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }


def _commit_times(
    *,
    intent: ProductionReservationIntentVerification,
    committed_at_utc: object,
) -> str:
    committed = _parse_utc(committed_at_utc, name="reservation committed_at")
    signed = _parse_utc(intent.signed_at_utc, name="reservation intent signed_at")
    expires = _parse_utc(intent.expires_at_utc, name="reservation intent expires_at")
    if not signed <= committed < expires:
        raise ValidationProductionReservationCustodyExtensionError(
            "atomic reservation commit escapes the signed intent window"
        )
    return _format_utc(committed, name="reservation committed_at")


def _derive_public_key(private_key: object, *, name: str) -> bytes:
    if type(private_key) is not bytes or len(private_key) != 32:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} signing key must be 32 private-key bytes"
        )
    try:
        return ed25519_public_key_bytes(private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            f"{name} public-key derivation failed"
        ) from exc


def build_signed_production_atomic_reservation_commit(
    *,
    raw_intent_bytes: bytes,
    raw_sequence_four_prefix: dict[str, object],
    sequence_four_reverification_arguments: dict[str, object],
    raw_reservation_record_bytes: bytes,
    expected_run_context: dict[str, object],
    expected_intent_sha256: str,
    expected_external_launch_nonce_sha256: str,
    expected_registry_realm_identity_sha256: str,
    expected_registry_epoch: str,
    expected_prior_registry_sequence: int,
    expected_prior_registry_checkpoint_sha256: str,
    registry_authority_identity_sha256: str,
    registry_authority_key_id: str,
    registry_authority_signing_key: bytes,
    checkpoint_witness_identity_sha256: str,
    checkpoint_witness_key_id: str,
    checkpoint_witness_signing_key: bytes,
    committed_at: datetime,
) -> dict[str, Any]:
    """Serialize authority attestations describing a claimed external commit.

    This function cannot establish that the claimed transaction occurred.  It
    does not contact, implement, emulate, or mutate the required external
    serializable registry.
    """

    committed_at_utc = _format_utc(committed_at, name="reservation committed_at")
    registry_public = _derive_public_key(
        registry_authority_signing_key,
        name="reservation registry authority",
    )
    witness_public = _derive_public_key(
        checkpoint_witness_signing_key,
        name="reservation checkpoint witness",
    )
    registry_identity = _require_sha256(
        registry_authority_identity_sha256,
        name="reservation registry authority identity",
    )
    witness_identity = _require_sha256(
        checkpoint_witness_identity_sha256,
        name="reservation checkpoint witness identity",
    )
    registry_key_id = _require_token(
        registry_authority_key_id,
        name="reservation registry authority key id",
    )
    witness_key_id = _require_token(
        checkpoint_witness_key_id,
        name="reservation checkpoint witness key id",
    )
    intent = verify_signed_production_reservation_intent(
        raw_intent_bytes,
        raw_sequence_four_prefix=raw_sequence_four_prefix,
        sequence_four_reverification_arguments=(sequence_four_reverification_arguments),
        raw_reservation_record_bytes=raw_reservation_record_bytes,
        expected_run_context=expected_run_context,
        expected_intent_sha256=expected_intent_sha256,
        expected_external_launch_nonce_sha256=(expected_external_launch_nonce_sha256),
        expected_registry_realm_identity_sha256=(
            expected_registry_realm_identity_sha256
        ),
        expected_registry_epoch=expected_registry_epoch,
        expected_prior_registry_sequence=expected_prior_registry_sequence,
        expected_prior_registry_checkpoint_sha256=(
            expected_prior_registry_checkpoint_sha256
        ),
        expected_registry_authority_identity_sha256=registry_identity,
        expected_registry_authority_key_id=registry_key_id,
        expected_registry_authority_public_key_sha256=_raw_sha256(registry_public),
        expected_checkpoint_witness_identity_sha256=witness_identity,
        expected_checkpoint_witness_key_id=witness_key_id,
        expected_checkpoint_witness_public_key_sha256=_raw_sha256(witness_public),
        checked_at=committed_at,
    )
    _commit_times(intent=intent, committed_at_utc=committed_at_utc)
    if (
        registry_identity in {witness_identity, intent.from_role_identity_sha256}
        or witness_identity == intent.from_role_identity_sha256
        or registry_key_id in {witness_key_id, intent.from_key_id}
        or witness_key_id == intent.from_key_id
        or registry_public == witness_public
        or _raw_sha256(registry_public) == intent.from_public_key_sha256
        or _raw_sha256(witness_public) == intent.from_public_key_sha256
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation registry and witness roles are not separated"
        )
    projection = _commit_projection(
        intent=intent,
        committed_at_utc=committed_at_utc,
    )
    payload = dict(projection)
    payload["commit_sha256"] = _sha256(projection)
    registry_signed_payload = dict(payload)
    try:
        registry_signature_value = sign_ed25519(
            _canonical_bytes(registry_signed_payload),
            registry_authority_signing_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation registry signing failed"
        ) from exc
    registry_signature = {
        "algorithm": PRODUCTION_RESERVATION_CUSTODY_SIGNATURE_ALGORITHM,
        "key_id": registry_key_id,
        "value": registry_signature_value,
    }
    witness_signed_payload = {
        **registry_signed_payload,
        "registry_signature": registry_signature,
    }
    try:
        witness_signature_value = sign_ed25519(
            _canonical_bytes(witness_signed_payload),
            checkpoint_witness_signing_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation checkpoint witness signing failed"
        ) from exc
    payload["registry_signature"] = registry_signature
    payload["checkpoint_witness_signature"] = {
        "algorithm": PRODUCTION_RESERVATION_CUSTODY_SIGNATURE_ALGORITHM,
        "key_id": witness_key_id,
        "value": witness_signature_value,
    }
    if (
        len(_canonical_bytes(payload))
        > PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "atomic reservation commit exceeds its signed transport bound"
        )
    return payload


def _require_status_descendant_prefix(
    *,
    fence_prefix: object,
    current_prefix: object,
) -> tuple[dict[str, object], dict[str, object]]:
    fence = _exact_raw_prefix(fence_prefix)
    current = _exact_raw_prefix(current_prefix)
    if any(
        fence[name] != current[name]
        for name in _RAW_SEQUENCE_FOUR_PREFIX_FIELDS
        if name != "raw_status_lineage_bytes"
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "current sequence-four prefix differs outside status lineage"
        )
    fence_lineage = fence["raw_status_lineage_bytes"]
    current_lineage = current["raw_status_lineage_bytes"]
    if (
        type(fence_lineage) is not tuple
        or type(current_lineage) is not tuple
        or len(current_lineage) < len(fence_lineage)
        or current_lineage[: len(fence_lineage)] != fence_lineage
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "current status lineage is not an exact descendant of the intent fence"
        )
    return fence, current


def _require_status_descendants_postdate_commit(
    *,
    fence_prefix: dict[str, object],
    current_prefix: dict[str, object],
    committed_at: datetime,
) -> None:
    fence_lineage = fence_prefix["raw_status_lineage_bytes"]
    current_lineage = current_prefix["raw_status_lineage_bytes"]
    if type(fence_lineage) is not tuple or type(current_lineage) is not tuple:
        raise ValidationProductionReservationCustodyExtensionError(
            "verified status lineage representation is invalid"
        )
    if len(current_lineage) <= len(fence_lineage):
        raise ValidationProductionReservationCustodyExtensionError(
            "current status lineage lacks a post-commit descendant"
        )
    for raw_status in current_lineage[len(fence_lineage) :]:
        _raw, status = _load_canonical_document(
            raw_status,
            name="post-intent raw status snapshot",
        )
        issued_at = _parse_utc(
            status.get("issued_at_utc"),
            name="post-intent status issued_at",
        )
        if issued_at <= committed_at:
            raise ValidationProductionReservationCustodyExtensionError(
                "intent status fence was stale before the attested registry commit"
            )


def _status_denials(document: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    revoked_keys: set[str] = set()
    revoked_artifacts: set[str] = set()
    superseded_artifacts: set[str] = set()
    for row in document.get("revoked_key_rows", ()):
        if type(row) is dict:
            revoked_keys.add(_require_token(row.get("key_id"), name="revoked key id"))
    for row in document.get("revoked_artifact_rows", ()):
        if type(row) is dict:
            revoked_artifacts.add(
                _require_sha256(
                    row.get("artifact_sha256"),
                    name="revoked artifact",
                )
            )
    for row in document.get("supersession_rows", ()):
        if type(row) is dict:
            superseded_artifacts.add(
                _require_sha256(
                    row.get("superseded_sha256"),
                    name="superseded artifact",
                )
            )
    return revoked_keys, revoked_artifacts, superseded_artifacts


def _collect_prior_trust_values(
    value: object,
) -> tuple[set[str], set[str], set[bytes]]:
    identities: set[str] = set()
    key_ids: set[str] = set()
    materials: set[bytes] = set()
    visited: set[int] = set()

    def visit(item: object) -> None:
        item_id = id(item)
        if item_id in visited:
            return
        if type(item) in (dict, list, tuple) or hasattr(item, "verification_key"):
            visited.add(item_id)
        verification_key = getattr(item, "verification_key", None)
        if type(verification_key) is bytes:
            materials.add(verification_key)
            for attribute in (
                "authority_identity_sha256",
                "role_identity_sha256",
                "reviewer_identity_sha256",
                "operator_identity_sha256",
            ):
                identity = getattr(item, attribute, None)
                if type(identity) is str and _SHA256_RE.fullmatch(identity):
                    identities.add(identity)
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is str and hasattr(child, "verification_key"):
                    key_ids.add(_require_token(key, name="prior trust key id"))
                if (
                    type(key) is str
                    and key.endswith("_identity_sha256")
                    and type(child) is str
                    and _SHA256_RE.fullmatch(child)
                ):
                    identities.add(child)
                if (
                    type(key) is str
                    and key.endswith("_key_id")
                    and type(child) is str
                    and _TOKEN_RE.fullmatch(child)
                ):
                    key_ids.add(child)
                visit(child)
        elif type(item) in (list, tuple):
            for child in item:
                visit(child)

    visit(value)
    return identities, key_ids, materials


def _require_new_trust_separation(
    *,
    sequence_four_reverification_arguments: dict[str, object],
    registry_trust: dict[str, ProductionReservationRegistryTrustAnchor],
    witness_trust: dict[str, ProductionReservationWitnessTrustAnchor],
) -> None:
    identities, key_ids, materials = _collect_prior_trust_values(
        sequence_four_reverification_arguments
    )
    registry_identities = {
        anchor.registry_identity_sha256 for anchor in registry_trust.values()
    }
    witness_identities = {
        anchor.witness_identity_sha256 for anchor in witness_trust.values()
    }
    registry_materials = {
        anchor.verification_key for anchor in registry_trust.values()
    }
    witness_materials = {anchor.verification_key for anchor in witness_trust.values()}
    if (
        registry_identities & (identities | witness_identities)
        or witness_identities & identities
        or set(registry_trust) & (key_ids | set(witness_trust))
        or set(witness_trust) & key_ids
        or registry_materials & (materials | witness_materials)
        or witness_materials & materials
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation registry or witness trust aliases a prior role"
        )


def _verify_commit_signatures(
    *,
    projection: dict[str, Any],
    commit_sha256: str,
    registry_signature: dict[str, Any],
    witness_signature: dict[str, Any],
    registry_anchor: ProductionReservationRegistryTrustAnchor,
    witness_anchor: ProductionReservationWitnessTrustAnchor,
) -> None:
    registry_payload = {**projection, "commit_sha256": commit_sha256}
    witness_payload = {
        **registry_payload,
        "registry_signature": registry_signature,
    }
    try:
        registry_valid = verify_ed25519(
            _canonical_bytes(registry_payload),
            registry_signature["value"],
            registry_anchor.verification_key,
        )
        witness_valid = verify_ed25519(
            _canonical_bytes(witness_payload),
            witness_signature["value"],
            witness_anchor.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionReservationCustodyExtensionError(
            "atomic reservation Ed25519 verifier is unavailable"
        ) from exc
    if not registry_valid or not witness_valid:
        raise ValidationProductionReservationCustodyExtensionError(
            "atomic reservation registry or witness signature verification failed"
        )


def verify_signed_production_atomic_reservation_commit(
    source: bytes,
    *,
    raw_intent_bytes: bytes,
    intent_raw_sequence_four_prefix: dict[str, object],
    current_raw_sequence_four_prefix: dict[str, object],
    intent_sequence_four_reverification_arguments: dict[str, object],
    current_sequence_four_reverification_arguments: dict[str, object],
    raw_reservation_record_bytes: bytes,
    expected_run_context: dict[str, object],
    expected_intent_sha256: str,
    expected_commit_sha256: str,
    expected_raw_commit_sha256: str,
    expected_external_launch_nonce_sha256: str,
    expected_registry_realm_identity_sha256: str,
    expected_registry_epoch: str,
    expected_prior_registry_sequence: int,
    expected_prior_registry_checkpoint_sha256: str,
    expected_committed_registry_sequence: int,
    expected_committed_registry_checkpoint_sha256: str,
    trusted_registry_authority_keys: dict[
        str, ProductionReservationRegistryTrustAnchor
    ],
    trusted_checkpoint_witness_keys: dict[str, ProductionReservationWitnessTrustAnchor],
    checked_at: datetime,
) -> ProductionAtomicReservationCommitVerification:
    """Verify a witnessed commit attestation against ancestry and status."""

    checked = _parse_utc(
        _format_utc(checked_at, name="atomic reservation checked_at"),
        name="atomic reservation checked_at",
    )
    raw_commit, loaded = _load_canonical_document(
        source,
        name="raw production atomic reservation commit",
    )
    if _raw_sha256(raw_commit) != _require_sha256(
        expected_raw_commit_sha256,
        name="expected raw atomic reservation commit",
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "raw atomic reservation commit identity is cross-wired"
        )
    registry_signature = _require_signature_fields(
        loaded.pop("registry_signature", None),
        name="reservation registry",
    )
    witness_signature = _require_signature_fields(
        loaded.pop("checkpoint_witness_signature", None),
        name="reservation checkpoint witness",
    )
    commit_sha256 = loaded.pop("commit_sha256", None)
    expected_commit = _require_sha256(
        expected_commit_sha256,
        name="expected atomic reservation commit",
    )
    if commit_sha256 != expected_commit or commit_sha256 != _sha256(loaded):
        raise ValidationProductionReservationCustodyExtensionError(
            "atomic reservation commit logical SHA-256 verification failed"
        )
    committed_at = _parse_utc(
        loaded.get("committed_at_utc"),
        name="atomic reservation committed_at",
    )
    if committed_at > checked:
        raise ValidationProductionReservationCustodyExtensionError(
            "atomic reservation commit is future-dated"
        )
    registry_trust = _exact_registry_trust_map(trusted_registry_authority_keys)
    witness_trust = _exact_witness_trust_map(trusted_checkpoint_witness_keys)
    registry_key_id = registry_signature["key_id"]
    witness_key_id = witness_signature["key_id"]
    registry_anchor = registry_trust.get(registry_key_id)
    witness_anchor = witness_trust.get(witness_key_id)
    if type(registry_anchor) is not ProductionReservationRegistryTrustAnchor:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation registry signature key is not trusted"
        )
    if type(witness_anchor) is not ProductionReservationWitnessTrustAnchor:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation witness signature key is not trusted"
        )
    if (
        any(
            anchor.registry_realm_identity_sha256
            != expected_registry_realm_identity_sha256
            or anchor.registry_epoch != expected_registry_epoch
            for anchor in registry_trust.values()
        )
        or any(
            anchor.registry_realm_identity_sha256
            != expected_registry_realm_identity_sha256
            or anchor.registry_epoch != expected_registry_epoch
            for anchor in witness_trust.values()
        )
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation registry or witness trust scope is cross-wired"
        )
    fence_prefix, current_prefix = _require_status_descendant_prefix(
        fence_prefix=intent_raw_sequence_four_prefix,
        current_prefix=current_raw_sequence_four_prefix,
    )
    _require_status_descendants_postdate_commit(
        fence_prefix=fence_prefix,
        current_prefix=current_prefix,
        committed_at=committed_at,
    )
    intent = verify_signed_production_reservation_intent(
        raw_intent_bytes,
        raw_sequence_four_prefix=fence_prefix,
        sequence_four_reverification_arguments=(
            intent_sequence_four_reverification_arguments
        ),
        raw_reservation_record_bytes=raw_reservation_record_bytes,
        expected_run_context=expected_run_context,
        expected_intent_sha256=expected_intent_sha256,
        expected_external_launch_nonce_sha256=(expected_external_launch_nonce_sha256),
        expected_registry_realm_identity_sha256=(
            expected_registry_realm_identity_sha256
        ),
        expected_registry_epoch=expected_registry_epoch,
        expected_prior_registry_sequence=expected_prior_registry_sequence,
        expected_prior_registry_checkpoint_sha256=(
            expected_prior_registry_checkpoint_sha256
        ),
        expected_registry_authority_identity_sha256=(
            registry_anchor.registry_identity_sha256
        ),
        expected_registry_authority_key_id=registry_key_id,
        expected_registry_authority_public_key_sha256=_raw_sha256(
            registry_anchor.verification_key
        ),
        expected_checkpoint_witness_identity_sha256=(
            witness_anchor.witness_identity_sha256
        ),
        expected_checkpoint_witness_key_id=witness_key_id,
        expected_checkpoint_witness_public_key_sha256=_raw_sha256(
            witness_anchor.verification_key
        ),
        checked_at=committed_at,
    )
    _commit_times(intent=intent, committed_at_utc=loaded["committed_at_utc"])
    current_sequence_four, _current_prefix, _arguments = _verify_sequence_four(
        raw_prefix=current_prefix,
        reverification_arguments=current_sequence_four_reverification_arguments,
        expected_run_context=expected_run_context,
        checked_at=checked,
    )
    if (
        current_sequence_four.custody_event_sha256 != intent.prior_custody_event_sha256
        or current_sequence_four.raw_event_sha256
        != intent.prior_raw_custody_event_sha256
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "current sequence-four verification differs from the intent predecessor"
        )
    _require_new_trust_separation(
        sequence_four_reverification_arguments=(
            current_sequence_four_reverification_arguments
        ),
        registry_trust=registry_trust,
        witness_trust=witness_trust,
    )
    expected_projection = _commit_projection(
        intent=intent,
        committed_at_utc=loaded["committed_at_utc"],
    )
    if _canonical_bytes(loaded) != _canonical_bytes(expected_projection):
        raise ValidationProductionReservationCustodyExtensionError(
            "atomic reservation commit fields are omitted, aliased, or transplanted"
        )
    _closed_claims(loaded)
    committed_sequence = _require_exact_int(
        loaded["committed_registry_sequence"],
        name="committed registry sequence",
        minimum=1,
        maximum=PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE,
    )
    if committed_sequence != _require_exact_int(
        expected_committed_registry_sequence,
        name="expected committed registry sequence",
        minimum=1,
        maximum=PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE,
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "committed registry sequence differs from the expected CAS result"
        )
    committed_checkpoint = _require_sha256(
        loaded["committed_registry_checkpoint_sha256"],
        name="committed registry checkpoint",
    )
    if committed_checkpoint != _require_sha256(
        expected_committed_registry_checkpoint_sha256,
        name="expected committed registry checkpoint",
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "committed registry checkpoint differs from the expected CAS result"
        )
    _verify_commit_signatures(
        projection=expected_projection,
        commit_sha256=commit_sha256,
        registry_signature=registry_signature,
        witness_signature=witness_signature,
        registry_anchor=registry_anchor,
        witness_anchor=witness_anchor,
    )
    current_status = _status_document(current_prefix)
    revoked_keys, revoked_artifacts, superseded_artifacts = _status_denials(
        current_status
    )
    if (set(registry_trust) | set(witness_trust)) & revoked_keys:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation registry or witness key is currently revoked"
        )
    status_artifact_identities: set[str] = set()
    current_lineage = current_prefix["raw_status_lineage_bytes"]
    if type(current_lineage) is not tuple:
        raise ValidationProductionReservationCustodyExtensionError(
            "verified current status lineage is unavailable"
        )
    for raw_status in current_lineage:
        _raw_status, status_document = _load_canonical_document(
            raw_status,
            name="current lineage raw status snapshot",
        )
        status_artifact_identities.update(
            {
                _require_sha256(
                    status_document.get("snapshot_sha256"),
                    name="current lineage status snapshot",
                ),
                _require_sha256(
                    status_document.get("external_log_checkpoint_sha256"),
                    name="current lineage status checkpoint",
                ),
                _raw_sha256(raw_status),
            }
        )
    new_trust_artifact_identities = {
        intent.registry_realm_identity_sha256,
        *(
            anchor.registry_identity_sha256 for anchor in registry_trust.values()
        ),
        *(
            _raw_sha256(anchor.verification_key)
            for anchor in registry_trust.values()
        ),
        *(anchor.witness_identity_sha256 for anchor in witness_trust.values()),
        *(
            _raw_sha256(anchor.verification_key)
            for anchor in witness_trust.values()
        ),
    }
    artifact_identities = {
        intent.intent_sha256,
        intent.raw_intent_sha256,
        intent.permit_sha256,
        intent.prior_custody_event_sha256,
        intent.prior_raw_custody_event_sha256,
        intent.reservation_record_sha256,
        intent.raw_reservation_record_sha256,
        commit_sha256,
        _raw_sha256(raw_commit),
        loaded["registry_transaction_sha256"],
        committed_checkpoint,
        loaded["permit_uniqueness_slot_sha256"],
        loaded["authorization_nonce_uniqueness_slot_sha256"],
        loaded["predecessor_successor_uniqueness_slot_sha256"],
        intent.external_launch_nonce_sha256,
        intent.expected_prior_registry_checkpoint_sha256,
        _raw_sha256(current_prefix["raw_permit_bytes"]),  # type: ignore[arg-type]
        *status_artifact_identities,
        *new_trust_artifact_identities,
        *current_sequence_four.custody_event_lineage_sha256s,
        *current_sequence_four.raw_custody_event_lineage_sha256s,
        *current_sequence_four.carrier_lineage_sha256s,
        *current_sequence_four.raw_carrier_lineage_sha256s,
        current_sequence_four.upstream_review_attestation_sha256,
        current_sequence_four.upstream_review_raw_sha256,
    }
    if current_sequence_four.upstream_authorization_receipt_sha256 is not None:
        artifact_identities.add(
            current_sequence_four.upstream_authorization_receipt_sha256
        )
    if current_sequence_four.upstream_authorization_raw_sha256 is not None:
        artifact_identities.add(current_sequence_four.upstream_authorization_raw_sha256)
    if artifact_identities & (revoked_artifacts | superseded_artifacts):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation custody chain is currently revoked or superseded"
        )
    return _new_commit_verification(
        commit_sha256=commit_sha256,
        raw_commit_sha256=_raw_sha256(raw_commit),
        raw_commit_byte_count=len(raw_commit),
        intent_sha256=intent.intent_sha256,
        raw_intent_sha256=intent.raw_intent_sha256,
        lane=intent.lane,
        permit_sha256=intent.permit_sha256,
        study_id_sha256=intent.study_id_sha256,
        run_id_sha256=intent.run_id_sha256,
        authorization_nonce_sha256=intent.authorization_nonce_sha256,
        prior_custody_event_sha256=intent.prior_custody_event_sha256,
        prior_raw_custody_event_sha256=intent.prior_raw_custody_event_sha256,
        continuing_custody_role=intent.from_role,
        continuing_custody_role_identity_sha256=intent.from_role_identity_sha256,
        continuing_custody_key_id=intent.from_key_id,
        continuing_custody_public_key_sha256=intent.from_public_key_sha256,
        reservation_record_sha256=intent.reservation_record_sha256,
        raw_reservation_record_sha256=intent.raw_reservation_record_sha256,
        external_launch_nonce_sha256=intent.external_launch_nonce_sha256,
        registry_realm_identity_sha256=intent.registry_realm_identity_sha256,
        registry_epoch=intent.registry_epoch,
        prior_registry_sequence=intent.expected_prior_registry_sequence,
        committed_registry_sequence=committed_sequence,
        prior_registry_checkpoint_sha256=(
            intent.expected_prior_registry_checkpoint_sha256
        ),
        committed_registry_checkpoint_sha256=committed_checkpoint,
        registry_transaction_sha256=loaded["registry_transaction_sha256"],
        registry_authority_identity_sha256=(registry_anchor.registry_identity_sha256),
        registry_authority_key_id=registry_key_id,
        registry_authority_public_key_sha256=_raw_sha256(
            registry_anchor.verification_key
        ),
        checkpoint_witness_identity_sha256=(witness_anchor.witness_identity_sha256),
        checkpoint_witness_key_id=witness_key_id,
        checkpoint_witness_public_key_sha256=_raw_sha256(
            witness_anchor.verification_key
        ),
        committed_at_utc=loaded["committed_at_utc"],
        current_status_snapshot_sha256=current_status["snapshot_sha256"],
        current_status_checkpoint_sha256=current_status[
            "external_log_checkpoint_sha256"
        ],
        current_status_sequence=current_status["status_sequence"],
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": (
            VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SCHEMA_ID
        ),
        "contract_id": VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_ID,
        "contract_version": (
            VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_VERSION
        ),
        "frozen_at_utc": (
            VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_FROZEN_AT_UTC
        ),
        "superseded_contract_sha256": (
            FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V6
        ),
        "legacy_contract_chain_sha256s": [
            FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V5,
            FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V4,
            FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V3,
            FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V2,
            FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V1,
        ],
        "refreeze_reason": (
            "bind_refrozen_energy_force_nonce_and_review_authorization_"
            "custody_contracts_without_reservation_policy_change"
        ),
        "purpose": {
            "additive_sequence_five_companion_only": True,
            "base_or_sequence_three_four_contract_modified": False,
            "reservation_intent_builder_and_verifier_implemented": True,
            "atomic_commit_attestation_builder_and_verifier_implemented": True,
            "external_serializable_registry_implemented_by_package": False,
            "actual_production_artifact_present": False,
            "execution_gate_opened": False,
            "claim_promotion_allowed": False,
        },
        "bound_contracts": {
            "review_authorization_custody_extension_sha256": (
                FROZEN_VALIDATION_PRODUCTION_REVIEW_AUTHORIZATION_CUSTODY_EXTENSION_CONTRACT_SHA256
            ),
            "energy_force_nonce_reservation_sha256": (
                FROZEN_REFERENCE_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
            ),
            "minimization_nonce_reservation_sha256": (
                FROZEN_REFERENCE_MINIMIZATION_VALIDATION_NONCE_RESERVATION_CONTRACT_SHA256
            ),
        },
        "schemas": {
            "reservation_intent": PRODUCTION_RESERVATION_INTENT_SCHEMA_ID,
            "atomic_reservation_commit": PRODUCTION_ATOMIC_RESERVATION_COMMIT_SCHEMA_ID,
        },
        "reservation_intent": {
            "requested_custody_sequence": PRODUCTION_RESERVATION_CUSTODY_SEQUENCE,
            "sequence_five_commit_attestation_artifact_expected": True,
            "signature_algorithm": PRODUCTION_RESERVATION_CUSTODY_SIGNATURE_ALGORITHM,
            "sequence_four_receiver_signature_required": True,
            "raw_sequence_one_through_four_reverification_required": True,
            "exact_status_fence_bound": True,
            "raw_lane_reservation_record_reverification_required": True,
            "reservation_logical_and_raw_identity_bound": True,
            "lane_record_claims_local_atomic_persistence": True,
            "local_atomic_persistence_independently_verified": False,
            "local_record_is_external_serializable_compare_and_set": False,
            "predecessor_logical_and_raw_identity_bound": True,
            "registry_realm_epoch_and_prior_checkpoint_bound": True,
            "registry_and_witness_identity_key_material_bound": True,
            "registry_witness_and_custody_roles_separated": True,
            "permit_nonce_and_predecessor_realm_global_slots_bound": True,
            "maximum_validity_seconds": int(
                PRODUCTION_RESERVATION_INTENT_MAX_VALIDITY.total_seconds()
            ),
            "maximum_prior_registry_sequence": (
                PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE - 1
            ),
        },
        "atomic_commit": {
            "sequence_five_commit_attestation_artifact_type": True,
            "continuing_sequence_four_receiver_custody_bound": True,
            "registry_authority_ed25519_signature_required": True,
            "independent_checkpoint_witness_ed25519_signature_required": True,
            "witness_signature_covers_registry_signature": True,
            "trust_anchors_scoped_to_registry_realm_and_epoch": True,
            "status_head_compare_and_set_attestation_required": True,
            "permit_one_use_slot_consumption_attestation_required": True,
            "authorization_nonce_slot_consumption_attestation_required": True,
            "predecessor_successor_slot_consumption_attestation_required": True,
            "append_only_commit_persistence_attestation_required": True,
            "checkpoint_witness_observation_attestation_required": True,
            "external_serializable_commit_independently_verified": False,
            "status_head_compare_and_set_committed": False,
            "permit_one_use_slot_consumed": False,
            "authorization_nonce_slot_consumed": False,
            "predecessor_successor_slot_consumed": False,
            "custody_successor_uniqueness_enforced": False,
            "monotonic_registry_sequence_required": True,
            "deterministic_checkpoint_transition_required": True,
            "intent_status_lineage_must_prefix_current_lineage": True,
            "current_status_strict_post_commit_descendant_required": True,
            "post_intent_status_descendants_must_postdate_commit": True,
            "current_revocation_and_supersession_applied": True,
            "all_status_logical_raw_and_checkpoint_identities_checked": True,
            "raw_permit_and_prior_registry_checkpoint_checked": True,
            "all_registry_and_witness_identity_material_checked": True,
            "all_new_trust_roles_globally_separated": True,
            "external_registry_non_equivocation_proof_present": False,
            "registry_epoch_transition_continuity_proof_present": False,
            "same_uid_local_file_replacement_resistance_established": False,
        },
        "resource_limits": {
            "signed_transport_max_bytes": (
                PRODUCTION_RESERVATION_MAX_SIGNED_TRANSPORT_BYTES
            ),
            "lane_reservation_record_max_bytes": (
                PRODUCTION_RESERVATION_MAX_RECORD_BYTES
            ),
            "trust_anchor_max_items": PRODUCTION_RESERVATION_MAX_TRUST_ANCHORS,
            "status_lineage_max_items": (
                PRODUCTION_RESERVATION_MAX_STATUS_LINEAGE_ITEMS
            ),
            "json_maximum_nesting_depth": PRODUCTION_RESERVATION_MAX_JSON_DEPTH,
            "maximum_registry_sequence": PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE,
            "mapping_arguments_exact_builtin_dict_required": True,
            "raw_size_checked_before_json_materialization": True,
            "json_nesting_checked_before_json_materialization": True,
        },
        "claim_policy": dict(_CLAIM_POLICY),
        "blockers": list(_BLOCKERS),
    }


def validation_production_reservation_custody_extension_contract_document() -> dict[
    str, Any
]:
    projection = _contract_projection()
    observed = _sha256(projection)
    if observed != (
        FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256
    ):
        raise ValidationProductionReservationCustodyExtensionError(
            "frozen production reservation custody extension hash drifted"
        )
    return {**projection, "contract_sha256": observed}


def require_validation_production_reservation_custody_extension_contract_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if type(value) is not dict:
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation custody extension contract must be an exact built-in dict"
        )
    expected = validation_production_reservation_custody_extension_contract_document()
    if _canonical_bytes(value) != _canonical_bytes(expected):
        raise ValidationProductionReservationCustodyExtensionError(
            "reservation custody extension contract differs from the frozen record"
        )
    return expected


def validation_production_reservation_custody_extension_decision() -> dict[str, Any]:
    contract = validation_production_reservation_custody_extension_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "reservation_intent_builder_and_verifier_implemented": True,
        "atomic_commit_attestation_builder_and_verifier_implemented": True,
        "external_serializable_registry_implemented_by_package": False,
        "actual_atomic_reservation_commit_present": False,
        "external_serializable_registry_commit_verified": False,
        "status_head_compare_and_set_committed": False,
        "permit_one_use_slot_consumed": False,
        "authorization_nonce_slot_consumed": False,
        "predecessor_successor_slot_consumed": False,
        "custody_successor_uniqueness_enforced": False,
        "external_registry_non_equivocation_verified": False,
        "registry_epoch_transition_continuity_verified": False,
        "same_uid_local_reservation_replacement_resistance_established": False,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "scientifically_validated": False,
        "parameter_fitting_authorized": False,
        "product_qualified": False,
        "claim_safe": False,
        "blockers": list(_BLOCKERS),
    }


__all__ = [
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V4",
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V5",
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V6",
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V3",
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V2",
    "FROZEN_LEGACY_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256_V1",
    "FROZEN_VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SHA256",
    "PRODUCTION_ATOMIC_RESERVATION_COMMIT_SCHEMA_ID",
    "PRODUCTION_RESERVATION_CUSTODY_SEQUENCE",
    "PRODUCTION_RESERVATION_INTENT_MAX_VALIDITY",
    "PRODUCTION_RESERVATION_INTENT_SCHEMA_ID",
    "PRODUCTION_RESERVATION_MAX_REGISTRY_SEQUENCE",
    "ProductionAtomicReservationCommitVerification",
    "ProductionReservationIntentVerification",
    "ProductionReservationRegistryTrustAnchor",
    "ProductionReservationWitnessTrustAnchor",
    "VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_ID",
    "VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_SCHEMA_ID",
    "VALIDATION_PRODUCTION_RESERVATION_CUSTODY_EXTENSION_CONTRACT_VERSION",
    "ValidationProductionReservationCustodyExtensionError",
    "build_signed_production_atomic_reservation_commit",
    "build_signed_production_reservation_intent",
    "require_validation_production_reservation_custody_extension_contract_document",
    "validation_production_reservation_custody_extension_contract_document",
    "validation_production_reservation_custody_extension_decision",
    "verify_signed_production_atomic_reservation_commit",
    "verify_signed_production_reservation_intent",
]
