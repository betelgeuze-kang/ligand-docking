"""Claim-closed production evidence-class and custody primitives.

This module is a common foundation for the synthetic energy/force and
minimization validation lanes.  It deliberately does not turn either lane into
a production runner.  No permit, trust anchor, host enrollment, status log,
custody record, or result is bundled by the repository.

The optional Ed25519 backend remains behind the already established lazy
helper.  Importing this module therefore does not import ``cryptography``.
"""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence


VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_validation_production_evidence_custody_contract/1.0.0"
)
VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_ID = (
    "engine_v2_synthetic_validation_production_evidence_custody/1.0.0"
)
VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_VERSION = "1.0.0"
VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_FROZEN_AT_UTC = "2026-07-19T02:00:00Z"
PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID = (
    "betelgeuze.engine_v2_production_evidence_permit/1.0.0"
)
PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_production_evidence_status_snapshot/1.0.0"
)
PRODUCTION_CUSTODY_EVENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_production_custody_event/1.0.0"
)
PRODUCTION_EVIDENCE_CLASS = "synthetic_validation_production"
PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM = "ed25519"
PRODUCTION_EVIDENCE_LANES = ("energy_force", "minimization")
SUPPORTED_PRODUCTION_LANES = PRODUCTION_EVIDENCE_LANES
PRODUCTION_EVIDENCE_PERMIT_MAX_VALIDITY = timedelta(hours=24)
PRODUCTION_STATUS_SNAPSHOT_MAX_AGE = timedelta(hours=24)
PRODUCTION_CUSTODY_HANDOFF_MAX_DURATION = timedelta(hours=24)
PRODUCTION_CUSTODY_MAX_RAW_ARTIFACT_BYTES = 256 * 1024 * 1024
PRODUCTION_EVIDENCE_MAX_SIGNED_TRANSPORT_BYTES = 4 * 1024 * 1024
PRODUCTION_EVIDENCE_MAX_ARGV_ITEMS = 64
PRODUCTION_EVIDENCE_MAX_ARGV_ITEM_BYTES = 4 * 1024
PRODUCTION_EVIDENCE_MAX_ARGV_TOTAL_BYTES = 64 * 1024
PRODUCTION_EVIDENCE_MAX_CONTRACT_BUNDLE_ROWS = 256
PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND = 4096
PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_ITEMS = 4096
PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_TOTAL_BYTES = 256 * 1024
PRODUCTION_EVIDENCE_MAX_TRUST_ANCHORS = 4096
PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_ITEMS = 64
PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_TOTAL_BYTES = 16 * 1024 * 1024
PRODUCTION_EVIDENCE_MAX_PERMIT_REVERIFICATION_ARGUMENT_BYTES = 2 * 1024 * 1024

PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SCHEMA_ID = (
    VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SCHEMA_ID
)
PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_ID = (
    VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_ID
)
PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_VERSION = (
    VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_VERSION
)
PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_FROZEN_AT_UTC = (
    VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_FROZEN_AT_UTC
)

# Filled with the canonical projection hash after the contract and tests are
# finalized.  Contract access fails closed if it drifts.
FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256 = (
    "cc9065017e2e227b811c56e4c82c31cfdecf8b06e0ffedcc05db85e9d15fc2f1"
)
FROZEN_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256 = (
    FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
)

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
    "production_evidence_permit_not_provisioned",
    "trusted_evidence_authority_key_not_provisioned",
    "external_status_log_not_provisioned",
    "global_one_use_permit_registry_not_provisioned",
    "global_atomic_permit_consumption_not_implemented",
    "run_custodian_key_not_provisioned",
    "enrolled_host_identity_not_provisioned",
    "production_custody_chain_not_provisioned",
    "external_custody_successor_uniqueness_not_provisioned",
    "post_status_snapshot_custody_stages_not_implemented",
    "worker_process_starttime_and_boot_id_binding_missing",
    "external_immutable_artifact_store_not_provisioned",
    "production_validation_result_not_collected",
    "scientific_validation_missing",
    "parameter_fitting_not_authorized",
    "product_integration_not_qualified",
)
_SAFE_CHARACTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-"
_CUSTODY_STAGES = (
    "production_permit",
    "status_snapshot",
    "pre_execution_review",
    "authorization",
    "reservation",
    "environment",
    "runner_start",
    "worker_transcript",
    "observation",
    "result",
    "result_review",
    "response",
)
_CUSTODY_VERIFIABLE_STAGE_SCHEMA_IDS = {
    "production_permit": PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
    "status_snapshot": PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
}
_CUSTODY_STAGE_TRANSITIONS = {
    "production_permit": ("status_snapshot",),
    "status_snapshot": (),
}
_CUSTODY_INITIAL_STAGE = "production_permit"
_CUSTODY_PLANNED_ONLY_STAGES = tuple(
    stage
    for stage in _CUSTODY_STAGES
    if stage not in _CUSTODY_VERIFIABLE_STAGE_SCHEMA_IDS
)
_VERIFICATION_SEAL = object()
_PERMIT_REVERIFICATION_ARGUMENT_KEYS = {
    "expected_permit_id_sha256",
    "expected_study_id_sha256",
    "expected_authorization_nonce_sha256",
    "expected_contract_bundle_sha256_rows",
    "expected_code_commit_sha",
    "expected_source_sha256",
    "expected_source_manifest_sha256",
    "expected_dependency_manifest_sha256",
    "expected_runtime_manifest_sha256",
    "expected_seed",
    "expected_command_argv",
    "expected_artifact_output_root_identity_sha256",
    "minimum_external_log_sequence",
    "expected_external_log_checkpoint_sha256",
    "revoked_authority_key_ids",
    "revoked_permit_sha256s",
    "superseded_permit_sha256s",
    "consumed_permit_sha256s",
}


class ValidationProductionEvidenceCustodyError(ValueError):
    """A production evidence, status, trust, or custody input is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ValidationProductionEvidenceCustodyError(
            "production evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_commit_sha(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be a lowercase Git commit SHA"
        )
    return value


def _require_token(value: object, *, name: str, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(character not in _SAFE_CHARACTERS for character in value)
    ):
        raise ValidationProductionEvidenceCustodyError(
            f"{name} contains unsupported characters"
        )
    return value


def _require_key_id(value: object, *, name: str) -> str:
    return _require_token(value, name=name, maximum=128)


def _require_lane(value: object) -> str:
    if value not in PRODUCTION_EVIDENCE_LANES:
        raise ValidationProductionEvidenceCustodyError(
            "production evidence lane is unsupported"
        )
    return str(value)


def _require_sequence(value: object, *, name: str) -> int:
    if type(value) is not int or value <= 0 or value > 2**63 - 1:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be a positive bounded integer"
        )
    return value


def _require_seed(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValidationProductionEvidenceCustodyError(
            "production evidence seed is invalid"
        )
    return value


def _require_argv(value: object) -> list[str]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not 1 <= len(value) <= PRODUCTION_EVIDENCE_MAX_ARGV_ITEMS
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production evidence argv is invalid"
        )
    argv = list(value)
    try:
        item_sizes = [len(item.encode("utf-8")) for item in argv]
    except UnicodeEncodeError as exc:
        raise ValidationProductionEvidenceCustodyError(
            "production evidence argv is not valid UTF-8"
        ) from exc
    if any(size > PRODUCTION_EVIDENCE_MAX_ARGV_ITEM_BYTES for size in item_sizes) or (
        sum(item_sizes) > PRODUCTION_EVIDENCE_MAX_ARGV_TOTAL_BYTES
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production evidence argv exceeds its fixed byte bounds"
        )
    return argv


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValidationProductionEvidenceCustodyError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must use second resolution"
        )
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be second-resolution UTC"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be second-resolution UTC"
        ) from exc


def _checked_time(value: datetime) -> datetime:
    return _parse_utc(
        _format_utc(value, name="checked_at"),
        name="checked_at",
    )


def _require_public_key(value: object, *, name: str) -> bytes:
    if not isinstance(value, bytes) or len(value) != 32:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must contain exactly 32 bytes"
        )
    return value


def _require_private_key(value: object, *, name: str) -> bytes:
    if not isinstance(value, bytes) or len(value) != 32:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must contain exactly 32 bytes"
        )
    return value


def _sign(message: bytes, private_key: bytes) -> str:
    try:
        from .reference_minimization_validation_ed25519 import (
            ReferenceMinimizationValidationEd25519Error,
            sign_ed25519,
        )

        return sign_ed25519(message, private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionEvidenceCustodyError(
            "production evidence Ed25519 signing failed"
        ) from exc


def _verify(message: bytes, signature: object, public_key: bytes) -> bool:
    try:
        from .reference_minimization_validation_ed25519 import (
            ReferenceMinimizationValidationEd25519Error,
            verify_ed25519,
        )

        return verify_ed25519(message, signature, public_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise ValidationProductionEvidenceCustodyError(
            "production evidence Ed25519 verification failed"
        ) from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationProductionEvidenceCustodyError(
                "production evidence contains a duplicate JSON key"
            )
        result[key] = value
    return result


def _json_string_ascii_size(value: str, *, remaining: int, name: str) -> int:
    if len(value) + 2 > remaining:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} exceeds its fixed transport byte bound"
        )
    size = 2
    for character in value:
        codepoint = ord(character)
        if character in {'"', "\\", "\b", "\f", "\n", "\r", "\t"}:
            size += 2
        elif codepoint < 0x20 or codepoint >= 0x7F:
            size += 6 if codepoint <= 0xFFFF else 12
        else:
            size += 1
        if size > remaining:
            raise ValidationProductionEvidenceCustodyError(
                f"{name} exceeds its fixed transport byte bound"
            )
    return size


def _bounded_json_size(
    value: object,
    *,
    remaining: int,
    name: str,
    active_container_ids: set[int],
    depth: int = 0,
) -> int:
    """Measure canonical JSON before copying or materializing its byte carrier."""

    if remaining < 0 or depth > 128:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} exceeds its fixed transport byte bound"
        )
    if isinstance(value, str):
        return _json_string_ascii_size(value, remaining=remaining, name=name)
    if value is None:
        size = 4
    elif type(value) is bool:
        size = 4 if value else 5
    elif type(value) is int:
        if value.bit_length() > max(64, remaining * 4):
            raise ValidationProductionEvidenceCustodyError(
                f"{name} exceeds its fixed transport byte bound"
            )
        size = len(str(value))
    elif type(value) is float:
        size = len(_canonical_bytes(value))
    elif isinstance(value, Mapping):
        if type(value) is not dict:
            raise ValidationProductionEvidenceCustodyError(
                f"{name} contains a non-built-in mapping container"
            )
        if len(value) > remaining:
            raise ValidationProductionEvidenceCustodyError(
                f"{name} exceeds its fixed transport byte bound"
            )
        container_id = id(value)
        if container_id in active_container_ids:
            raise ValidationProductionEvidenceCustodyError(
                f"{name} contains a circular JSON container"
            )
        active_container_ids.add(container_id)
        try:
            size = 2
            for index, (key, item) in enumerate(value.items()):
                if not isinstance(key, str):
                    raise ValidationProductionEvidenceCustodyError(
                        f"{name} mapping keys must be strings"
                    )
                size += 1 if index else 0
                size += _json_string_ascii_size(
                    key,
                    remaining=remaining - size,
                    name=name,
                )
                size += 1
                size += _bounded_json_size(
                    item,
                    remaining=remaining - size,
                    name=name,
                    active_container_ids=active_container_ids,
                    depth=depth + 1,
                )
                if size > remaining:
                    raise ValidationProductionEvidenceCustodyError(
                        f"{name} exceeds its fixed transport byte bound"
                    )
        finally:
            active_container_ids.remove(container_id)
        return size
    elif isinstance(value, (list, tuple)):
        if type(value) not in (list, tuple):
            raise ValidationProductionEvidenceCustodyError(
                f"{name} contains a non-built-in sequence container"
            )
        if len(value) > remaining:
            raise ValidationProductionEvidenceCustodyError(
                f"{name} exceeds its fixed transport byte bound"
            )
        container_id = id(value)
        if container_id in active_container_ids:
            raise ValidationProductionEvidenceCustodyError(
                f"{name} contains a circular JSON container"
            )
        active_container_ids.add(container_id)
        try:
            size = 2
            for index, item in enumerate(value):
                size += 1 if index else 0
                size += _bounded_json_size(
                    item,
                    remaining=remaining - size,
                    name=name,
                    active_container_ids=active_container_ids,
                    depth=depth + 1,
                )
                if size > remaining:
                    raise ValidationProductionEvidenceCustodyError(
                        f"{name} exceeds its fixed transport byte bound"
                    )
        finally:
            active_container_ids.remove(container_id)
        return size
    else:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} is not canonical JSON data"
        )
    if size > remaining:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} exceeds its fixed transport byte bound"
        )
    return size


def _load_document(
    source: str | bytes | Mapping[str, Any],
    *,
    name: str,
    maximum_bytes: int = PRODUCTION_EVIDENCE_MAX_SIGNED_TRANSPORT_BYTES,
) -> dict[str, Any]:
    if isinstance(source, Mapping):
        if type(source) is not dict:
            raise ValidationProductionEvidenceCustodyError(
                f"{name} mapping source must be an exact built-in dict"
            )
        _bounded_json_size(
            source,
            remaining=maximum_bytes,
            name=name,
            active_container_ids=set(),
        )
        raw = _canonical_bytes(source)
        if len(raw) > maximum_bytes:
            raise ValidationProductionEvidenceCustodyError(
                f"{name} exceeds its fixed transport byte bound"
            )
        return json.loads(raw.decode("ascii"))
    if isinstance(source, str) and len(source) > maximum_bytes:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} exceeds its fixed transport byte bound"
        )
    raw = source.encode("utf-8") if isinstance(source, str) else source
    if not isinstance(raw, bytes) or not raw:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be a mapping, string, or bytes"
        )
    if len(raw) > maximum_bytes:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} exceeds its fixed transport byte bound"
        )
    try:
        loaded = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be canonical UTF-8 JSON"
        ) from exc
    if not isinstance(loaded, dict) or _canonical_bytes(loaded) != raw:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} transport is not canonical JSON"
        )
    return loaded


def _require_bounded_signed_payload(
    payload: dict[str, Any],
    *,
    name: str,
) -> dict[str, Any]:
    if len(_canonical_bytes(payload)) > PRODUCTION_EVIDENCE_MAX_SIGNED_TRANSPORT_BYTES:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} exceeds its fixed signed transport byte bound"
        )
    return payload


def _external_sha256_set(values: Sequence[str], *, name: str) -> set[str]:
    bounded = _bounded_external_values(values, name=name)
    return {_require_sha256(value, name=name) for value in bounded}


def _external_key_id_set(values: Sequence[str], *, name: str) -> set[str]:
    bounded = _bounded_external_values(values, name=name)
    return {_require_key_id(value, name=name) for value in bounded}


def _bounded_external_values(values: Sequence[str], *, name: str) -> tuple[str, ...]:
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or len(values) > PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_ITEMS
    ):
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be an explicit bounded sequence"
        )
    normalized = tuple(values)
    if any(not isinstance(value, str) for value in normalized):
        raise ValidationProductionEvidenceCustodyError(
            f"{name} sequence contains a non-string value"
        )
    try:
        total_bytes = sum(len(value.encode("utf-8")) for value in normalized)
    except UnicodeEncodeError as exc:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} sequence is not valid UTF-8"
        ) from exc
    if total_bytes > PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_TOTAL_BYTES:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} sequence exceeds its fixed total byte bound"
        )
    if len(set(normalized)) != len(normalized):
        raise ValidationProductionEvidenceCustodyError(
            f"{name} sequence contains duplicates"
        )
    return normalized


def _contract_bundle_rows(value: Mapping[str, str]) -> list[dict[str, str]]:
    if (
        not isinstance(value, Mapping)
        or not value
        or len(value) > PRODUCTION_EVIDENCE_MAX_CONTRACT_BUNDLE_ROWS
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production evidence contract bundle is empty or exceeds its row bound"
        )
    rows = [
        {
            "contract_id": _require_token(contract_id, name="contract bundle id"),
            "sha256": _require_sha256(digest, name="contract bundle digest"),
        }
        for contract_id, digest in value.items()
    ]
    rows.sort(key=lambda row: row["contract_id"])
    if len({row["contract_id"] for row in rows}) != len(rows):
        raise ValidationProductionEvidenceCustodyError(
            "production evidence contract bundle contains duplicates"
        )
    return rows


def _require_closed_claim_policy(payload: Mapping[str, Any]) -> None:
    if any(payload.get(key) is not False for key in _CLAIM_POLICY):
        raise ValidationProductionEvidenceCustodyError(
            "production evidence cannot promote scientific, fitting, or product claims"
        )


@dataclass(frozen=True, slots=True)
class EvidenceAuthorityTrustAnchor:
    authority_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "authority_identity_sha256",
            _require_sha256(
                self.authority_identity_sha256,
                name="evidence authority identity",
            ),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_public_key(
                self.verification_key,
                name="evidence authority public key",
            ),
        )


@dataclass(frozen=True, slots=True)
class CustodyRoleTrustAnchor:
    custody_role: str
    role_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "custody_role",
            _require_token(self.custody_role, name="custody role", maximum=128),
        )
        object.__setattr__(
            self,
            "role_identity_sha256",
            _require_sha256(self.role_identity_sha256, name="custody role identity"),
        )
        object.__setattr__(
            self,
            "verification_key",
            _require_public_key(
                self.verification_key,
                name="custody role public key",
            ),
        )


def _require_valid_authority_trust_map(
    trusted_authority_keys: Mapping[str, EvidenceAuthorityTrustAnchor],
) -> None:
    if (
        not isinstance(trusted_authority_keys, Mapping)
        or not trusted_authority_keys
        or len(trusted_authority_keys) > PRODUCTION_EVIDENCE_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionEvidenceCustodyError(
            "evidence authority trust map is empty or exceeds its fixed bound"
        )
    anchors: list[EvidenceAuthorityTrustAnchor] = []
    for key_id, anchor in trusted_authority_keys.items():
        _require_key_id(key_id, name="trusted evidence authority key id")
        if not isinstance(anchor, EvidenceAuthorityTrustAnchor):
            raise ValidationProductionEvidenceCustodyError(
                "evidence authority trust map contains an invalid anchor"
            )
        anchors.append(anchor)
    public_keys = [anchor.verification_key for anchor in anchors]
    identities = [anchor.authority_identity_sha256 for anchor in anchors]
    if len(set(public_keys)) != len(public_keys) or len(set(identities)) != len(
        identities
    ):
        raise ValidationProductionEvidenceCustodyError(
            "evidence authority trust map contains a public-key or identity alias"
        )


def _require_valid_custody_trust_map(
    trusted_custody_keys: Mapping[str, CustodyRoleTrustAnchor],
) -> None:
    if (
        not isinstance(trusted_custody_keys, Mapping)
        or not trusted_custody_keys
        or len(trusted_custody_keys) > PRODUCTION_EVIDENCE_MAX_TRUST_ANCHORS
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody trust map is empty or exceeds its fixed bound"
        )
    anchors: list[CustodyRoleTrustAnchor] = []
    for key_id, anchor in trusted_custody_keys.items():
        _require_key_id(key_id, name="trusted custody key id")
        if not isinstance(anchor, CustodyRoleTrustAnchor):
            raise ValidationProductionEvidenceCustodyError(
                "custody trust map contains an invalid anchor"
            )
        anchors.append(anchor)
    public_keys = [anchor.verification_key for anchor in anchors]
    identities = [anchor.role_identity_sha256 for anchor in anchors]
    if len(set(public_keys)) != len(public_keys) or len(set(identities)) != len(
        identities
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody trust map contains a public-key or role-identity alias"
        )


def _require_globally_separated_trust_maps(
    trusted_authority_keys: Mapping[str, EvidenceAuthorityTrustAnchor],
    trusted_custody_keys: Mapping[str, CustodyRoleTrustAnchor],
) -> None:
    _require_valid_authority_trust_map(trusted_authority_keys)
    _require_valid_custody_trust_map(trusted_custody_keys)
    authority_public_keys = {
        anchor.verification_key for anchor in trusted_authority_keys.values()
    }
    custody_public_keys = {
        anchor.verification_key for anchor in trusted_custody_keys.values()
    }
    authority_identities = {
        anchor.authority_identity_sha256 for anchor in trusted_authority_keys.values()
    }
    custody_identities = {
        anchor.role_identity_sha256 for anchor in trusted_custody_keys.values()
    }
    if (
        authority_public_keys & custody_public_keys
        or (authority_identities & custody_identities)
        or set(trusted_authority_keys) & set(trusted_custody_keys)
    ):
        raise ValidationProductionEvidenceCustodyError(
            "authority and custody trust maps reuse key id, public key, or identity material"
        )


def _new_sealed_verification(verification_type: type[Any], **values: Any) -> Any:
    instance = object.__new__(verification_type)
    for name, definition in verification_type.__dataclass_fields__.items():
        if name == "_verification_seal":
            value = _VERIFICATION_SEAL
        elif name in values:
            value = values[name]
        elif definition.default is not MISSING:
            value = definition.default
        else:
            raise AssertionError(f"missing sealed verification field: {name}")
        object.__setattr__(instance, name, value)
    return instance


def _require_sealed_verification(
    value: object,
    expected_type: type[Any],
    *,
    name: str,
) -> None:
    if type(value) is not expected_type or (
        getattr(value, "_verification_seal", None) is not _VERIFICATION_SEAL
    ):
        raise ValidationProductionEvidenceCustodyError(
            f"{name} must be a verifier-issued sealed verification"
        )


@dataclass(frozen=True, slots=True, init=False)
class ProductionEvidencePermitVerification:
    permit_sha256: str
    permit_id_sha256: str
    lane: str
    study_id_sha256: str
    run_id_sha256: str
    authorization_nonce_sha256: str
    authority_identity_sha256: str
    authority_key_id: str
    expected_custodian_identity_sha256: str
    expected_enrolled_host_identity_sha256: str
    issued_at_utc: str
    expires_at_utc: str
    external_log_sequence: int
    external_log_checkpoint_sha256: str
    authority_public_key_sha256: str
    checked_at_utc: str
    production_evidence_permit_verified: bool = True
    production_validation_results_collected: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _permit_projection(
    *,
    permit_id_sha256: str,
    lane: str,
    study_id_sha256: str,
    run_id_sha256: str,
    authorization_nonce_sha256: str,
    contract_bundle_sha256_rows: Mapping[str, str],
    code_commit_sha: str,
    source_sha256: str,
    source_manifest_sha256: str,
    dependency_manifest_sha256: str,
    runtime_manifest_sha256: str,
    expected_custodian_identity_sha256: str,
    expected_enrolled_host_identity_sha256: str,
    seed: int,
    command_argv: Sequence[str],
    artifact_output_root_identity_sha256: str,
    authority_identity_sha256: str,
    authority_key_id: str,
    issued_at_utc: str,
    expires_at_utc: str,
    external_log_sequence: int,
    external_log_checkpoint_sha256: str,
) -> dict[str, Any]:
    authority_identity = _require_sha256(
        authority_identity_sha256,
        name="permit authority identity",
    )
    custodian_identity = _require_sha256(
        expected_custodian_identity_sha256,
        name="permit expected custodian",
    )
    if authority_identity == custodian_identity:
        raise ValidationProductionEvidenceCustodyError(
            "production permit authority and custodian identities must be distinct"
        )
    return {
        "schema_id": PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
        "contract_sha256": validation_production_evidence_custody_contract_document()[
            "contract_sha256"
        ],
        "evidence_class": PRODUCTION_EVIDENCE_CLASS,
        "artifact_stage": "production_permit",
        "lane": _require_lane(lane),
        "one_use_permit": True,
        "permit_id_sha256": _require_sha256(permit_id_sha256, name="permit id"),
        "study_id_sha256": _require_sha256(study_id_sha256, name="study id"),
        "run_id_sha256": _require_sha256(run_id_sha256, name="run id"),
        "authorization_nonce_sha256": _require_sha256(
            authorization_nonce_sha256,
            name="authorization nonce",
        ),
        "contract_bundle_sha256_rows": _contract_bundle_rows(
            contract_bundle_sha256_rows
        ),
        "code_commit_sha": _require_commit_sha(
            code_commit_sha,
            name="permit code commit",
        ),
        "source_sha256": _require_sha256(source_sha256, name="permit source"),
        "source_manifest_sha256": _require_sha256(
            source_manifest_sha256,
            name="permit source manifest",
        ),
        "dependency_manifest_sha256": _require_sha256(
            dependency_manifest_sha256,
            name="permit dependency manifest",
        ),
        "runtime_manifest_sha256": _require_sha256(
            runtime_manifest_sha256,
            name="permit runtime manifest",
        ),
        "expected_custodian_identity_sha256": custodian_identity,
        "expected_enrolled_host_identity_sha256": _require_sha256(
            expected_enrolled_host_identity_sha256,
            name="permit expected enrolled host",
        ),
        "seed": _require_seed(seed),
        "command_argv": _require_argv(command_argv),
        "artifact_output_root_identity_sha256": _require_sha256(
            artifact_output_root_identity_sha256,
            name="permit artifact output root",
        ),
        "authority_identity_sha256": authority_identity,
        "authority_key_id": _require_key_id(
            authority_key_id,
            name="permit authority key id",
        ),
        "issued_at_utc": issued_at_utc,
        "expires_at_utc": expires_at_utc,
        "external_log_sequence": _require_sequence(
            external_log_sequence,
            name="permit external log sequence",
        ),
        "external_log_checkpoint_sha256": _require_sha256(
            external_log_checkpoint_sha256,
            name="permit external log checkpoint",
        ),
        **_CLAIM_POLICY,
        "superseded": False,
        "revoked": False,
    }


def build_signed_production_evidence_permit(
    *,
    permit_id_sha256: str,
    lane: str,
    study_id_sha256: str,
    run_id_sha256: str,
    authorization_nonce_sha256: str,
    contract_bundle_sha256_rows: Mapping[str, str],
    code_commit_sha: str,
    source_sha256: str,
    source_manifest_sha256: str,
    dependency_manifest_sha256: str,
    runtime_manifest_sha256: str,
    expected_custodian_identity_sha256: str,
    expected_enrolled_host_identity_sha256: str,
    seed: int,
    command_argv: Sequence[str],
    artifact_output_root_identity_sha256: str,
    authority_identity_sha256: str,
    authority_key_id: str,
    signing_key: bytes,
    issued_at: datetime,
    expires_at: datetime,
    external_log_sequence: int,
    external_log_checkpoint_sha256: str,
) -> dict[str, Any]:
    """Create one pre-execution, one-use, claim-closed production permit."""

    issued_at_utc = _format_utc(issued_at, name="permit issued_at")
    expires_at_utc = _format_utc(expires_at, name="permit expires_at")
    issued = _parse_utc(issued_at_utc, name="permit issued_at")
    expires = _parse_utc(expires_at_utc, name="permit expires_at")
    if expires <= issued or expires - issued > PRODUCTION_EVIDENCE_PERMIT_MAX_VALIDITY:
        raise ValidationProductionEvidenceCustodyError(
            "production permit validity must be positive and no longer than 24 hours"
        )
    projection = _permit_projection(
        permit_id_sha256=permit_id_sha256,
        lane=lane,
        study_id_sha256=study_id_sha256,
        run_id_sha256=run_id_sha256,
        authorization_nonce_sha256=authorization_nonce_sha256,
        contract_bundle_sha256_rows=contract_bundle_sha256_rows,
        code_commit_sha=code_commit_sha,
        source_sha256=source_sha256,
        source_manifest_sha256=source_manifest_sha256,
        dependency_manifest_sha256=dependency_manifest_sha256,
        runtime_manifest_sha256=runtime_manifest_sha256,
        expected_custodian_identity_sha256=expected_custodian_identity_sha256,
        expected_enrolled_host_identity_sha256=expected_enrolled_host_identity_sha256,
        seed=seed,
        command_argv=command_argv,
        artifact_output_root_identity_sha256=artifact_output_root_identity_sha256,
        authority_identity_sha256=authority_identity_sha256,
        authority_key_id=authority_key_id,
        issued_at_utc=issued_at_utc,
        expires_at_utc=expires_at_utc,
        external_log_sequence=external_log_sequence,
        external_log_checkpoint_sha256=external_log_checkpoint_sha256,
    )
    payload = dict(projection)
    payload["permit_sha256"] = _sha256(projection)
    payload["signature"] = {
        "algorithm": PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(authority_key_id, name="permit authority key id"),
        "value": _sign(
            _canonical_bytes(payload),
            _require_private_key(signing_key, name="permit signing key"),
        ),
    }
    return _require_bounded_signed_payload(payload, name="production evidence permit")


def verify_signed_production_evidence_permit(
    source: str | bytes | Mapping[str, Any],
    *,
    expected_permit_sha256: str,
    trusted_authority_keys: Mapping[str, EvidenceAuthorityTrustAnchor],
    checked_at: datetime,
    expected_lane: str,
    expected_permit_id_sha256: str,
    expected_study_id_sha256: str,
    expected_run_id_sha256: str,
    expected_authorization_nonce_sha256: str,
    expected_contract_bundle_sha256_rows: Mapping[str, str],
    expected_code_commit_sha: str,
    expected_source_sha256: str,
    expected_source_manifest_sha256: str,
    expected_dependency_manifest_sha256: str,
    expected_runtime_manifest_sha256: str,
    expected_custodian_identity_sha256: str,
    expected_enrolled_host_identity_sha256: str,
    expected_seed: int,
    expected_command_argv: Sequence[str],
    expected_artifact_output_root_identity_sha256: str,
    minimum_external_log_sequence: int,
    expected_external_log_checkpoint_sha256: str,
    revoked_authority_key_ids: Sequence[str],
    revoked_permit_sha256s: Sequence[str],
    superseded_permit_sha256s: Sequence[str],
    consumed_permit_sha256s: Sequence[str],
) -> ProductionEvidencePermitVerification:
    """Verify one exact, current, unconsumed permit with out-of-band trust."""

    payload = _load_document(source, name="production evidence permit")
    _require_valid_authority_trust_map(trusted_authority_keys)
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping) or set(signature) != {
        "algorithm",
        "key_id",
        "value",
    }:
        raise ValidationProductionEvidenceCustodyError(
            "production permit signature fields are invalid"
        )
    if signature.get("algorithm") != PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM:
        raise ValidationProductionEvidenceCustodyError(
            "production permit signature algorithm is unsupported"
        )
    key_id = _require_key_id(signature.get("key_id"), name="permit authority key id")
    if key_id in _external_key_id_set(
        revoked_authority_key_ids,
        name="revoked authority key id",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production permit authority key is revoked"
        )
    anchor = trusted_authority_keys.get(key_id)
    if not isinstance(anchor, EvidenceAuthorityTrustAnchor):
        raise ValidationProductionEvidenceCustodyError(
            "production permit authority key is not trusted"
        )
    if not _verify(
        _canonical_bytes(payload), signature.get("value"), anchor.verification_key
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production permit signature verification failed"
        )
    permit_sha256 = payload.pop("permit_sha256", None)
    if permit_sha256 != _sha256(payload):
        raise ValidationProductionEvidenceCustodyError(
            "production permit SHA-256 verification failed"
        )
    permit_sha256 = _require_sha256(permit_sha256, name="production permit")
    if permit_sha256 != _require_sha256(
        expected_permit_sha256,
        name="expected production permit",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production permit is cross-wired to its out-of-band identity"
        )
    if permit_sha256 in _external_sha256_set(
        revoked_permit_sha256s,
        name="revoked production permit",
    ):
        raise ValidationProductionEvidenceCustodyError("production permit is revoked")
    if permit_sha256 in _external_sha256_set(
        superseded_permit_sha256s,
        name="superseded production permit",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production permit is superseded"
        )
    if permit_sha256 in _external_sha256_set(
        consumed_permit_sha256s,
        name="consumed production permit",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production permit was already consumed"
        )
    if payload.get("evidence_class") != PRODUCTION_EVIDENCE_CLASS:
        raise ValidationProductionEvidenceCustodyError(
            "production evidence class is missing or downgraded"
        )
    if payload.get("authority_identity_sha256") != anchor.authority_identity_sha256:
        raise ValidationProductionEvidenceCustodyError(
            "production permit authority identity does not match its trusted key"
        )
    if payload.get("authority_key_id") != key_id:
        raise ValidationProductionEvidenceCustodyError(
            "production permit authority key id is cross-wired"
        )
    sequence = _require_sequence(
        payload.get("external_log_sequence"),
        name="permit external log sequence",
    )
    if sequence < _require_sequence(
        minimum_external_log_sequence,
        name="minimum external log sequence",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production permit external log sequence is stale"
        )
    checkpoint = _require_sha256(
        payload.get("external_log_checkpoint_sha256"),
        name="permit external log checkpoint",
    )
    if checkpoint != _require_sha256(
        expected_external_log_checkpoint_sha256,
        name="expected external log checkpoint",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "production permit external log checkpoint is stale or forked"
        )
    issued = _parse_utc(payload.get("issued_at_utc"), name="permit issued_at")
    expires = _parse_utc(payload.get("expires_at_utc"), name="permit expires_at")
    checked = _checked_time(checked_at)
    if expires <= issued or expires - issued > PRODUCTION_EVIDENCE_PERMIT_MAX_VALIDITY:
        raise ValidationProductionEvidenceCustodyError(
            "production permit validity interval is invalid"
        )
    if checked < issued:
        raise ValidationProductionEvidenceCustodyError(
            "production permit is not yet valid"
        )
    if checked >= expires:
        raise ValidationProductionEvidenceCustodyError("production permit is expired")
    expected_projection = _permit_projection(
        permit_id_sha256=expected_permit_id_sha256,
        lane=expected_lane,
        study_id_sha256=expected_study_id_sha256,
        run_id_sha256=expected_run_id_sha256,
        authorization_nonce_sha256=expected_authorization_nonce_sha256,
        contract_bundle_sha256_rows=expected_contract_bundle_sha256_rows,
        code_commit_sha=expected_code_commit_sha,
        source_sha256=expected_source_sha256,
        source_manifest_sha256=expected_source_manifest_sha256,
        dependency_manifest_sha256=expected_dependency_manifest_sha256,
        runtime_manifest_sha256=expected_runtime_manifest_sha256,
        expected_custodian_identity_sha256=expected_custodian_identity_sha256,
        expected_enrolled_host_identity_sha256=expected_enrolled_host_identity_sha256,
        seed=expected_seed,
        command_argv=expected_command_argv,
        artifact_output_root_identity_sha256=(
            expected_artifact_output_root_identity_sha256
        ),
        authority_identity_sha256=anchor.authority_identity_sha256,
        authority_key_id=key_id,
        issued_at_utc=payload["issued_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        external_log_sequence=sequence,
        external_log_checkpoint_sha256=checkpoint,
    )
    if payload != expected_projection:
        raise ValidationProductionEvidenceCustodyError(
            "production permit fields do not match the exact expected run"
        )
    _require_closed_claim_policy(payload)
    return _new_sealed_verification(
        ProductionEvidencePermitVerification,
        permit_sha256=permit_sha256,
        permit_id_sha256=payload["permit_id_sha256"],
        lane=payload["lane"],
        study_id_sha256=payload["study_id_sha256"],
        run_id_sha256=payload["run_id_sha256"],
        authorization_nonce_sha256=payload["authorization_nonce_sha256"],
        authority_identity_sha256=anchor.authority_identity_sha256,
        authority_key_id=key_id,
        expected_custodian_identity_sha256=payload[
            "expected_custodian_identity_sha256"
        ],
        expected_enrolled_host_identity_sha256=payload[
            "expected_enrolled_host_identity_sha256"
        ],
        issued_at_utc=payload["issued_at_utc"],
        expires_at_utc=payload["expires_at_utc"],
        external_log_sequence=sequence,
        external_log_checkpoint_sha256=checkpoint,
        authority_public_key_sha256=_raw_sha256(anchor.verification_key),
        checked_at_utc=_format_utc(checked, name="permit checked_at"),
    )


def _normalize_revoked_key_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    if (
        isinstance(rows, (str, bytes))
        or not isinstance(rows, Sequence)
        or len(rows) > PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND
    ):
        raise ValidationProductionEvidenceCustodyError(
            "revoked key rows must be an explicit sequence"
        )
    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "role",
            "key_id",
            "revoked_at_utc",
            "reason_code",
        }:
            raise ValidationProductionEvidenceCustodyError(
                "revoked key row fields are invalid"
            )
        normalized.append(
            {
                "role": _require_token(row["role"], name="revoked key role"),
                "key_id": _require_key_id(row["key_id"], name="revoked key id"),
                "revoked_at_utc": _format_utc(
                    _parse_utc(row["revoked_at_utc"], name="key revoked_at"),
                    name="key revoked_at",
                ),
                "reason_code": _require_token(
                    row["reason_code"],
                    name="revoked key reason",
                ),
            }
        )
    normalized.sort(key=lambda row: (row["role"], row["key_id"]))
    if len({(row["role"], row["key_id"]) for row in normalized}) != len(normalized):
        raise ValidationProductionEvidenceCustodyError(
            "revoked key rows contain duplicates"
        )
    return normalized


def _normalize_revoked_artifact_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    if (
        isinstance(rows, (str, bytes))
        or not isinstance(rows, Sequence)
        or len(rows) > PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND
    ):
        raise ValidationProductionEvidenceCustodyError(
            "revoked artifact rows must be an explicit sequence"
        )
    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "artifact_kind",
            "artifact_sha256",
            "revoked_at_utc",
            "reason_code",
        }:
            raise ValidationProductionEvidenceCustodyError(
                "revoked artifact row fields are invalid"
            )
        normalized.append(
            {
                "artifact_kind": _require_token(
                    row["artifact_kind"],
                    name="revoked artifact kind",
                ),
                "artifact_sha256": _require_sha256(
                    row["artifact_sha256"],
                    name="revoked artifact",
                ),
                "revoked_at_utc": _format_utc(
                    _parse_utc(row["revoked_at_utc"], name="artifact revoked_at"),
                    name="artifact revoked_at",
                ),
                "reason_code": _require_token(
                    row["reason_code"],
                    name="revoked artifact reason",
                ),
            }
        )
    normalized.sort(key=lambda row: (row["artifact_kind"], row["artifact_sha256"]))
    if len(
        {(row["artifact_kind"], row["artifact_sha256"]) for row in normalized}
    ) != len(normalized):
        raise ValidationProductionEvidenceCustodyError(
            "revoked artifact rows contain duplicates"
        )
    return normalized


def _normalize_supersession_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    if (
        isinstance(rows, (str, bytes))
        or not isinstance(rows, Sequence)
        or len(rows) > PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND
    ):
        raise ValidationProductionEvidenceCustodyError(
            "supersession rows must be an explicit sequence"
        )
    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "artifact_kind",
            "superseded_sha256",
            "replacement_sha256",
            "superseded_at_utc",
        }:
            raise ValidationProductionEvidenceCustodyError(
                "supersession row fields are invalid"
            )
        superseded = _require_sha256(
            row["superseded_sha256"],
            name="superseded artifact",
        )
        replacement = _require_sha256(
            row["replacement_sha256"],
            name="replacement artifact",
        )
        if superseded == replacement:
            raise ValidationProductionEvidenceCustodyError(
                "supersession replacement must differ from the superseded artifact"
            )
        normalized.append(
            {
                "artifact_kind": _require_token(
                    row["artifact_kind"],
                    name="supersession artifact kind",
                ),
                "superseded_sha256": superseded,
                "replacement_sha256": replacement,
                "superseded_at_utc": _format_utc(
                    _parse_utc(
                        row["superseded_at_utc"],
                        name="artifact superseded_at",
                    ),
                    name="artifact superseded_at",
                ),
            }
        )
    normalized.sort(key=lambda row: (row["artifact_kind"], row["superseded_sha256"]))
    if len(
        {(row["artifact_kind"], row["superseded_sha256"]) for row in normalized}
    ) != len(normalized):
        raise ValidationProductionEvidenceCustodyError(
            "supersession rows contain duplicates or forks"
        )
    return normalized


@dataclass(frozen=True, slots=True, init=False)
class ProductionEvidenceStatusSnapshotVerification:
    snapshot_sha256: str
    permit_sha256: str
    run_id_sha256: str
    lane: str
    custodian_identity_sha256: str
    enrolled_host_identity_sha256: str
    status_sequence: int
    external_log_checkpoint_sha256: str
    previous_snapshot_sha256: str | None
    issued_at_utc: str
    authority_identity_sha256: str
    authority_key_id: str
    authority_public_key_sha256: str
    checked_at_utc: str
    lineage_snapshot_sha256s: tuple[str, ...]
    revoked_key_rows: tuple[tuple[str, str], ...]
    revoked_artifact_rows: tuple[tuple[str, str], ...]
    supersession_rows: tuple[tuple[str, str, str], ...]
    revoked_key_record_rows: tuple[tuple[str, str, str, str], ...]
    revoked_artifact_record_rows: tuple[tuple[str, str, str, str], ...]
    supersession_record_rows: tuple[tuple[str, str, str, str], ...]
    status_snapshot_verified: bool = True
    production_validation_results_collected: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)

    def key_is_revoked(self, role: str, key_id: str) -> bool:
        return (role, key_id) in self.revoked_key_rows

    def artifact_is_revoked(self, kind: str, sha256: str) -> bool:
        return (kind, sha256) in self.revoked_artifact_rows

    def artifact_is_superseded(self, kind: str, sha256: str) -> bool:
        return any(
            row_kind == kind and superseded == sha256
            for row_kind, superseded, _replacement in self.supersession_rows
        )


def _status_projection(
    *,
    permit_sha256: str,
    run_id_sha256: str,
    lane: str,
    custodian_identity_sha256: str,
    enrolled_host_identity_sha256: str,
    status_sequence: int,
    external_log_checkpoint_sha256: str,
    previous_snapshot_sha256: str | None,
    issued_at_utc: str,
    authority_identity_sha256: str,
    authority_key_id: str,
    revoked_key_rows: Sequence[Mapping[str, Any]],
    revoked_artifact_rows: Sequence[Mapping[str, Any]],
    supersession_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    sequence = _require_sequence(status_sequence, name="status sequence")
    previous = (
        None
        if previous_snapshot_sha256 is None
        else _require_sha256(
            previous_snapshot_sha256,
            name="previous status snapshot",
        )
    )
    if (sequence == 1) is not (previous is None):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot sequence and previous snapshot are inconsistent"
        )
    issued = _parse_utc(issued_at_utc, name="status issued_at")
    normalized_keys = _normalize_revoked_key_rows(revoked_key_rows)
    normalized_artifacts = _normalize_revoked_artifact_rows(revoked_artifact_rows)
    normalized_supersessions = _normalize_supersession_rows(supersession_rows)
    event_times = [
        *(
            _parse_utc(row["revoked_at_utc"], name="key revoked_at")
            for row in normalized_keys
        ),
        *(
            _parse_utc(row["revoked_at_utc"], name="artifact revoked_at")
            for row in normalized_artifacts
        ),
        *(
            _parse_utc(row["superseded_at_utc"], name="artifact superseded_at")
            for row in normalized_supersessions
        ),
    ]
    if any(event_time > issued for event_time in event_times):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot contains future-dated revocation or supersession data"
        )
    return {
        "schema_id": PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
        "contract_sha256": validation_production_evidence_custody_contract_document()[
            "contract_sha256"
        ],
        "evidence_class": PRODUCTION_EVIDENCE_CLASS,
        "artifact_stage": "status_snapshot",
        "permit_sha256": _require_sha256(
            permit_sha256,
            name="status permit",
        ),
        "run_id_sha256": _require_sha256(run_id_sha256, name="status run id"),
        "lane": _require_lane(lane),
        "custodian_identity_sha256": _require_sha256(
            custodian_identity_sha256,
            name="status custodian identity",
        ),
        "enrolled_host_identity_sha256": _require_sha256(
            enrolled_host_identity_sha256,
            name="status enrolled host identity",
        ),
        "status_sequence": sequence,
        "external_log_checkpoint_sha256": _require_sha256(
            external_log_checkpoint_sha256,
            name="status external log checkpoint",
        ),
        "previous_snapshot_sha256": previous,
        "issued_at_utc": issued_at_utc,
        "authority_identity_sha256": _require_sha256(
            authority_identity_sha256,
            name="status authority identity",
        ),
        "authority_key_id": _require_key_id(
            authority_key_id,
            name="status authority key id",
        ),
        "revoked_key_rows": normalized_keys,
        "revoked_artifact_rows": normalized_artifacts,
        "supersession_rows": normalized_supersessions,
        **_CLAIM_POLICY,
    }


def build_signed_production_evidence_status_snapshot(
    *,
    permit_sha256: str,
    run_id_sha256: str,
    lane: str,
    custodian_identity_sha256: str,
    enrolled_host_identity_sha256: str,
    status_sequence: int,
    external_log_checkpoint_sha256: str,
    previous_snapshot_sha256: str | None,
    issued_at: datetime,
    authority_identity_sha256: str,
    authority_key_id: str,
    signing_key: bytes,
    revoked_key_rows: Sequence[Mapping[str, Any]] = (),
    revoked_artifact_rows: Sequence[Mapping[str, Any]] = (),
    supersession_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    projection = _status_projection(
        permit_sha256=permit_sha256,
        run_id_sha256=run_id_sha256,
        lane=lane,
        custodian_identity_sha256=custodian_identity_sha256,
        enrolled_host_identity_sha256=enrolled_host_identity_sha256,
        status_sequence=status_sequence,
        external_log_checkpoint_sha256=external_log_checkpoint_sha256,
        previous_snapshot_sha256=previous_snapshot_sha256,
        issued_at_utc=_format_utc(issued_at, name="status issued_at"),
        authority_identity_sha256=authority_identity_sha256,
        authority_key_id=authority_key_id,
        revoked_key_rows=revoked_key_rows,
        revoked_artifact_rows=revoked_artifact_rows,
        supersession_rows=supersession_rows,
    )
    payload = dict(projection)
    payload["snapshot_sha256"] = _sha256(projection)
    payload["signature"] = {
        "algorithm": PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM,
        "key_id": _require_key_id(authority_key_id, name="status authority key id"),
        "value": _sign(
            _canonical_bytes(payload),
            _require_private_key(signing_key, name="status signing key"),
        ),
    }
    return _require_bounded_signed_payload(
        payload,
        name="production evidence status snapshot",
    )


def verify_signed_production_evidence_status_snapshot(
    source: str | bytes | Mapping[str, Any],
    *,
    expected_snapshot_sha256: str,
    expected_permit_sha256: str,
    expected_run_id_sha256: str,
    expected_lane: str,
    expected_custodian_identity_sha256: str,
    expected_enrolled_host_identity_sha256: str,
    trusted_authority_keys: Mapping[str, EvidenceAuthorityTrustAnchor],
    checked_at: datetime,
    minimum_trusted_sequence: int,
    minimum_trusted_external_log_checkpoint_sha256: str,
    minimum_trusted_issued_at: datetime,
    expected_previous_snapshot_sha256: str | None,
    revoked_authority_key_ids: Sequence[str],
    previous_verified_snapshot: ProductionEvidenceStatusSnapshotVerification
    | None = None,
) -> ProductionEvidenceStatusSnapshotVerification:
    payload = _load_document(source, name="production evidence status snapshot")
    _require_valid_authority_trust_map(trusted_authority_keys)
    signature = payload.pop("signature", None)
    if not isinstance(signature, Mapping) or set(signature) != {
        "algorithm",
        "key_id",
        "value",
    }:
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot signature fields are invalid"
        )
    if signature.get("algorithm") != PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM:
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot signature algorithm is unsupported"
        )
    key_id = _require_key_id(signature.get("key_id"), name="status authority key id")
    if key_id in _external_key_id_set(
        revoked_authority_key_ids,
        name="revoked authority key id",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot authority key is externally revoked"
        )
    anchor = trusted_authority_keys.get(key_id)
    if not isinstance(anchor, EvidenceAuthorityTrustAnchor):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot authority key is not trusted"
        )
    if not _verify(
        _canonical_bytes(payload), signature.get("value"), anchor.verification_key
    ):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot signature verification failed"
        )
    snapshot_sha256 = payload.pop("snapshot_sha256", None)
    if snapshot_sha256 != _sha256(payload):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot SHA-256 verification failed"
        )
    snapshot_sha256 = _require_sha256(snapshot_sha256, name="status snapshot")
    if snapshot_sha256 != _require_sha256(
        expected_snapshot_sha256,
        name="expected status snapshot",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot is cross-wired to its out-of-band identity"
        )
    if payload.get("evidence_class") != PRODUCTION_EVIDENCE_CLASS:
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot evidence class is missing or downgraded"
        )
    if payload.get("authority_identity_sha256") != anchor.authority_identity_sha256:
        raise ValidationProductionEvidenceCustodyError(
            "status authority identity does not match its trusted key"
        )
    if payload.get("authority_key_id") != key_id:
        raise ValidationProductionEvidenceCustodyError(
            "status authority key id is cross-wired"
        )
    sequence = _require_sequence(payload.get("status_sequence"), name="status sequence")
    if sequence < _require_sequence(
        minimum_trusted_sequence,
        name="minimum trusted status sequence",
    ):
        raise ValidationProductionEvidenceCustodyError("status snapshot is stale")
    checkpoint = _require_sha256(
        payload.get("external_log_checkpoint_sha256"),
        name="status external log checkpoint",
    )
    if checkpoint != _require_sha256(
        minimum_trusted_external_log_checkpoint_sha256,
        name="minimum trusted external log checkpoint",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot checkpoint is stale or forked"
        )
    expected_previous = (
        None
        if expected_previous_snapshot_sha256 is None
        else _require_sha256(
            expected_previous_snapshot_sha256,
            name="expected previous status snapshot",
        )
    )
    if payload.get("previous_snapshot_sha256") != expected_previous:
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot previous link is missing or forked"
        )
    issued = _parse_utc(payload.get("issued_at_utc"), name="status issued_at")
    checked = _checked_time(checked_at)
    minimum_issued = _checked_time(minimum_trusted_issued_at)
    if issued < minimum_issued:
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot is backdated before the trusted minimum"
        )
    if issued > checked:
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot is not yet valid"
        )
    if checked - issued > PRODUCTION_STATUS_SNAPSHOT_MAX_AGE:
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot is older than the maximum trusted age"
        )
    expected_projection = _status_projection(
        permit_sha256=expected_permit_sha256,
        run_id_sha256=expected_run_id_sha256,
        lane=expected_lane,
        custodian_identity_sha256=expected_custodian_identity_sha256,
        enrolled_host_identity_sha256=expected_enrolled_host_identity_sha256,
        status_sequence=sequence,
        external_log_checkpoint_sha256=checkpoint,
        previous_snapshot_sha256=expected_previous,
        issued_at_utc=payload["issued_at_utc"],
        authority_identity_sha256=anchor.authority_identity_sha256,
        authority_key_id=key_id,
        revoked_key_rows=payload.get("revoked_key_rows", ()),
        revoked_artifact_rows=payload.get("revoked_artifact_rows", ()),
        supersession_rows=payload.get("supersession_rows", ()),
    )
    if payload != expected_projection:
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot fields do not match the frozen schema"
        )
    _require_closed_claim_policy(payload)
    revoked_keys = tuple(
        (row["role"], row["key_id"]) for row in payload["revoked_key_rows"]
    )
    if any(revoked_key_id == key_id for _role, revoked_key_id in revoked_keys):
        raise ValidationProductionEvidenceCustodyError(
            "status snapshot was signed by a key it records as revoked"
        )
    previous_verification: ProductionEvidenceStatusSnapshotVerification | None
    if sequence == 1:
        if previous_verified_snapshot is not None:
            raise ValidationProductionEvidenceCustodyError(
                "initial status snapshot cannot have a verified predecessor"
            )
        previous_verification = None
        lineage = (snapshot_sha256,)
    else:
        _require_sealed_verification(
            previous_verified_snapshot,
            ProductionEvidenceStatusSnapshotVerification,
            name="previous status snapshot",
        )
        previous_verification = previous_verified_snapshot
        if (
            sequence != previous_verification.status_sequence + 1
            or expected_previous != previous_verification.snapshot_sha256
        ):
            raise ValidationProductionEvidenceCustodyError(
                "status snapshot sequence is not adjacent to its verified predecessor"
            )
        if (
            expected_permit_sha256 != previous_verification.permit_sha256
            or expected_run_id_sha256 != previous_verification.run_id_sha256
            or expected_lane != previous_verification.lane
            or expected_custodian_identity_sha256
            != previous_verification.custodian_identity_sha256
            or expected_enrolled_host_identity_sha256
            != previous_verification.enrolled_host_identity_sha256
        ):
            raise ValidationProductionEvidenceCustodyError(
                "status snapshot context differs from its verified predecessor"
            )
        if issued < _parse_utc(
            previous_verification.issued_at_utc,
            name="previous status issued_at",
        ):
            raise ValidationProductionEvidenceCustodyError(
                "status snapshot is backdated before its verified predecessor"
            )
        lineage = (*previous_verification.lineage_snapshot_sha256s, snapshot_sha256)
    verification = _new_sealed_verification(
        ProductionEvidenceStatusSnapshotVerification,
        snapshot_sha256=snapshot_sha256,
        permit_sha256=payload["permit_sha256"],
        run_id_sha256=payload["run_id_sha256"],
        lane=payload["lane"],
        custodian_identity_sha256=payload["custodian_identity_sha256"],
        enrolled_host_identity_sha256=payload["enrolled_host_identity_sha256"],
        status_sequence=sequence,
        external_log_checkpoint_sha256=checkpoint,
        previous_snapshot_sha256=expected_previous,
        issued_at_utc=payload["issued_at_utc"],
        authority_identity_sha256=anchor.authority_identity_sha256,
        authority_key_id=key_id,
        authority_public_key_sha256=_raw_sha256(anchor.verification_key),
        checked_at_utc=_format_utc(checked, name="status checked_at"),
        lineage_snapshot_sha256s=lineage,
        revoked_key_rows=revoked_keys,
        revoked_artifact_rows=tuple(
            (row["artifact_kind"], row["artifact_sha256"])
            for row in payload["revoked_artifact_rows"]
        ),
        supersession_rows=tuple(
            (
                row["artifact_kind"],
                row["superseded_sha256"],
                row["replacement_sha256"],
            )
            for row in payload["supersession_rows"]
        ),
        revoked_key_record_rows=tuple(
            (
                row["role"],
                row["key_id"],
                row["revoked_at_utc"],
                row["reason_code"],
            )
            for row in payload["revoked_key_rows"]
        ),
        revoked_artifact_record_rows=tuple(
            (
                row["artifact_kind"],
                row["artifact_sha256"],
                row["revoked_at_utc"],
                row["reason_code"],
            )
            for row in payload["revoked_artifact_rows"]
        ),
        supersession_record_rows=tuple(
            (
                row["artifact_kind"],
                row["superseded_sha256"],
                row["replacement_sha256"],
                row["superseded_at_utc"],
            )
            for row in payload["supersession_rows"]
        ),
    )
    if previous_verification is not None:
        if not set(previous_verification.revoked_key_record_rows).issubset(
            verification.revoked_key_record_rows
        ) or not set(previous_verification.revoked_artifact_record_rows).issubset(
            verification.revoked_artifact_record_rows
        ):
            raise ValidationProductionEvidenceCustodyError(
                "status snapshot drops an accumulated revocation"
            )
        current_supersessions = {
            (kind, superseded): replacement
            for kind, superseded, replacement in verification.supersession_rows
        }
        if any(
            current_supersessions.get((kind, superseded)) != replacement
            for kind, superseded, replacement in previous_verification.supersession_rows
        ):
            raise ValidationProductionEvidenceCustodyError(
                "status snapshot drops or rewrites an accumulated supersession"
            )
        if not set(previous_verification.supersession_record_rows).issubset(
            verification.supersession_record_rows
        ):
            raise ValidationProductionEvidenceCustodyError(
                "status snapshot rewrites accumulated supersession metadata"
            )
    return verification


def _load_inner_artifact(
    raw: bytes,
    *,
    artifact_stage: str,
    expected_schema_id: str,
    permit_sha256: str,
    run_id_sha256: str,
    lane: str,
    custodian_identity_sha256: str,
    enrolled_host_identity_sha256: str,
) -> dict[str, Any]:
    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > PRODUCTION_CUSTODY_MAX_RAW_ARTIFACT_BYTES
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody raw artifact bytes are empty or exceed the fixed bound"
        )
    loaded = _load_document(
        raw,
        name="custody raw artifact",
        maximum_bytes=PRODUCTION_CUSTODY_MAX_RAW_ARTIFACT_BYTES,
    )
    stage = _require_token(artifact_stage, name="custody artifact stage")
    schema = _require_token(expected_schema_id, name="custody inner schema id")
    if _CUSTODY_VERIFIABLE_STAGE_SCHEMA_IDS.get(stage) != schema:
        raise ValidationProductionEvidenceCustodyError(
            "custody stage is planned-only or cross-wired to its carrier schema"
        )
    if loaded.get("schema_id") != schema:
        raise ValidationProductionEvidenceCustodyError(
            "custody raw artifact inner schema is cross-wired"
        )
    if loaded.get("evidence_class") != PRODUCTION_EVIDENCE_CLASS:
        raise ValidationProductionEvidenceCustodyError(
            "custody raw artifact production evidence class is missing or downgraded"
        )
    expected_contract = validation_production_evidence_custody_contract_document()[
        "contract_sha256"
    ]
    if (
        loaded.get("artifact_stage") != stage
        or loaded.get("contract_sha256") != expected_contract
        or loaded.get("run_id_sha256") != run_id_sha256
        or loaded.get("lane") != lane
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody raw carrier omits or transplants stage, contract, run, or lane"
        )
    if stage == "production_permit":
        context = (
            loaded.get("permit_sha256"),
            loaded.get("expected_custodian_identity_sha256"),
            loaded.get("expected_enrolled_host_identity_sha256"),
        )
    else:
        context = (
            loaded.get("permit_sha256"),
            loaded.get("custodian_identity_sha256"),
            loaded.get("enrolled_host_identity_sha256"),
        )
    if context != (
        permit_sha256,
        custodian_identity_sha256,
        enrolled_host_identity_sha256,
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody raw carrier omits or transplants permit, custodian, or host"
        )
    return loaded


@dataclass(frozen=True, slots=True, init=False)
class ProductionCustodyEventVerification:
    custody_event_sha256: str
    raw_artifact_sha256: str
    raw_artifact_byte_count: int
    artifact_stage: str
    custody_sequence: int
    prior_custody_event_sha256: str | None
    permit_sha256: str
    run_id_sha256: str
    lane: str
    custodian_identity_sha256: str
    enrolled_host_identity_sha256: str
    from_role: str
    from_role_identity_sha256: str
    from_key_id: str
    from_public_key_sha256: str
    to_role: str
    to_role_identity_sha256: str
    to_key_id: str
    to_public_key_sha256: str
    handed_off_at_utc: str
    received_at_utc: str
    handoff_status_snapshot_sha256: str
    current_status_snapshot_sha256: str
    lineage_custody_event_sha256s: tuple[str, ...]
    lineage_artifact_stages: tuple[str, ...]
    checked_at_utc: str
    dual_custody_signatures_verified: bool = True
    production_validation_results_collected: bool = False
    scientifically_validated: bool = False
    parameter_fitting_authorized: bool = False
    product_qualified: bool = False
    claim_safe: bool = False
    _verification_seal: object = field(init=False, repr=False, compare=False)


def _custody_projection(
    *,
    raw_artifact_sha256: str,
    raw_artifact_byte_count: int,
    inner_schema_id: str,
    artifact_stage: str,
    prior_custody_event_sha256: str | None,
    custody_sequence: int,
    permit_sha256: str,
    run_id_sha256: str,
    lane: str,
    custodian_identity_sha256: str,
    enrolled_host_identity_sha256: str,
    from_role: str,
    from_role_identity_sha256: str,
    from_key_id: str,
    to_role: str,
    to_role_identity_sha256: str,
    to_key_id: str,
    handed_off_at_utc: str,
    received_at_utc: str,
    status_snapshot_sha256: str,
) -> dict[str, Any]:
    sequence = _require_sequence(custody_sequence, name="custody sequence")
    prior = (
        None
        if prior_custody_event_sha256 is None
        else _require_sha256(prior_custody_event_sha256, name="prior custody event")
    )
    if (sequence == 1) is not (prior is None):
        raise ValidationProductionEvidenceCustodyError(
            "custody sequence and prior event link are inconsistent"
        )
    stage = _require_token(artifact_stage, name="custody artifact stage")
    expected_stage_by_sequence = {1: "production_permit", 2: "status_snapshot"}
    if stage not in _CUSTODY_VERIFIABLE_STAGE_SCHEMA_IDS or (
        expected_stage_by_sequence.get(sequence) != stage
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody stage is planned-only or out of the fixed v1 sequence"
        )
    inner_schema = _require_token(
        inner_schema_id,
        name="custody inner schema id",
    )
    if _CUSTODY_VERIFIABLE_STAGE_SCHEMA_IDS[stage] != inner_schema:
        raise ValidationProductionEvidenceCustodyError(
            "custody stage is cross-wired to its fixed inner schema"
        )
    from_role_value = _require_token(from_role, name="from custody role")
    to_role_value = _require_token(to_role, name="to custody role")
    from_identity = _require_sha256(
        from_role_identity_sha256,
        name="from custody identity",
    )
    to_identity = _require_sha256(to_role_identity_sha256, name="to custody identity")
    from_key = _require_key_id(from_key_id, name="from custody key id")
    to_key = _require_key_id(to_key_id, name="to custody key id")
    custodian_identity = _require_sha256(
        custodian_identity_sha256,
        name="custody custodian identity",
    )
    if (
        from_role_value == to_role_value
        or from_identity == to_identity
        or from_key == to_key
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody handoff roles, identities, and key ids must be distinct"
        )
    if sequence == 1 and from_identity != custodian_identity:
        raise ValidationProductionEvidenceCustodyError(
            "initial custody sender must be the permit custodian"
        )
    if type(raw_artifact_byte_count) is not int or not (
        0 < raw_artifact_byte_count <= PRODUCTION_CUSTODY_MAX_RAW_ARTIFACT_BYTES
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody raw artifact byte count is invalid"
        )
    handed_off = _parse_utc(handed_off_at_utc, name="custody handed_off_at")
    received = _parse_utc(received_at_utc, name="custody received_at")
    if (
        received < handed_off
        or received - handed_off > PRODUCTION_CUSTODY_HANDOFF_MAX_DURATION
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody handoff timestamps are invalid"
        )
    return {
        "schema_id": PRODUCTION_CUSTODY_EVENT_SCHEMA_ID,
        "contract_sha256": validation_production_evidence_custody_contract_document()[
            "contract_sha256"
        ],
        "evidence_class": PRODUCTION_EVIDENCE_CLASS,
        "raw_artifact_sha256": _require_sha256(
            raw_artifact_sha256,
            name="custody raw artifact",
        ),
        "raw_artifact_byte_count": raw_artifact_byte_count,
        "inner_schema_id": inner_schema,
        "artifact_stage": stage,
        "prior_custody_event_sha256": prior,
        "custody_sequence": sequence,
        "permit_sha256": _require_sha256(permit_sha256, name="custody permit"),
        "run_id_sha256": _require_sha256(run_id_sha256, name="custody run id"),
        "lane": _require_lane(lane),
        "custodian_identity_sha256": custodian_identity,
        "enrolled_host_identity_sha256": _require_sha256(
            enrolled_host_identity_sha256,
            name="custody enrolled host",
        ),
        "from_role": from_role_value,
        "from_role_identity_sha256": from_identity,
        "from_key_id": from_key,
        "to_role": to_role_value,
        "to_role_identity_sha256": to_identity,
        "to_key_id": to_key,
        "handed_off_at_utc": handed_off_at_utc,
        "received_at_utc": received_at_utc,
        "status_snapshot_sha256": _require_sha256(
            status_snapshot_sha256,
            name="custody status snapshot",
        ),
        **_CLAIM_POLICY,
    }


def build_signed_production_custody_event(
    *,
    raw_artifact_bytes: bytes,
    inner_schema_id: str,
    artifact_stage: str,
    prior_custody_event_sha256: str | None,
    custody_sequence: int,
    permit_sha256: str,
    run_id_sha256: str,
    lane: str,
    custodian_identity_sha256: str,
    enrolled_host_identity_sha256: str,
    from_role: str,
    from_role_identity_sha256: str,
    from_key_id: str,
    from_signing_key: bytes,
    to_role: str,
    to_role_identity_sha256: str,
    to_key_id: str,
    to_signing_key: bytes,
    handed_off_at: datetime,
    received_at: datetime,
    status_snapshot_sha256: str,
) -> dict[str, Any]:
    """Dual-sign one exact canonical raw artifact custody handoff."""

    _load_inner_artifact(
        raw_artifact_bytes,
        artifact_stage=artifact_stage,
        expected_schema_id=inner_schema_id,
        permit_sha256=permit_sha256,
        run_id_sha256=run_id_sha256,
        lane=lane,
        custodian_identity_sha256=custodian_identity_sha256,
        enrolled_host_identity_sha256=enrolled_host_identity_sha256,
    )
    from_private_key = _require_private_key(
        from_signing_key,
        name="from custody signing key",
    )
    to_private_key = _require_private_key(
        to_signing_key,
        name="to custody signing key",
    )
    if from_private_key == to_private_key:
        raise ValidationProductionEvidenceCustodyError(
            "custody handoff signing key material must be distinct"
        )
    projection = _custody_projection(
        raw_artifact_sha256=_raw_sha256(raw_artifact_bytes),
        raw_artifact_byte_count=len(raw_artifact_bytes),
        inner_schema_id=inner_schema_id,
        artifact_stage=artifact_stage,
        prior_custody_event_sha256=prior_custody_event_sha256,
        custody_sequence=custody_sequence,
        permit_sha256=permit_sha256,
        run_id_sha256=run_id_sha256,
        lane=lane,
        custodian_identity_sha256=custodian_identity_sha256,
        enrolled_host_identity_sha256=enrolled_host_identity_sha256,
        from_role=from_role,
        from_role_identity_sha256=from_role_identity_sha256,
        from_key_id=from_key_id,
        to_role=to_role,
        to_role_identity_sha256=to_role_identity_sha256,
        to_key_id=to_key_id,
        handed_off_at_utc=_format_utc(handed_off_at, name="custody handed_off_at"),
        received_at_utc=_format_utc(received_at, name="custody received_at"),
        status_snapshot_sha256=status_snapshot_sha256,
    )
    payload = dict(projection)
    payload["custody_event_sha256"] = _sha256(projection)
    message = _canonical_bytes(payload)
    payload["signatures"] = {
        "from": {
            "algorithm": PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM,
            "key_id": _require_key_id(from_key_id, name="from custody key id"),
            "value": _sign(
                message,
                from_private_key,
            ),
        },
        "to": {
            "algorithm": PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM,
            "key_id": _require_key_id(to_key_id, name="to custody key id"),
            "value": _sign(message, to_private_key),
        },
    }
    return _require_bounded_signed_payload(payload, name="production custody event")


def _verify_signed_production_custody_event_legacy_unreachable(
    *_args: object,
    **_kwargs: object,
) -> None:
    raise ValidationProductionEvidenceCustodyError(
        "legacy custody verification path is permanently disabled"
    )


def _verify_custody_carrier(
    source: str | bytes | Mapping[str, Any],
    *,
    trusted_custody_keys: Mapping[str, CustodyRoleTrustAnchor],
) -> tuple[
    dict[str, Any],
    str,
    CustodyRoleTrustAnchor,
    CustodyRoleTrustAnchor,
    str,
    str,
]:
    _require_valid_custody_trust_map(trusted_custody_keys)
    payload = _load_document(source, name="production custody event")
    signatures = payload.pop("signatures", None)
    if not isinstance(signatures, Mapping) or set(signatures) != {"from", "to"}:
        raise ValidationProductionEvidenceCustodyError(
            "custody event dual signatures are missing"
        )
    for slot in ("from", "to"):
        signature = signatures.get(slot)
        if not isinstance(signature, Mapping) or set(signature) != {
            "algorithm",
            "key_id",
            "value",
        }:
            raise ValidationProductionEvidenceCustodyError(
                "custody event signature fields are invalid"
            )
        if signature.get("algorithm") != PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM:
            raise ValidationProductionEvidenceCustodyError(
                "custody event signature algorithm is unsupported"
            )
    from_key_id = _require_key_id(
        signatures["from"].get("key_id"),
        name="from custody key id",
    )
    to_key_id = _require_key_id(
        signatures["to"].get("key_id"),
        name="to custody key id",
    )
    from_anchor = trusted_custody_keys.get(from_key_id)
    to_anchor = trusted_custody_keys.get(to_key_id)
    if not isinstance(from_anchor, CustodyRoleTrustAnchor) or not isinstance(
        to_anchor,
        CustodyRoleTrustAnchor,
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody event key is not trusted for its role"
        )
    message = _canonical_bytes(payload)
    if not _verify(
        message,
        signatures["from"].get("value"),
        from_anchor.verification_key,
    ) or not _verify(
        message,
        signatures["to"].get("value"),
        to_anchor.verification_key,
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody event dual signature verification failed"
        )
    event_sha256 = payload.pop("custody_event_sha256", None)
    if event_sha256 != _sha256(payload):
        raise ValidationProductionEvidenceCustodyError(
            "custody event SHA-256 verification failed"
        )
    event_sha256 = _require_sha256(event_sha256, name="custody event")
    if (
        payload.get("from_key_id") != from_key_id
        or payload.get("to_key_id") != to_key_id
        or payload.get("from_role") != from_anchor.custody_role
        or payload.get("to_role") != to_anchor.custody_role
        or payload.get("from_role_identity_sha256") != from_anchor.role_identity_sha256
        or payload.get("to_role_identity_sha256") != to_anchor.role_identity_sha256
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody carrier role, identity, or key id is cross-wired"
        )
    projection = _custody_projection(
        raw_artifact_sha256=payload.get("raw_artifact_sha256"),
        raw_artifact_byte_count=payload.get("raw_artifact_byte_count"),
        inner_schema_id=payload.get("inner_schema_id"),
        artifact_stage=payload.get("artifact_stage"),
        prior_custody_event_sha256=payload.get("prior_custody_event_sha256"),
        custody_sequence=payload.get("custody_sequence"),
        permit_sha256=payload.get("permit_sha256"),
        run_id_sha256=payload.get("run_id_sha256"),
        lane=payload.get("lane"),
        custodian_identity_sha256=payload.get("custodian_identity_sha256"),
        enrolled_host_identity_sha256=payload.get("enrolled_host_identity_sha256"),
        from_role=payload.get("from_role"),
        from_role_identity_sha256=payload.get("from_role_identity_sha256"),
        from_key_id=payload.get("from_key_id"),
        to_role=payload.get("to_role"),
        to_role_identity_sha256=payload.get("to_role_identity_sha256"),
        to_key_id=payload.get("to_key_id"),
        handed_off_at_utc=payload.get("handed_off_at_utc"),
        received_at_utc=payload.get("received_at_utc"),
        status_snapshot_sha256=payload.get("status_snapshot_sha256"),
    )
    if payload != projection:
        raise ValidationProductionEvidenceCustodyError(
            "custody carrier fields do not match the frozen schema"
        )
    _require_closed_claim_policy(payload)
    return (
        payload,
        event_sha256,
        from_anchor,
        to_anchor,
        _raw_sha256(from_anchor.verification_key),
        _raw_sha256(to_anchor.verification_key),
    )


def _source_canonical_bytes(
    source: str | bytes | Mapping[str, Any], *, name: str
) -> bytes:
    document = _load_document(source, name=name)
    return _canonical_bytes(document)


def _reverify_status_lineage(
    sources: Sequence[str | bytes | Mapping[str, Any]],
    *,
    trusted_authority_keys: Mapping[str, EvidenceAuthorityTrustAnchor],
    revoked_authority_key_ids: Sequence[str],
    checked_at: datetime,
    expected_current_snapshot_sha256: str,
    expected_current_checkpoint_sha256: str,
    permit_sha256: str,
    run_id_sha256: str,
    lane: str,
    custodian_identity_sha256: str,
    enrolled_host_identity_sha256: str,
) -> tuple[
    tuple[ProductionEvidenceStatusSnapshotVerification, ...],
    tuple[bytes, ...],
]:
    if (
        isinstance(sources, (str, bytes))
        or not isinstance(sources, Sequence)
        or not sources
        or len(sources) > PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_ITEMS
    ):
        raise ValidationProductionEvidenceCustodyError(
            "status lineage sources are empty or exceed the fixed count bound"
        )
    raw_source_rows: list[bytes] = []
    running_total = 0
    for source in sources:
        raw = _source_canonical_bytes(source, name="status lineage carrier")
        running_total += len(raw)
        if running_total > PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_TOTAL_BYTES:
            raise ValidationProductionEvidenceCustodyError(
                "status lineage sources exceed the fixed total byte bound"
            )
        raw_source_rows.append(raw)
    raw_sources = tuple(raw_source_rows)
    verifications: list[ProductionEvidenceStatusSnapshotVerification] = []
    previous: ProductionEvidenceStatusSnapshotVerification | None = None
    checked = _checked_time(checked_at)
    for index, raw in enumerate(raw_sources):
        document = _load_document(raw, name="status lineage carrier")
        issued = _parse_utc(document.get("issued_at_utc"), name="status issued_at")
        is_current = index == len(raw_sources) - 1
        verification = verify_signed_production_evidence_status_snapshot(
            raw,
            expected_snapshot_sha256=document.get("snapshot_sha256"),
            expected_permit_sha256=permit_sha256,
            expected_run_id_sha256=run_id_sha256,
            expected_lane=lane,
            expected_custodian_identity_sha256=custodian_identity_sha256,
            expected_enrolled_host_identity_sha256=enrolled_host_identity_sha256,
            trusted_authority_keys=trusted_authority_keys,
            checked_at=checked if is_current else issued,
            minimum_trusted_sequence=document.get("status_sequence"),
            minimum_trusted_external_log_checkpoint_sha256=(
                expected_current_checkpoint_sha256
                if is_current
                else document.get("external_log_checkpoint_sha256")
            ),
            minimum_trusted_issued_at=issued,
            expected_previous_snapshot_sha256=(
                None if previous is None else previous.snapshot_sha256
            ),
            revoked_authority_key_ids=revoked_authority_key_ids,
            previous_verified_snapshot=previous,
        )
        verifications.append(verification)
        previous = verification
    current = verifications[-1]
    if current.snapshot_sha256 != _require_sha256(
        expected_current_snapshot_sha256,
        name="expected current status snapshot",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "status lineage does not terminate at the out-of-band current snapshot"
        )
    return tuple(verifications), raw_sources


def _require_status_fresh_for_time(
    status: ProductionEvidenceStatusSnapshotVerification,
    *,
    at: datetime,
    name: str,
) -> None:
    issued = _parse_utc(status.issued_at_utc, name=f"{name} issued_at")
    if issued > at or at - issued > PRODUCTION_STATUS_SNAPSHOT_MAX_AGE:
        raise ValidationProductionEvidenceCustodyError(
            f"{name} is retroactive or stale"
        )


def _require_current_status_allows_event(
    status: ProductionEvidenceStatusSnapshotVerification,
    *,
    payload: Mapping[str, Any],
    event_sha256: str,
    raw_sha256: str,
    from_anchor: CustodyRoleTrustAnchor,
    to_anchor: CustodyRoleTrustAnchor,
) -> None:
    revoked_key_ids = {key_id for _role, key_id in status.revoked_key_rows}
    if payload["from_key_id"] in revoked_key_ids or (
        payload["to_key_id"] in revoked_key_ids
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody event uses a currently revoked role key"
        )
    stage = payload["artifact_stage"]
    if status.artifact_is_revoked(stage, raw_sha256) or status.artifact_is_superseded(
        stage,
        raw_sha256,
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody raw carrier is currently revoked or superseded"
        )
    if status.artifact_is_revoked(
        "custody_event",
        event_sha256,
    ) or status.artifact_is_superseded("custody_event", event_sha256):
        raise ValidationProductionEvidenceCustodyError(
            "custody event is currently revoked or superseded"
        )


def _require_current_status_allows_evidence_lineage(
    status: ProductionEvidenceStatusSnapshotVerification,
    *,
    permit: ProductionEvidencePermitVerification,
    permit_raw_sha256: str,
    status_lineage: Sequence[ProductionEvidenceStatusSnapshotVerification],
    status_raw_sha256s: Sequence[str],
) -> None:
    revoked_key_ids = {key_id for _role, key_id in status.revoked_key_rows}
    if permit.authority_key_id in revoked_key_ids or any(
        ancestor.authority_key_id in revoked_key_ids for ancestor in status_lineage
    ):
        raise ValidationProductionEvidenceCustodyError(
            "permit or status lineage uses a currently revoked authority key"
        )
    if len(status_lineage) != len(status_raw_sha256s):
        raise ValidationProductionEvidenceCustodyError(
            "status lineage raw identity count is inconsistent"
        )

    def require_identities_allowed(
        *,
        artifact_kinds: Sequence[str],
        artifact_sha256s: Sequence[str],
        name: str,
    ) -> None:
        for artifact_kind in artifact_kinds:
            for artifact_sha256 in artifact_sha256s:
                identity = _require_sha256(
                    artifact_sha256,
                    name=f"{name} artifact identity",
                )
                if status.artifact_is_revoked(
                    artifact_kind,
                    identity,
                ) or status.artifact_is_superseded(artifact_kind, identity):
                    raise ValidationProductionEvidenceCustodyError(
                        f"{name} is currently revoked or superseded"
                    )

    require_identities_allowed(
        artifact_kinds=("production_permit", "permit"),
        artifact_sha256s=(permit.permit_sha256, permit_raw_sha256),
        name="permit lineage artifact",
    )
    for ancestor, raw_sha256 in zip(
        status_lineage,
        status_raw_sha256s,
        strict=True,
    ):
        require_identities_allowed(
            artifact_kinds=("status_snapshot",),
            artifact_sha256s=(ancestor.snapshot_sha256, raw_sha256),
            name="status lineage artifact",
        )


def verify_signed_production_custody_event(
    source: str | bytes | Mapping[str, Any],
    *,
    raw_artifact_bytes: bytes,
    expected_custody_event_sha256: str,
    trusted_custody_keys: Mapping[str, CustodyRoleTrustAnchor],
    trusted_authority_keys: Mapping[str, EvidenceAuthorityTrustAnchor],
    checked_at: datetime,
    expected_inner_schema_id: str,
    expected_artifact_stage: str,
    expected_prior_custody_event_sha256: str | None,
    expected_custody_sequence: int,
    expected_permit_sha256: str,
    expected_run_id_sha256: str,
    expected_lane: str,
    expected_custodian_identity_sha256: str,
    expected_enrolled_host_identity_sha256: str,
    expected_from_role: str,
    expected_from_role_identity_sha256: str,
    expected_from_key_id: str,
    expected_to_role: str,
    expected_to_role_identity_sha256: str,
    expected_to_key_id: str,
    permit_source: str | bytes | Mapping[str, Any],
    permit_verification_arguments: Mapping[str, Any],
    verified_permit: ProductionEvidencePermitVerification,
    status_lineage_sources: Sequence[str | bytes | Mapping[str, Any]],
    expected_current_status_snapshot_sha256: str,
    expected_current_status_checkpoint_sha256: str,
    verified_handoff_status_snapshot: ProductionEvidenceStatusSnapshotVerification,
    verified_current_status_snapshot: ProductionEvidenceStatusSnapshotVerification,
    revoked_authority_key_ids: Sequence[str],
    previous_event_source: str | bytes | Mapping[str, Any] | None = None,
    previous_raw_artifact_bytes: bytes | None = None,
    previous_verified_event: ProductionCustodyEventVerification | None = None,
) -> ProductionCustodyEventVerification:
    """Reverify raw authority and custody carriers before issuing a sealed receipt."""

    checked = _checked_time(checked_at)
    _require_globally_separated_trust_maps(
        trusted_authority_keys,
        trusted_custody_keys,
    )
    _require_sealed_verification(
        verified_permit,
        ProductionEvidencePermitVerification,
        name="production permit",
    )
    _require_sealed_verification(
        verified_handoff_status_snapshot,
        ProductionEvidenceStatusSnapshotVerification,
        name="handoff status snapshot",
    )
    _require_sealed_verification(
        verified_current_status_snapshot,
        ProductionEvidenceStatusSnapshotVerification,
        name="current status snapshot",
    )
    (
        payload,
        event_sha256,
        from_anchor,
        to_anchor,
        from_public_key_sha256,
        to_public_key_sha256,
    ) = _verify_custody_carrier(
        source,
        trusted_custody_keys=trusted_custody_keys,
    )
    if event_sha256 != _require_sha256(
        expected_custody_event_sha256,
        name="expected custody event",
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody event is cross-wired to its out-of-band identity"
        )
    handed_off = _parse_utc(payload["handed_off_at_utc"], name="custody handed_off_at")
    received = _parse_utc(payload["received_at_utc"], name="custody received_at")
    if checked < received:
        raise ValidationProductionEvidenceCustodyError("custody event is not yet valid")

    if (
        type(permit_verification_arguments) is not dict
        or len(permit_verification_arguments)
        != len(_PERMIT_REVERIFICATION_ARGUMENT_KEYS)
        or set(permit_verification_arguments) != _PERMIT_REVERIFICATION_ARGUMENT_KEYS
    ):
        raise ValidationProductionEvidenceCustodyError(
            "permit reverification arguments do not match the exact allowed keys"
        )
    _contract_bundle_rows(
        permit_verification_arguments["expected_contract_bundle_sha256_rows"]
    )
    _require_argv(permit_verification_arguments["expected_command_argv"])
    for scalar_name in (
        "expected_permit_id_sha256",
        "expected_study_id_sha256",
        "expected_authorization_nonce_sha256",
        "expected_source_sha256",
        "expected_source_manifest_sha256",
        "expected_dependency_manifest_sha256",
        "expected_runtime_manifest_sha256",
        "expected_artifact_output_root_identity_sha256",
        "expected_external_log_checkpoint_sha256",
    ):
        _require_sha256(
            permit_verification_arguments[scalar_name],
            name=f"reverification {scalar_name}",
        )
    _require_commit_sha(
        permit_verification_arguments["expected_code_commit_sha"],
        name="reverification code commit",
    )
    _require_seed(permit_verification_arguments["expected_seed"])
    _require_sequence(
        permit_verification_arguments["minimum_external_log_sequence"],
        name="reverification minimum external log sequence",
    )
    nested_revoked_authority_key_ids = _external_key_id_set(
        permit_verification_arguments["revoked_authority_key_ids"],
        name="reverification revoked authority key id",
    )
    current_revoked_authority_key_ids = _external_key_id_set(
        revoked_authority_key_ids,
        name="current revoked authority key id",
    )
    if nested_revoked_authority_key_ids != current_revoked_authority_key_ids:
        raise ValidationProductionEvidenceCustodyError(
            "permit and status authority revocation inputs differ"
        )
    for sequence_name in (
        "revoked_permit_sha256s",
        "superseded_permit_sha256s",
        "consumed_permit_sha256s",
    ):
        _external_sha256_set(
            permit_verification_arguments[sequence_name],
            name=f"reverification {sequence_name}",
        )
    if (
        len(_canonical_bytes(dict(permit_verification_arguments)))
        > PRODUCTION_EVIDENCE_MAX_PERMIT_REVERIFICATION_ARGUMENT_BYTES
    ):
        raise ValidationProductionEvidenceCustodyError(
            "permit reverification arguments exceed the fixed byte bound"
        )
    permit_arguments = dict(permit_verification_arguments)
    normalized_revoked_authority_key_ids = tuple(
        sorted(current_revoked_authority_key_ids)
    )
    permit_arguments["revoked_authority_key_ids"] = normalized_revoked_authority_key_ids
    permit_arguments.update(
        {
            "expected_permit_sha256": expected_permit_sha256,
            "trusted_authority_keys": trusted_authority_keys,
            "checked_at": handed_off,
            "expected_lane": expected_lane,
            "expected_run_id_sha256": expected_run_id_sha256,
            "expected_custodian_identity_sha256": expected_custodian_identity_sha256,
            "expected_enrolled_host_identity_sha256": (
                expected_enrolled_host_identity_sha256
            ),
        }
    )
    reverified_permit = verify_signed_production_evidence_permit(
        permit_source,
        **permit_arguments,
    )
    if (
        reverified_permit.permit_sha256 != verified_permit.permit_sha256
        or reverified_permit.authority_public_key_sha256
        != verified_permit.authority_public_key_sha256
        or reverified_permit.permit_sha256 != expected_permit_sha256
    ):
        raise ValidationProductionEvidenceCustodyError(
            "sealed permit does not match the internally reverified raw permit"
        )
    permit_issued = _parse_utc(
        reverified_permit.issued_at_utc,
        name="permit issued_at",
    )
    permit_expires = _parse_utc(
        reverified_permit.expires_at_utc,
        name="permit expires_at",
    )
    if not permit_issued <= handed_off < permit_expires:
        raise ValidationProductionEvidenceCustodyError(
            "custody handoff is outside the permit validity interval"
        )
    permit_raw_source_bytes = _source_canonical_bytes(
        permit_source,
        name="raw permit carrier",
    )

    status_lineage, status_raw_sources = _reverify_status_lineage(
        status_lineage_sources,
        trusted_authority_keys=trusted_authority_keys,
        revoked_authority_key_ids=normalized_revoked_authority_key_ids,
        checked_at=checked,
        expected_current_snapshot_sha256=expected_current_status_snapshot_sha256,
        expected_current_checkpoint_sha256=(expected_current_status_checkpoint_sha256),
        permit_sha256=expected_permit_sha256,
        run_id_sha256=expected_run_id_sha256,
        lane=expected_lane,
        custodian_identity_sha256=expected_custodian_identity_sha256,
        enrolled_host_identity_sha256=expected_enrolled_host_identity_sha256,
    )
    current_status = status_lineage[-1]
    status_by_sha = {status.snapshot_sha256: status for status in status_lineage}
    handoff_status = status_by_sha.get(payload["status_snapshot_sha256"])
    if handoff_status is None:
        raise ValidationProductionEvidenceCustodyError(
            "current status is not a descendant of the embedded handoff status"
        )
    if (
        handoff_status.snapshot_sha256
        != verified_handoff_status_snapshot.snapshot_sha256
        or handoff_status.authority_public_key_sha256
        != verified_handoff_status_snapshot.authority_public_key_sha256
        or handoff_status.lineage_snapshot_sha256s
        != verified_handoff_status_snapshot.lineage_snapshot_sha256s
        or current_status.snapshot_sha256
        != verified_current_status_snapshot.snapshot_sha256
        or current_status.authority_public_key_sha256
        != verified_current_status_snapshot.authority_public_key_sha256
        or current_status.lineage_snapshot_sha256s
        != verified_current_status_snapshot.lineage_snapshot_sha256s
    ):
        raise ValidationProductionEvidenceCustodyError(
            "sealed status receipt does not match the internally reverified lineage"
        )
    _require_status_fresh_for_time(
        handoff_status,
        at=handed_off,
        name="handoff status snapshot",
    )
    _require_status_fresh_for_time(
        current_status,
        at=checked,
        name="current status snapshot",
    )
    current_checked = _parse_utc(
        verified_current_status_snapshot.checked_at_utc,
        name="current status checked_at",
    )
    if (
        current_checked > checked
        or checked - current_checked > PRODUCTION_STATUS_SNAPSHOT_MAX_AGE
    ):
        raise ValidationProductionEvidenceCustodyError(
            "current status verification receipt is future-dated or stale"
        )
    _require_current_status_allows_evidence_lineage(
        current_status,
        permit=reverified_permit,
        permit_raw_sha256=_raw_sha256(permit_raw_source_bytes),
        status_lineage=status_lineage,
        status_raw_sha256s=tuple(
            _raw_sha256(raw_source) for raw_source in status_raw_sources
        ),
    )

    authority_public_keys = {
        reverified_permit.authority_public_key_sha256,
        *(status.authority_public_key_sha256 for status in status_lineage),
    }
    if (
        from_public_key_sha256 in authority_public_keys
        or to_public_key_sha256 in authority_public_keys
    ):
        raise ValidationProductionEvidenceCustodyError(
            "custody key material is reused as permit or status authority material"
        )

    raw_sha256 = _raw_sha256(raw_artifact_bytes)
    if payload["raw_artifact_sha256"] != raw_sha256 or payload[
        "raw_artifact_byte_count"
    ] != len(raw_artifact_bytes):
        raise ValidationProductionEvidenceCustodyError(
            "custody event raw carrier bytes are substituted"
        )
    inner = _load_inner_artifact(
        raw_artifact_bytes,
        artifact_stage=expected_artifact_stage,
        expected_schema_id=expected_inner_schema_id,
        permit_sha256=expected_permit_sha256,
        run_id_sha256=expected_run_id_sha256,
        lane=expected_lane,
        custodian_identity_sha256=expected_custodian_identity_sha256,
        enrolled_host_identity_sha256=expected_enrolled_host_identity_sha256,
    )
    if expected_artifact_stage == "production_permit":
        if raw_artifact_bytes != permit_raw_source_bytes:
            raise ValidationProductionEvidenceCustodyError(
                "custodied permit bytes differ from the reverified permit carrier"
            )
    else:
        matching_status_raw = status_raw_sources[
            tuple(status_by_sha).index(handoff_status.snapshot_sha256)
        ]
        if (
            inner.get("snapshot_sha256") != handoff_status.snapshot_sha256
            or raw_artifact_bytes != matching_status_raw
        ):
            raise ValidationProductionEvidenceCustodyError(
                "custodied status bytes differ from the reverified handoff snapshot"
            )

    expected_projection = _custody_projection(
        raw_artifact_sha256=raw_sha256,
        raw_artifact_byte_count=len(raw_artifact_bytes),
        inner_schema_id=expected_inner_schema_id,
        artifact_stage=expected_artifact_stage,
        prior_custody_event_sha256=expected_prior_custody_event_sha256,
        custody_sequence=expected_custody_sequence,
        permit_sha256=expected_permit_sha256,
        run_id_sha256=expected_run_id_sha256,
        lane=expected_lane,
        custodian_identity_sha256=expected_custodian_identity_sha256,
        enrolled_host_identity_sha256=expected_enrolled_host_identity_sha256,
        from_role=expected_from_role,
        from_role_identity_sha256=expected_from_role_identity_sha256,
        from_key_id=expected_from_key_id,
        to_role=expected_to_role,
        to_role_identity_sha256=expected_to_role_identity_sha256,
        to_key_id=expected_to_key_id,
        handed_off_at_utc=payload["handed_off_at_utc"],
        received_at_utc=payload["received_at_utc"],
        status_snapshot_sha256=handoff_status.snapshot_sha256,
    )
    if payload != expected_projection:
        raise ValidationProductionEvidenceCustodyError(
            "custody event fields are omitted, reordered, or transplanted"
        )
    _require_current_status_allows_event(
        current_status,
        payload=payload,
        event_sha256=event_sha256,
        raw_sha256=raw_sha256,
        from_anchor=from_anchor,
        to_anchor=to_anchor,
    )

    if expected_custody_sequence == 1:
        if any(
            value is not None
            for value in (
                previous_event_source,
                previous_raw_artifact_bytes,
                previous_verified_event,
            )
        ):
            raise ValidationProductionEvidenceCustodyError(
                "initial custody event cannot have a predecessor"
            )
        if expected_from_role_identity_sha256 != expected_custodian_identity_sha256:
            raise ValidationProductionEvidenceCustodyError(
                "initial custody sender must be the permit custodian"
            )
        lineage_hashes = (event_sha256,)
        lineage_stages = (expected_artifact_stage,)
    else:
        _require_sealed_verification(
            previous_verified_event,
            ProductionCustodyEventVerification,
            name="previous custody event",
        )
        if previous_event_source is None or previous_raw_artifact_bytes is None:
            raise ValidationProductionEvidenceCustodyError(
                "non-initial custody event requires raw predecessor evidence"
            )
        (
            previous_payload,
            previous_event_sha256,
            previous_from_anchor,
            previous_to_anchor,
            previous_from_public_key_sha256,
            previous_to_public_key_sha256,
        ) = _verify_custody_carrier(
            previous_event_source,
            trusted_custody_keys=trusted_custody_keys,
        )
        previous_raw_sha256 = _raw_sha256(previous_raw_artifact_bytes)
        if (
            previous_payload["raw_artifact_sha256"] != previous_raw_sha256
            or previous_payload["raw_artifact_byte_count"]
            != len(previous_raw_artifact_bytes)
            or previous_raw_artifact_bytes != permit_raw_source_bytes
        ):
            raise ValidationProductionEvidenceCustodyError(
                "previous custody raw permit carrier is missing or substituted"
            )
        _load_inner_artifact(
            previous_raw_artifact_bytes,
            artifact_stage="production_permit",
            expected_schema_id=PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
            permit_sha256=expected_permit_sha256,
            run_id_sha256=expected_run_id_sha256,
            lane=expected_lane,
            custodian_identity_sha256=expected_custodian_identity_sha256,
            enrolled_host_identity_sha256=expected_enrolled_host_identity_sha256,
        )
        previous_handed_off = _parse_utc(
            previous_payload["handed_off_at_utc"],
            name="previous custody handed_off_at",
        )
        previous_received = _parse_utc(
            previous_payload["received_at_utc"],
            name="previous custody received_at",
        )
        if previous_received > handed_off:
            raise ValidationProductionEvidenceCustodyError(
                "custody successor is handed off before its predecessor is received"
            )
        if not permit_issued <= previous_handed_off < permit_expires:
            raise ValidationProductionEvidenceCustodyError(
                "previous custody handoff is outside the permit validity interval"
            )
        previous_handoff_status = status_by_sha.get(
            previous_payload["status_snapshot_sha256"]
        )
        if previous_handoff_status is None:
            raise ValidationProductionEvidenceCustodyError(
                "current status is not a descendant of previous handoff status"
            )
        _require_status_fresh_for_time(
            previous_handoff_status,
            at=previous_handed_off,
            name="previous handoff status snapshot",
        )
        _require_current_status_allows_event(
            current_status,
            payload=previous_payload,
            event_sha256=previous_event_sha256,
            raw_sha256=previous_raw_sha256,
            from_anchor=previous_from_anchor,
            to_anchor=previous_to_anchor,
        )
        if (
            previous_payload["custody_sequence"] + 1 != expected_custody_sequence
            or previous_event_sha256 != expected_prior_custody_event_sha256
            or previous_payload["artifact_stage"] != "production_permit"
            or previous_payload["inner_schema_id"]
            != PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID
            or previous_payload["prior_custody_event_sha256"] is not None
            or previous_payload["from_role_identity_sha256"]
            != expected_custodian_identity_sha256
            or expected_artifact_stage
            not in _CUSTODY_STAGE_TRANSITIONS[previous_payload["artifact_stage"]]
            or previous_payload["permit_sha256"] != expected_permit_sha256
            or previous_payload["run_id_sha256"] != expected_run_id_sha256
            or previous_payload["lane"] != expected_lane
            or previous_payload["custodian_identity_sha256"]
            != expected_custodian_identity_sha256
            or previous_payload["enrolled_host_identity_sha256"]
            != expected_enrolled_host_identity_sha256
            or previous_payload["to_role"] != expected_from_role
            or previous_payload["to_role_identity_sha256"]
            != expected_from_role_identity_sha256
            or previous_payload["to_key_id"] != expected_from_key_id
            or previous_to_public_key_sha256 != from_public_key_sha256
        ):
            raise ValidationProductionEvidenceCustodyError(
                "custody predecessor continuity, context, or stage transition failed"
            )
        if (
            previous_verified_event.custody_event_sha256 != previous_event_sha256
            or previous_verified_event.raw_artifact_sha256 != previous_raw_sha256
            or previous_verified_event.raw_artifact_byte_count
            != len(previous_raw_artifact_bytes)
            or previous_verified_event.artifact_stage
            != previous_payload["artifact_stage"]
            or previous_verified_event.custody_sequence
            != previous_payload["custody_sequence"]
            or previous_verified_event.prior_custody_event_sha256
            != previous_payload["prior_custody_event_sha256"]
            or previous_verified_event.permit_sha256
            != previous_payload["permit_sha256"]
            or previous_verified_event.run_id_sha256
            != previous_payload["run_id_sha256"]
            or previous_verified_event.lane != previous_payload["lane"]
            or previous_verified_event.custodian_identity_sha256
            != previous_payload["custodian_identity_sha256"]
            or previous_verified_event.enrolled_host_identity_sha256
            != previous_payload["enrolled_host_identity_sha256"]
            or previous_verified_event.from_role != previous_payload["from_role"]
            or previous_verified_event.from_role_identity_sha256
            != previous_payload["from_role_identity_sha256"]
            or previous_verified_event.from_key_id != previous_payload["from_key_id"]
            or previous_verified_event.from_public_key_sha256
            != previous_from_public_key_sha256
            or previous_verified_event.to_role != previous_payload["to_role"]
            or previous_verified_event.to_role_identity_sha256
            != previous_payload["to_role_identity_sha256"]
            or previous_verified_event.to_key_id != previous_payload["to_key_id"]
            or previous_verified_event.to_public_key_sha256
            != previous_to_public_key_sha256
            or previous_verified_event.handed_off_at_utc
            != previous_payload["handed_off_at_utc"]
            or previous_verified_event.received_at_utc
            != previous_payload["received_at_utc"]
            or previous_verified_event.handoff_status_snapshot_sha256
            != previous_payload["status_snapshot_sha256"]
            or previous_verified_event.current_status_snapshot_sha256
            not in status_by_sha
            or previous_verified_event.lineage_custody_event_sha256s
            != (previous_event_sha256,)
            or previous_verified_event.lineage_artifact_stages != ("production_permit",)
        ):
            raise ValidationProductionEvidenceCustodyError(
                "sealed predecessor does not match its internally reverified raw event"
            )
        if (
            previous_from_public_key_sha256 in authority_public_keys
            or previous_to_public_key_sha256 in authority_public_keys
        ):
            raise ValidationProductionEvidenceCustodyError(
                "previous custody key material reuses authority material"
            )
        lineage_hashes = (previous_event_sha256, event_sha256)
        lineage_stages = ("production_permit", "status_snapshot")

    return _new_sealed_verification(
        ProductionCustodyEventVerification,
        custody_event_sha256=event_sha256,
        raw_artifact_sha256=raw_sha256,
        raw_artifact_byte_count=len(raw_artifact_bytes),
        artifact_stage=expected_artifact_stage,
        custody_sequence=expected_custody_sequence,
        prior_custody_event_sha256=expected_prior_custody_event_sha256,
        permit_sha256=expected_permit_sha256,
        run_id_sha256=expected_run_id_sha256,
        lane=expected_lane,
        custodian_identity_sha256=expected_custodian_identity_sha256,
        enrolled_host_identity_sha256=expected_enrolled_host_identity_sha256,
        from_role=expected_from_role,
        from_role_identity_sha256=expected_from_role_identity_sha256,
        from_key_id=expected_from_key_id,
        from_public_key_sha256=from_public_key_sha256,
        to_role=expected_to_role,
        to_role_identity_sha256=expected_to_role_identity_sha256,
        to_key_id=expected_to_key_id,
        to_public_key_sha256=to_public_key_sha256,
        handed_off_at_utc=payload["handed_off_at_utc"],
        received_at_utc=payload["received_at_utc"],
        handoff_status_snapshot_sha256=handoff_status.snapshot_sha256,
        current_status_snapshot_sha256=current_status.snapshot_sha256,
        lineage_custody_event_sha256s=lineage_hashes,
        lineage_artifact_stages=lineage_stages,
        checked_at_utc=_format_utc(checked, name="custody checked_at"),
    )


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SCHEMA_ID,
        "contract_id": VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_ID,
        "contract_version": VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_VERSION,
        "frozen_at_utc": VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_FROZEN_AT_UTC,
        "purpose": {
            "common_foundation_only": True,
            "final_production_wrapper_implemented": False,
            "actual_production_evidence_present": False,
            "test_only_artifact_upgrade_allowed": False,
            "claim_promotion_allowed": False,
        },
        "evidence_class": {
            "exact_value": PRODUCTION_EVIDENCE_CLASS,
            "lanes": list(PRODUCTION_EVIDENCE_LANES),
            "missing_mixed_legacy_or_downgraded_class_allowed": False,
            "class_must_be_signed_at_every_carrier": True,
        },
        "permit": {
            "schema_id": PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID,
            "signature_algorithm": PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM,
            "one_use_intent_only": True,
            "one_use_enforced": False,
            "verification_consumes_permit": False,
            "global_atomic_compare_and_set_consumption_registry_required": True,
            "maximum_validity_seconds": int(
                PRODUCTION_EVIDENCE_PERMIT_MAX_VALIDITY.total_seconds()
            ),
            "pre_execution_external_log_sequence_and_checkpoint_required": True,
            "out_of_band_authority_public_key_required": True,
            "exact_run_lane_contract_source_dependency_runtime_host_and_custodian_binding_required": True,
            "revocation_supersession_and_consumption_inputs_required": True,
        },
        "status_snapshot": {
            "schema_id": PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID,
            "signature_algorithm": PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM,
            "maximum_age_seconds": int(
                PRODUCTION_STATUS_SNAPSHOT_MAX_AGE.total_seconds()
            ),
            "monotonic_sequence_checkpoint_and_previous_hash_required": True,
            "verified_predecessor_and_monotonic_row_accumulation_required": True,
            "canonical_revoked_key_and_artifact_rows_required": True,
            "canonical_nonforking_supersession_rows_required": True,
            "trusted_minimum_sequence_checkpoint_and_time_required": True,
            "full_verified_ancestor_lineage_required": True,
            "permit_run_lane_host_and_custodian_context_required": True,
            "current_authority_key_revocation_applies_to_full_permit_and_status_lineage": True,
            "current_artifact_revocation_and_supersession_apply_to_full_permit_and_status_lineage": True,
            "permit_logical_and_signed_carrier_identities_checked": True,
            "status_logical_and_signed_carrier_identities_checked": True,
            "current_snapshot_self_revocation_or_supersession_allowed": False,
            "single_exact_external_authority_revocation_source_required": True,
        },
        "custody_event": {
            "schema_id": PRODUCTION_CUSTODY_EVENT_SCHEMA_ID,
            "signature_algorithm": PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM,
            "dual_distinct_role_identity_and_key_signatures_required": True,
            "exact_canonical_raw_artifact_hash_size_and_inner_schema_required": True,
            "raw_permit_status_and_predecessor_reverification_required": True,
            "permit_run_lane_host_custodian_and_status_binding_required": True,
            "predecessor_receiver_to_sender_continuity_required": True,
            "predecessor_received_before_successor_handoff_required": True,
            "initial_sender_must_equal_permit_custodian": True,
            "sealed_predecessor_full_raw_field_match_required": True,
            "custody_successor_uniqueness_enforced": False,
            "custody_fork_prevention_requires_external_log": True,
            "verified_stage_sequence": ["production_permit", "status_snapshot"],
            "maximum_verified_sequence": 2,
            "planned_only_stages": list(_CUSTODY_PLANNED_ONLY_STAGES),
            "post_status_snapshot_stage_implemented": False,
            "maximum_handoff_seconds": int(
                PRODUCTION_CUSTODY_HANDOFF_MAX_DURATION.total_seconds()
            ),
            "verifiable_stage_schema_allowlist": dict(
                _CUSTODY_VERIFIABLE_STAGE_SCHEMA_IDS
            ),
        },
        "key_policy": {
            "repository_bundles_private_key": False,
            "repository_bundles_trusted_public_key": False,
            "authority_and_custody_keys_are_out_of_band": True,
            "role_key_cross_use_allowed": False,
            "global_public_key_and_role_identity_aliases_allowed": False,
            "custody_authority_key_material_reuse_allowed": False,
        },
        "resource_limits": {
            "signed_transport_max_bytes": PRODUCTION_EVIDENCE_MAX_SIGNED_TRANSPORT_BYTES,
            "argv_max_items": PRODUCTION_EVIDENCE_MAX_ARGV_ITEMS,
            "argv_item_max_bytes": PRODUCTION_EVIDENCE_MAX_ARGV_ITEM_BYTES,
            "argv_total_max_bytes": PRODUCTION_EVIDENCE_MAX_ARGV_TOTAL_BYTES,
            "contract_bundle_max_rows": PRODUCTION_EVIDENCE_MAX_CONTRACT_BUNDLE_ROWS,
            "status_rows_max_per_kind": PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND,
            "external_sequence_max_items": PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_ITEMS,
            "external_sequence_max_total_bytes": (
                PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_TOTAL_BYTES
            ),
            "trust_anchor_max_items": PRODUCTION_EVIDENCE_MAX_TRUST_ANCHORS,
            "status_lineage_max_items": PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_ITEMS,
            "status_lineage_max_total_bytes": (
                PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_TOTAL_BYTES
            ),
            "permit_reverification_argument_max_bytes": (
                PRODUCTION_EVIDENCE_MAX_PERMIT_REVERIFICATION_ARGUMENT_BYTES
            ),
            "raw_artifact_max_bytes": PRODUCTION_CUSTODY_MAX_RAW_ARTIFACT_BYTES,
            "mapping_source_exact_builtin_dict_and_recursive_preflight_required": True,
        },
        "claim_policy": dict(_CLAIM_POLICY),
        "blockers": list(_BLOCKERS),
    }


def validation_production_evidence_custody_contract_document() -> dict[str, Any]:
    projection = _contract_projection()
    contract_sha256 = _sha256(projection)
    if contract_sha256 != (
        FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256
    ):
        raise ValidationProductionEvidenceCustodyError(
            "frozen production evidence custody contract SHA-256 drifted"
        )
    return {**projection, "contract_sha256": contract_sha256}


def require_validation_production_evidence_custody_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    observed = _load_document(
        payload,
        name="production evidence custody contract",
    )
    expected = validation_production_evidence_custody_contract_document()
    if observed != expected:
        raise ValidationProductionEvidenceCustodyError(
            "production evidence custody contract does not match the frozen record"
        )
    return observed


def validation_production_evidence_custody_decision() -> dict[str, Any]:
    contract = validation_production_evidence_custody_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "common_production_evidence_foundation_implemented": True,
        "final_production_wrapper_implemented": False,
        "production_permit_one_use_enforced": False,
        "maximum_verified_custody_sequence": 2,
        "custody_stages_after_status_snapshot_implemented": False,
        "custody_successor_uniqueness_enforced": False,
        "custody_fork_prevention_requires_external_log": True,
        "actual_production_permit_present": False,
        "trusted_evidence_authority_key_provisioned": False,
        "external_status_log_provisioned": False,
        "enrolled_production_host_present": False,
        "run_custodian_key_provisioned": False,
        "production_custody_chain_present": False,
        "production_validation_results_collected": False,
        "force_or_energy_validated": False,
        "minimization_validated": False,
        "scientifically_validated": False,
        "parameter_fitting_authorized": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "blockers": list(_BLOCKERS),
    }


# Concise public aliases retained for callers that consume this as the common
# production-evidence foundation rather than through the validation namespace.
production_evidence_custody_contract_document = (
    validation_production_evidence_custody_contract_document
)
production_evidence_custody_decision = validation_production_evidence_custody_decision


__all__ = [
    "CustodyRoleTrustAnchor",
    "EvidenceAuthorityTrustAnchor",
    "FROZEN_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256",
    "FROZEN_VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SHA256",
    "PRODUCTION_CUSTODY_EVENT_SCHEMA_ID",
    "PRODUCTION_CUSTODY_HANDOFF_MAX_DURATION",
    "PRODUCTION_EVIDENCE_CLASS",
    "PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_FROZEN_AT_UTC",
    "PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_ID",
    "PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SCHEMA_ID",
    "PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_VERSION",
    "PRODUCTION_EVIDENCE_LANES",
    "PRODUCTION_EVIDENCE_MAX_ARGV_ITEM_BYTES",
    "PRODUCTION_EVIDENCE_MAX_ARGV_ITEMS",
    "PRODUCTION_EVIDENCE_MAX_ARGV_TOTAL_BYTES",
    "PRODUCTION_EVIDENCE_MAX_CONTRACT_BUNDLE_ROWS",
    "PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_ITEMS",
    "PRODUCTION_EVIDENCE_MAX_EXTERNAL_SEQUENCE_TOTAL_BYTES",
    "PRODUCTION_EVIDENCE_MAX_PERMIT_REVERIFICATION_ARGUMENT_BYTES",
    "PRODUCTION_EVIDENCE_MAX_SIGNED_TRANSPORT_BYTES",
    "PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_ITEMS",
    "PRODUCTION_EVIDENCE_MAX_STATUS_LINEAGE_TOTAL_BYTES",
    "PRODUCTION_EVIDENCE_MAX_STATUS_ROWS_PER_KIND",
    "PRODUCTION_EVIDENCE_MAX_TRUST_ANCHORS",
    "SUPPORTED_PRODUCTION_LANES",
    "PRODUCTION_EVIDENCE_PERMIT_MAX_VALIDITY",
    "PRODUCTION_EVIDENCE_PERMIT_SCHEMA_ID",
    "PRODUCTION_EVIDENCE_SIGNATURE_ALGORITHM",
    "PRODUCTION_EVIDENCE_STATUS_SNAPSHOT_SCHEMA_ID",
    "PRODUCTION_STATUS_SNAPSHOT_MAX_AGE",
    "ProductionCustodyEventVerification",
    "ProductionEvidencePermitVerification",
    "ProductionEvidenceStatusSnapshotVerification",
    "VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_ID",
    "VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_SCHEMA_ID",
    "VALIDATION_PRODUCTION_EVIDENCE_CUSTODY_CONTRACT_VERSION",
    "ValidationProductionEvidenceCustodyError",
    "build_signed_production_custody_event",
    "build_signed_production_evidence_permit",
    "build_signed_production_evidence_status_snapshot",
    "require_validation_production_evidence_custody_contract_document",
    "validation_production_evidence_custody_contract_document",
    "validation_production_evidence_custody_decision",
    "production_evidence_custody_contract_document",
    "production_evidence_custody_decision",
    "verify_signed_production_custody_event",
    "verify_signed_production_evidence_permit",
    "verify_signed_production_evidence_status_snapshot",
]
