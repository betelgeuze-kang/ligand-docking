"""Independent preregistration and blind-release custody for pose ranking.

The registration artifact exposes only SHA-256 commitments.  It intentionally
contains no CASF row, label, class count, metric, report, or selected model.
An independently trusted registrar signs that commitment before a separately
trusted validation custodian may sign the exact validation-file release.

Both signatures are execution admission only.  They do not prove dataset
quality, public test performance, scientific validation, or product fitness.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ..docking.calibration import PoseRankingCalibrationPartition
from ..physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    verify_ed25519,
)
from .public_pose_ranking_calibration_partition_intake import (
    PublicPoseRankingCalibrationPartitionIntakeError,
    _canonical_bytes,
    _canonical_sha256,
    _decode_json_object,
    _read_regular_file,
)
from .public_pose_ranking_calibration_training_view import (
    PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES,
    PublicPoseRankingCalibrationTrainingViewReceipt,
)
from .public_pose_ranking_fit_validation_selection import (
    PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_MANIFEST_BYTES,
    PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256,
    PublicPoseRankingFitValidationManifest,
    _hash_regular_file,
    _source_identity as _fit_validation_source_identity,
    load_public_pose_ranking_fit_validation_bound_inputs_from_files,
)


PUBLIC_POSE_RANKING_PREREGISTRATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_preregistration/1.0.0"
)
PUBLIC_POSE_RANKING_PREREGISTRATION_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_preregistration_request/1.0.0"
)
PUBLIC_POSE_RANKING_VALIDATION_RELEASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_validation_release/1.0.0"
)
PUBLIC_POSE_RANKING_VALIDATION_RELEASE_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_validation_release_request/1.0.0"
)
PUBLIC_POSE_RANKING_FIT_VALIDATION_CUSTODY_ADMISSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_fit_validation_"
    "custody_admission/1.0.0"
)
PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM = "ed25519"
PUBLIC_POSE_RANKING_CUSTODY_MAX_VALIDITY = timedelta(days=90)
PUBLIC_POSE_RANKING_CUSTODY_MAX_REQUEST_BYTES = 8 * 1024 * 1024
PUBLIC_POSE_RANKING_CUSTODY_MAX_SIGNED_RECEIPT_BYTES = 8 * 1024 * 1024
PUBLIC_POSE_RANKING_CUSTODY_MAX_ADMISSION_BYTES = 16 * 1024 * 1024

_KEY_ID_RE = re.compile(r"\A[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}\Z")

PUBLIC_POSE_RANKING_CUSTODY_POLICY: Mapping[str, object] = MappingProxyType(
    {
        "signature_algorithm": (
            PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        ),
        "maximum_validity_seconds": int(
            PUBLIC_POSE_RANKING_CUSTODY_MAX_VALIDITY.total_seconds()
        ),
        "registration_output": "sha256_commitments_only",
        "registration_forbidden_observations": (
            "validation_rows",
            "validation_labels",
            "validation_class_counts",
            "validation_metrics",
            "validation_reports",
            "selected_model",
        ),
        "required_distinct_roles": (
            "independent_registrar",
            "training_operator",
            "validation_custodian",
            "evaluation_operator",
        ),
        "release_order": (
            "signed_registration_before_signed_validation_release"
        ),
        "candidate_manifest_after_registration": "immutable",
        "posebusters_test_score_partition": "forbidden",
        "trust_anchors": "out_of_band_public_keys_only",
        "revocation_and_supersession_state": "required_at_verification",
        "secret_signing_material": "forbidden_in_request_receipt_or_cli",
    }
)
PUBLIC_POSE_RANKING_CUSTODY_POLICY_SHA256 = _canonical_sha256(
    dict(PUBLIC_POSE_RANKING_CUSTODY_POLICY)
)

_REGISTRATION_BLOCKERS = (
    "validation_labels_not_yet_released",
    "posebusters_test_evaluation_not_executed",
    "independent_external_rerun_not_executed",
    "confidence_calibration_not_fitted",
    "supported_chemistry_not_validated",
    "scientific_and_product_claims_not_authorized",
)
PUBLIC_POSE_RANKING_CUSTODY_ADMISSION_SCIENTIFIC_BLOCKERS = (
    "signatures_verify_declared_custody_not_human_independence",
    "validation_selection_is_not_posebusters_test_evaluation",
    "selected_model_is_not_independently_reproduced",
    "pose_ranking_confidence_calibration_is_not_fitted",
    "supported_chemistry_applicability_is_not_validated",
    "public_docking_product_claim_is_not_authorized",
)


class PublicPoseRankingFitValidationCustodyError(ValueError):
    """A custody commitment, signature, role, time, or artifact failed closed."""


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _plain_json(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must be an object"
        )
    return {str(key): item for key, item in value.items()}


def _sequence(value: object, *, name: str) -> list[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must be an array"
        )
    return list(value)


def _exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    *,
    name: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} fields differ; "
            f"missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _integer(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must be an integer in [{minimum},{maximum}]"
        )
    return int(value)


def _key_id(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _KEY_ID_RE.fullmatch(value) is None:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} is invalid"
        )
    return value


def _key_bytes(value: object, *, name: str) -> bytes:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise PublicPoseRankingFitValidationCustodyError(
                f"{name} must be hexadecimal"
            ) from exc
    else:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must be raw bytes or hexadecimal"
        )
    if len(raw) != 32:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must contain exactly 32 bytes"
        )
    return raw


def _utc(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must be a UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must be an RFC3339 UTC timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must include UTC"
        )
    parsed = parsed.astimezone(timezone.utc)
    normalized = parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
    if value != normalized:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must use canonical second-precision UTC"
        )
    return normalized


def _parse_utc(value: object, *, name: str) -> datetime:
    return datetime.fromisoformat(
        _utc(value, name=name).replace("Z", "+00:00")
    ).astimezone(timezone.utc)


def _validity_window(
    registered_at_utc: object,
    expires_at_utc: object,
) -> tuple[str, str]:
    registered_text = _utc(registered_at_utc, name="registered_at_utc")
    expires_text = _utc(expires_at_utc, name="expires_at_utc")
    registered = _parse_utc(registered_text, name="registered_at_utc")
    expires = _parse_utc(expires_text, name="expires_at_utc")
    if (
        expires <= registered
        or expires - registered > PUBLIC_POSE_RANKING_CUSTODY_MAX_VALIDITY
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "registration validity window is invalid"
        )
    return registered_text, expires_text


def _reject_private_signing_material(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PublicPoseRankingFitValidationCustodyError(
                    "signing request contains a non-string field"
                )
            lowered = key.lower()
            if (
                "private_key" in lowered
                or "signing_key" in lowered
                or lowered
                in {
                    "secret",
                    "secret_hex",
                    "seed",
                    "seed_hex",
                    "mnemonic",
                }
            ):
                raise PublicPoseRankingFitValidationCustodyError(
                    "signing request contains private signing material"
                )
            _reject_private_signing_material(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_private_signing_material(child)


_REGISTRATION_DISCLOSURE_AUDIT_FIELDS = {
    "validation_commitment_is_label_blind",
    "validation_rows_disclosed",
    "validation_labels_disclosed",
    "validation_class_counts_disclosed",
    "validation_metrics_disclosed",
}


def _reject_registration_observations(value: object) -> None:
    forbidden = (
        "label",
        "native_like",
        "positive",
        "negative",
        "metric",
        "report",
        "selected_model",
        "row_count",
        "case_count",
    )
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if (
                lowered not in _REGISTRATION_DISCLOSURE_AUDIT_FIELDS
                and any(token in lowered for token in forbidden)
            ):
                raise PublicPoseRankingFitValidationCustodyError(
                    "registration exposes a forbidden validation observation"
                )
            _reject_registration_observations(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_registration_observations(child)


def _normalized_digest_state(
    values: Sequence[str],
    *,
    name: str,
) -> tuple[str, ...]:
    normalized = tuple(sorted(_digest(item, name=name) for item in values))
    if len(normalized) != len(set(normalized)):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} contains duplicates"
        )
    return normalized


def _normalized_key_state(
    values: Sequence[str],
    *,
    name: str,
) -> tuple[str, ...]:
    normalized = tuple(
        sorted(_key_id(item, name=name) for item in values)
    )
    if len(normalized) != len(set(normalized)):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} contains duplicates"
        )
    return normalized


def _signature_hex(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 128
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must be a lowercase 64-byte Ed25519 signature"
        )
    return value


@dataclass(frozen=True, slots=True)
class PublicPoseRankingCustodyTrustAnchor:
    """One out-of-band identity and raw Ed25519 public key."""

    identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "identity_sha256",
            _digest(self.identity_sha256, name="trusted identity"),
        )
        object.__setattr__(
            self,
            "verification_key",
            _key_bytes(
                self.verification_key,
                name="trusted Ed25519 public key",
            ),
        )


def _custody_source_identity() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    paths = (
        "betelgeuze_engine_v2/benchmark/"
        "public_pose_ranking_fit_validation_custody.py",
        "betelgeuze_engine_v2/benchmark/"
        "public_pose_ranking_fit_validation_selection.py",
        "betelgeuze_engine_v2/physics/"
        "reference_minimization_validation_ed25519.py",
    )
    rows = [
        {"path": path, **_hash_regular_file(root / path)}
        for path in paths
    ]
    projection = {
        "source_files": rows,
        "source_manifest_sha256": _canonical_sha256(rows),
        "absolute_paths_disclosed": False,
    }
    return {
        **projection,
        "source_identity_sha256": _canonical_sha256(projection),
    }


def _role_identities(
    *,
    registrar_identity_sha256: str,
    training_operator_identity_sha256: str,
    validation_custodian_identity_sha256: str,
    evaluation_operator_identity_sha256: str,
) -> dict[str, str]:
    roles = {
        "registrar_identity_sha256": _digest(
            registrar_identity_sha256,
            name="registrar identity",
        ),
        "training_operator_identity_sha256": _digest(
            training_operator_identity_sha256,
            name="training operator identity",
        ),
        "validation_custodian_identity_sha256": _digest(
            validation_custodian_identity_sha256,
            name="validation custodian identity",
        ),
        "evaluation_operator_identity_sha256": _digest(
            evaluation_operator_identity_sha256,
            name="evaluation operator identity",
        ),
    }
    if len(set(roles.values())) != len(roles):
        raise PublicPoseRankingFitValidationCustodyError(
            "custody roles must have distinct identities"
        )
    return roles


def _validate_bound_inputs(
    *,
    training_view_receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    training_view_receipt_source_file_sha256: str,
    training_view_receipt_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    manifest: PublicPoseRankingFitValidationManifest,
    manifest_source_file_sha256: str,
    manifest_source_file_size_bytes: int,
) -> dict[str, object]:
    if (
        not isinstance(
            training_view_receipt,
            PublicPoseRankingCalibrationTrainingViewReceipt,
        )
        or not training_view_receipt.ready_for_fit
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "custody requires a ready training-view receipt"
        )
    if (
        not isinstance(
            validation_partition,
            PoseRankingCalibrationPartition,
        )
        or validation_partition.split_role != "validation"
        or validation_partition.fingerprint_sha256
        != training_view_receipt.validation_partition.partition_sha256
        or validation_partition.identity_fingerprint_sha256
        != training_view_receipt.validation_partition.partition_identity_sha256
        or len(validation_partition.rows)
        != training_view_receipt.validation_partition.row_count
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation partition is not bound to the training view"
        )
    if (
        not isinstance(manifest, PublicPoseRankingFitValidationManifest)
        or any(
            candidate.config.term_ids
            != training_view_receipt.training_partition.term_ids
            for candidate in manifest.candidates
        )
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "candidate manifest is not bound to the training schema"
        )
    training_file_sha = _digest(
        training_view_receipt_source_file_sha256,
        name="training-view receipt source file SHA-256",
    )
    training_file_size = _integer(
        training_view_receipt_source_file_size_bytes,
        name="training-view receipt source file size",
        minimum=1,
        maximum=(
            PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES
        ),
    )
    manifest_file_sha = _digest(
        manifest_source_file_sha256,
        name="candidate manifest source file SHA-256",
    )
    manifest_file_size = _integer(
        manifest_source_file_size_bytes,
        name="candidate manifest source file size",
        minimum=1,
        maximum=PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_MANIFEST_BYTES,
    )
    validation_identity = training_view_receipt.validation_partition
    return {
        "candidate_manifest_source_file_sha256": manifest_file_sha,
        "candidate_manifest_source_file_size_bytes": manifest_file_size,
        "candidate_manifest_sha256": manifest.manifest_sha256,
        "candidate_count": len(manifest.candidates),
        "candidate_config_sha256s": [
            item.config.fingerprint_sha256
            for item in manifest.candidates
        ],
        "training_view_receipt_source_file_sha256": training_file_sha,
        "training_view_receipt_source_file_size_bytes": training_file_size,
        "training_view_receipt_sha256": (
            training_view_receipt.receipt_sha256
        ),
        "training_partition_sha256": (
            training_view_receipt.training_partition.fingerprint_sha256
        ),
        "training_partition_identity_sha256": (
            training_view_receipt.training_partition.identity_fingerprint_sha256
        ),
        "validation_partition_source_file_sha256": (
            validation_identity.source_file_sha256
        ),
        "validation_partition_source_file_size_bytes": (
            validation_identity.source_file_size_bytes
        ),
        "validation_partition_sha256": (
            validation_partition.fingerprint_sha256
        ),
        "validation_partition_identity_sha256": (
            validation_partition.identity_fingerprint_sha256
        ),
        "fit_validation_leakage_audit_sha256": (
            training_view_receipt.fit_validation_training_leakage_audit.fingerprint_sha256
        ),
    }


_BOUND_INPUT_FIELDS = {
    "candidate_manifest_source_file_sha256",
    "candidate_manifest_source_file_size_bytes",
    "candidate_manifest_sha256",
    "candidate_count",
    "candidate_config_sha256s",
    "training_view_receipt_source_file_sha256",
    "training_view_receipt_source_file_size_bytes",
    "training_view_receipt_sha256",
    "training_partition_sha256",
    "training_partition_identity_sha256",
    "validation_partition_source_file_sha256",
    "validation_partition_source_file_size_bytes",
    "validation_partition_sha256",
    "validation_partition_identity_sha256",
    "fit_validation_leakage_audit_sha256",
}


def _registration_payload(
    *,
    training_view_receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    training_view_receipt_source_file_sha256: str,
    training_view_receipt_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    manifest: PublicPoseRankingFitValidationManifest,
    manifest_source_file_sha256: str,
    manifest_source_file_size_bytes: int,
    registrar_identity_sha256: str,
    registrar_key_id: str,
    training_operator_identity_sha256: str,
    validation_custodian_identity_sha256: str,
    validation_custodian_key_id: str,
    evaluation_operator_identity_sha256: str,
    registered_at_utc: str,
    expires_at_utc: str,
    registration_nonce_sha256: str,
) -> dict[str, object]:
    bound = _validate_bound_inputs(
        training_view_receipt=training_view_receipt,
        training_view_receipt_source_file_sha256=(
            training_view_receipt_source_file_sha256
        ),
        training_view_receipt_source_file_size_bytes=(
            training_view_receipt_source_file_size_bytes
        ),
        validation_partition=validation_partition,
        manifest=manifest,
        manifest_source_file_sha256=manifest_source_file_sha256,
        manifest_source_file_size_bytes=manifest_source_file_size_bytes,
    )
    roles = _role_identities(
        registrar_identity_sha256=registrar_identity_sha256,
        training_operator_identity_sha256=training_operator_identity_sha256,
        validation_custodian_identity_sha256=(
            validation_custodian_identity_sha256
        ),
        evaluation_operator_identity_sha256=(
            evaluation_operator_identity_sha256
        ),
    )
    registrar_key = _key_id(
        registrar_key_id,
        name="registrar key ID",
    )
    custodian_key = _key_id(
        validation_custodian_key_id,
        name="validation custodian key ID",
    )
    if registrar_key == custodian_key:
        raise PublicPoseRankingFitValidationCustodyError(
            "registrar and custodian key IDs must be distinct"
        )
    registered, expires = _validity_window(
        registered_at_utc,
        expires_at_utc,
    )
    nonce = _digest(
        registration_nonce_sha256,
        name="registration nonce",
    )
    if nonce in {
        *roles.values(),
        bound["candidate_manifest_sha256"],
        bound["training_view_receipt_sha256"],
        bound["validation_partition_sha256"],
    }:
        raise PublicPoseRankingFitValidationCustodyError(
            "registration nonce reuses an identity or evidence digest"
        )
    fit_source = _fit_validation_source_identity()
    custody_source = _custody_source_identity()
    projection: dict[str, object] = {
        "schema_id": PUBLIC_POSE_RANKING_PREREGISTRATION_SCHEMA_ID,
        **bound,
        "selection_policy_sha256": (
            PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256
        ),
        "fit_validation_source_identity": fit_source,
        "fit_validation_source_identity_sha256": (
            fit_source["source_identity_sha256"]
        ),
        "custody_source_identity": custody_source,
        "custody_source_identity_sha256": (
            custody_source["source_identity_sha256"]
        ),
        **roles,
        "registrar_key_id": registrar_key,
        "validation_custodian_key_id": custodian_key,
        "registered_at_utc": registered,
        "expires_at_utc": expires,
        "registration_nonce_sha256": nonce,
        "custody_policy": _plain_json(
            PUBLIC_POSE_RANKING_CUSTODY_POLICY
        ),
        "custody_policy_sha256": (
            PUBLIC_POSE_RANKING_CUSTODY_POLICY_SHA256
        ),
        "validation_commitment_is_label_blind": True,
        "validation_rows_disclosed": False,
        "validation_labels_disclosed": False,
        "validation_class_counts_disclosed": False,
        "validation_metrics_disclosed": False,
        "validation_release_complete": False,
        "candidate_manifest_locked_before_release": True,
        "posebusters_test_score_partition_present": False,
        "signature_algorithm": (
            PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        ),
        "independent_preregistration_declared": True,
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
        "scientific_blockers": list(_REGISTRATION_BLOCKERS),
        "revoked": False,
        "superseded": False,
    }
    _reject_registration_observations(projection)
    return {
        **projection,
        "registration_receipt_sha256": _canonical_sha256(projection),
    }


_REGISTRATION_PAYLOAD_FIELDS = {
    "schema_id",
    *_BOUND_INPUT_FIELDS,
    "selection_policy_sha256",
    "fit_validation_source_identity",
    "fit_validation_source_identity_sha256",
    "custody_source_identity",
    "custody_source_identity_sha256",
    "registrar_identity_sha256",
    "training_operator_identity_sha256",
    "validation_custodian_identity_sha256",
    "evaluation_operator_identity_sha256",
    "registrar_key_id",
    "validation_custodian_key_id",
    "registered_at_utc",
    "expires_at_utc",
    "registration_nonce_sha256",
    "custody_policy",
    "custody_policy_sha256",
    "validation_commitment_is_label_blind",
    "validation_rows_disclosed",
    "validation_labels_disclosed",
    "validation_class_counts_disclosed",
    "validation_metrics_disclosed",
    "validation_release_complete",
    "candidate_manifest_locked_before_release",
    "posebusters_test_score_partition_present",
    "signature_algorithm",
    "independent_preregistration_declared",
    "scientifically_validated",
    "production_eligible",
    "claim_safe",
    "scientific_blockers",
    "revoked",
    "superseded",
    "registration_receipt_sha256",
}


def _require_registration_payload(value: object) -> dict[str, object]:
    payload = _mapping(value, name="preregistration payload")
    _exact_keys(
        payload,
        _REGISTRATION_PAYLOAD_FIELDS,
        name="preregistration payload",
    )
    _reject_private_signing_material(payload)
    _reject_registration_observations(payload)
    digest = _digest(
        payload["registration_receipt_sha256"],
        name="preregistration receipt",
    )
    projection = {
        key: item
        for key, item in payload.items()
        if key != "registration_receipt_sha256"
    }
    if digest != _canonical_sha256(projection):
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration receipt digest is invalid"
        )
    digest_fields = (
        "candidate_manifest_source_file_sha256",
        "candidate_manifest_sha256",
        "training_view_receipt_source_file_sha256",
        "training_view_receipt_sha256",
        "training_partition_sha256",
        "training_partition_identity_sha256",
        "validation_partition_source_file_sha256",
        "validation_partition_sha256",
        "validation_partition_identity_sha256",
        "fit_validation_leakage_audit_sha256",
        "selection_policy_sha256",
        "fit_validation_source_identity_sha256",
        "custody_source_identity_sha256",
        "registrar_identity_sha256",
        "training_operator_identity_sha256",
        "validation_custodian_identity_sha256",
        "evaluation_operator_identity_sha256",
        "registration_nonce_sha256",
        "custody_policy_sha256",
    )
    for name in digest_fields:
        _digest(payload[name], name=name)
    _integer(
        payload["candidate_count"],
        name="candidate count",
        minimum=1,
        maximum=32,
    )
    config_digests = tuple(
        _digest(item, name="candidate config SHA-256")
        for item in _sequence(
            payload["candidate_config_sha256s"],
            name="candidate config SHA-256s",
        )
    )
    if len(config_digests) != payload["candidate_count"]:
        raise PublicPoseRankingFitValidationCustodyError(
            "candidate config commitments are incomplete"
        )
    _integer(
        payload["candidate_manifest_source_file_size_bytes"],
        name="candidate manifest file size",
        minimum=1,
        maximum=PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_MANIFEST_BYTES,
    )
    _integer(
        payload["training_view_receipt_source_file_size_bytes"],
        name="training-view receipt file size",
        minimum=1,
        maximum=(
            PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES
        ),
    )
    _integer(
        payload["validation_partition_source_file_size_bytes"],
        name="validation partition file size",
        minimum=1,
        maximum=512 * 1024 * 1024,
    )
    roles = _role_identities(
        registrar_identity_sha256=str(
            payload["registrar_identity_sha256"]
        ),
        training_operator_identity_sha256=str(
            payload["training_operator_identity_sha256"]
        ),
        validation_custodian_identity_sha256=str(
            payload["validation_custodian_identity_sha256"]
        ),
        evaluation_operator_identity_sha256=str(
            payload["evaluation_operator_identity_sha256"]
        ),
    )
    if any(payload[name] != value for name, value in roles.items()):
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration role identities are invalid"
        )
    _key_id(payload["registrar_key_id"], name="registrar key ID")
    _key_id(
        payload["validation_custodian_key_id"],
        name="validation custodian key ID",
    )
    if payload["registrar_key_id"] == payload[
        "validation_custodian_key_id"
    ]:
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration key roles are aliased"
        )
    _validity_window(
        payload["registered_at_utc"],
        payload["expires_at_utc"],
    )
    booleans = {
        "validation_commitment_is_label_blind": True,
        "validation_rows_disclosed": False,
        "validation_labels_disclosed": False,
        "validation_class_counts_disclosed": False,
        "validation_metrics_disclosed": False,
        "validation_release_complete": False,
        "candidate_manifest_locked_before_release": True,
        "posebusters_test_score_partition_present": False,
        "independent_preregistration_declared": True,
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
        "revoked": False,
        "superseded": False,
    }
    if (
        payload["schema_id"]
        != PUBLIC_POSE_RANKING_PREREGISTRATION_SCHEMA_ID
        or payload["selection_policy_sha256"]
        != PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256
        or payload["custody_policy"]
        != _plain_json(PUBLIC_POSE_RANKING_CUSTODY_POLICY)
        or payload["custody_policy_sha256"]
        != PUBLIC_POSE_RANKING_CUSTODY_POLICY_SHA256
        or payload["signature_algorithm"]
        != PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        or payload["scientific_blockers"]
        != list(_REGISTRATION_BLOCKERS)
        or any(payload[name] is not expected for name, expected in booleans.items())
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration policy or claim boundary is invalid"
        )
    return json.loads(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )


def build_public_pose_ranking_preregistration_signing_request(
    **payload_arguments: Any,
) -> dict[str, object]:
    """Build canonical, label-blind, secret-free registrar signing input."""

    payload = _registration_payload(**payload_arguments)
    projection = {
        "schema_id": (
            PUBLIC_POSE_RANKING_PREREGISTRATION_REQUEST_SCHEMA_ID
        ),
        "signature_algorithm": (
            PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        ),
        "registrar_identity_sha256": (
            payload["registrar_identity_sha256"]
        ),
        "registrar_key_id": payload["registrar_key_id"],
        "registration_payload": payload,
        "signing_bytes_sha256": hashlib.sha256(
            _canonical_bytes(payload)
        ).hexdigest(),
    }
    return {
        **projection,
        "request_sha256": _canonical_sha256(projection),
    }


def require_public_pose_ranking_preregistration_signing_request(
    value: object,
) -> dict[str, object]:
    request = _mapping(value, name="preregistration signing request")
    _reject_private_signing_material(request)
    _exact_keys(
        request,
        {
            "schema_id",
            "signature_algorithm",
            "registrar_identity_sha256",
            "registrar_key_id",
            "registration_payload",
            "signing_bytes_sha256",
            "request_sha256",
        },
        name="preregistration signing request",
    )
    digest = _digest(
        request["request_sha256"],
        name="preregistration request",
    )
    projection = {
        key: item
        for key, item in request.items()
        if key != "request_sha256"
    }
    payload = _require_registration_payload(
        request["registration_payload"]
    )
    if (
        digest != _canonical_sha256(projection)
        or request["schema_id"]
        != PUBLIC_POSE_RANKING_PREREGISTRATION_REQUEST_SCHEMA_ID
        or request["signature_algorithm"]
        != PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        or request["registrar_identity_sha256"]
        != payload["registrar_identity_sha256"]
        or request["registrar_key_id"] != payload["registrar_key_id"]
        or _digest(
            request["signing_bytes_sha256"],
            name="preregistration signing bytes",
        )
        != hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration signing request is cross-wired"
        )
    return {
        **projection,
        "registration_payload": payload,
        "request_sha256": digest,
    }


def public_pose_ranking_preregistration_signing_bytes(
    value: object,
) -> bytes:
    request = require_public_pose_ranking_preregistration_signing_request(
        value
    )
    return _canonical_bytes(request["registration_payload"])


def attach_public_pose_ranking_preregistration_signature(
    request_value: object,
    *,
    signature_hex: str,
    verification_key: bytes | str,
) -> dict[str, object]:
    """Verify and attach a detached registrar signature."""

    request = require_public_pose_ranking_preregistration_signing_request(
        request_value
    )
    public_key = _key_bytes(
        verification_key,
        name="registrar verification key",
    )
    signature = _signature_hex(
        signature_hex,
        name="preregistration signature",
    )
    try:
        verified = verify_ed25519(
            _canonical_bytes(request["registration_payload"]),
            signature,
            public_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration signature verifier is unavailable"
        ) from exc
    if not verified:
        raise PublicPoseRankingFitValidationCustodyError(
            "detached preregistration signature verification failed"
        )
    return {
        **request["registration_payload"],
        "signature": {
            "algorithm": (
                PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
            ),
            "key_id": request["registrar_key_id"],
            "value": signature,
        },
    }


def _signed_payload(
    value: object,
    *,
    receipt_field: str,
    payload_require: Any,
    name: str,
) -> tuple[dict[str, object], dict[str, object]]:
    signed = _mapping(value, name=name)
    signature = _mapping(
        signed.pop("signature", None),
        name=f"{name} signature",
    )
    _exact_keys(
        signature,
        {"algorithm", "key_id", "value"},
        name=f"{name} signature",
    )
    payload = payload_require(signed)
    if (
        signature["algorithm"]
        != PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        or receipt_field not in payload
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} signature envelope is invalid"
        )
    signature["value"] = _signature_hex(
        signature["value"],
        name=f"{name} signature",
    )
    return payload, signature


def _state_allows(
    *,
    key_id: str,
    receipt_sha256: str,
    revoked_key_ids: Sequence[str],
    revoked_receipt_sha256s: Sequence[str],
    superseded_receipt_sha256s: Sequence[str],
    role: str,
) -> None:
    if key_id in _normalized_key_state(
        revoked_key_ids,
        name=f"revoked {role} key ID",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{role} key is revoked"
        )
    if receipt_sha256 in _normalized_digest_state(
        revoked_receipt_sha256s,
        name=f"revoked {role} receipt",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{role} receipt is revoked"
        )
    if receipt_sha256 in _normalized_digest_state(
        superseded_receipt_sha256s,
        name=f"superseded {role} receipt",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{role} receipt is superseded"
        )


def verify_signed_public_pose_ranking_preregistration(
    signed_value: object,
    *,
    training_view_receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    training_view_receipt_source_file_sha256: str,
    training_view_receipt_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    manifest: PublicPoseRankingFitValidationManifest,
    manifest_source_file_sha256: str,
    manifest_source_file_size_bytes: int,
    trusted_registrar_keys: Mapping[
        str, PublicPoseRankingCustodyTrustAnchor
    ],
    checked_at_utc: str,
    revoked_registrar_key_ids: Sequence[str],
    revoked_registration_receipt_sha256s: Sequence[str],
    superseded_registration_receipt_sha256s: Sequence[str],
) -> dict[str, object]:
    """Verify trust, signature, time, state, source, and exact commitments."""

    payload, signature = _signed_payload(
        signed_value,
        receipt_field="registration_receipt_sha256",
        payload_require=_require_registration_payload,
        name="signed preregistration",
    )
    key_id = _key_id(
        signature["key_id"],
        name="registrar signature key ID",
    )
    if key_id != payload["registrar_key_id"]:
        raise PublicPoseRankingFitValidationCustodyError(
            "registrar signature key is cross-wired"
        )
    anchor = trusted_registrar_keys.get(key_id)
    if not isinstance(anchor, PublicPoseRankingCustodyTrustAnchor):
        raise PublicPoseRankingFitValidationCustodyError(
            "registrar key is not trusted"
        )
    if anchor.identity_sha256 != payload["registrar_identity_sha256"]:
        raise PublicPoseRankingFitValidationCustodyError(
            "registrar identity is cross-wired"
        )
    _state_allows(
        key_id=key_id,
        receipt_sha256=str(payload["registration_receipt_sha256"]),
        revoked_key_ids=revoked_registrar_key_ids,
        revoked_receipt_sha256s=(
            revoked_registration_receipt_sha256s
        ),
        superseded_receipt_sha256s=(
            superseded_registration_receipt_sha256s
        ),
        role="registrar",
    )
    try:
        verified = verify_ed25519(
            _canonical_bytes(payload),
            signature["value"],
            anchor.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration signature verifier is unavailable"
        ) from exc
    if not verified:
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration signature verification failed"
        )
    checked = _parse_utc(checked_at_utc, name="checked_at_utc")
    registered = _parse_utc(
        payload["registered_at_utc"],
        name="registered_at_utc",
    )
    expires = _parse_utc(
        payload["expires_at_utc"],
        name="expires_at_utc",
    )
    if not registered <= checked <= expires:
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration is not currently valid"
        )
    expected = _registration_payload(
        training_view_receipt=training_view_receipt,
        training_view_receipt_source_file_sha256=(
            training_view_receipt_source_file_sha256
        ),
        training_view_receipt_source_file_size_bytes=(
            training_view_receipt_source_file_size_bytes
        ),
        validation_partition=validation_partition,
        manifest=manifest,
        manifest_source_file_sha256=manifest_source_file_sha256,
        manifest_source_file_size_bytes=manifest_source_file_size_bytes,
        registrar_identity_sha256=anchor.identity_sha256,
        registrar_key_id=key_id,
        training_operator_identity_sha256=str(
            payload["training_operator_identity_sha256"]
        ),
        validation_custodian_identity_sha256=str(
            payload["validation_custodian_identity_sha256"]
        ),
        validation_custodian_key_id=str(
            payload["validation_custodian_key_id"]
        ),
        evaluation_operator_identity_sha256=str(
            payload["evaluation_operator_identity_sha256"]
        ),
        registered_at_utc=str(payload["registered_at_utc"]),
        expires_at_utc=str(payload["expires_at_utc"]),
        registration_nonce_sha256=str(
            payload["registration_nonce_sha256"]
        ),
    )
    if payload != expected:
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration differs from exact reconstruction"
        )
    return payload


def _release_payload(
    *,
    registration: Mapping[str, object],
    bound_inputs: Mapping[str, object],
    custodian_identity_sha256: str,
    custodian_key_id: str,
    released_at_utc: str,
    release_nonce_sha256: str,
) -> dict[str, object]:
    registration_payload = _require_registration_payload(registration)
    if any(
        registration_payload[name] != bound_inputs[name]
        for name in _BOUND_INPUT_FIELDS
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release inputs differ from preregistration"
        )
    custodian_identity = _digest(
        custodian_identity_sha256,
        name="validation custodian identity",
    )
    key_id = _key_id(
        custodian_key_id,
        name="validation custodian key ID",
    )
    if (
        custodian_identity
        != registration_payload["validation_custodian_identity_sha256"]
        or key_id
        != registration_payload["validation_custodian_key_id"]
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation custodian identity is not preregistered"
        )
    released_text = _utc(released_at_utc, name="released_at_utc")
    released = _parse_utc(released_text, name="released_at_utc")
    registered = _parse_utc(
        registration_payload["registered_at_utc"],
        name="registered_at_utc",
    )
    expires = _parse_utc(
        registration_payload["expires_at_utc"],
        name="expires_at_utc",
    )
    if not registered < released <= expires:
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release must follow registration within validity"
        )
    nonce = _digest(release_nonce_sha256, name="release nonce")
    if nonce in {
        registration_payload["registration_nonce_sha256"],
        custodian_identity,
        registration_payload["validation_partition_sha256"],
    }:
        raise PublicPoseRankingFitValidationCustodyError(
            "release nonce reuses a registration or evidence digest"
        )
    custody_source = _custody_source_identity()
    projection: dict[str, object] = {
        "schema_id": PUBLIC_POSE_RANKING_VALIDATION_RELEASE_SCHEMA_ID,
        "registration_receipt_sha256": (
            registration_payload["registration_receipt_sha256"]
        ),
        **{
            name: bound_inputs[name]
            for name in _BOUND_INPUT_FIELDS
            if name
            not in {
                "candidate_count",
                "candidate_config_sha256s",
            }
        },
        "selection_policy_sha256": (
            registration_payload["selection_policy_sha256"]
        ),
        "fit_validation_source_identity_sha256": (
            registration_payload[
                "fit_validation_source_identity_sha256"
            ]
        ),
        "custody_source_identity": custody_source,
        "custody_source_identity_sha256": (
            custody_source["source_identity_sha256"]
        ),
        "registrar_identity_sha256": (
            registration_payload["registrar_identity_sha256"]
        ),
        "training_operator_identity_sha256": (
            registration_payload["training_operator_identity_sha256"]
        ),
        "validation_custodian_identity_sha256": custodian_identity,
        "evaluation_operator_identity_sha256": (
            registration_payload["evaluation_operator_identity_sha256"]
        ),
        "validation_custodian_key_id": key_id,
        "registered_at_utc": registration_payload["registered_at_utc"],
        "released_at_utc": released_text,
        "expires_at_utc": registration_payload["expires_at_utc"],
        "release_nonce_sha256": nonce,
        "custody_policy_sha256": (
            PUBLIC_POSE_RANKING_CUSTODY_POLICY_SHA256
        ),
        "validation_file_matches_preregistered_commitment": True,
        "validation_labels_released_after_registration": True,
        "candidate_manifest_unchanged_after_registration": True,
        "posebusters_test_score_partition_present": False,
        "signature_algorithm": (
            PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        ),
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
        "scientific_blockers": list(
            PUBLIC_POSE_RANKING_CUSTODY_ADMISSION_SCIENTIFIC_BLOCKERS
        ),
        "revoked": False,
        "superseded": False,
    }
    return {
        **projection,
        "release_receipt_sha256": _canonical_sha256(projection),
    }


_RELEASE_BOUND_FIELDS = _BOUND_INPUT_FIELDS - {
    "candidate_count",
    "candidate_config_sha256s",
}
_RELEASE_PAYLOAD_FIELDS = {
    "schema_id",
    "registration_receipt_sha256",
    *_RELEASE_BOUND_FIELDS,
    "selection_policy_sha256",
    "fit_validation_source_identity_sha256",
    "custody_source_identity",
    "custody_source_identity_sha256",
    "registrar_identity_sha256",
    "training_operator_identity_sha256",
    "validation_custodian_identity_sha256",
    "evaluation_operator_identity_sha256",
    "validation_custodian_key_id",
    "registered_at_utc",
    "released_at_utc",
    "expires_at_utc",
    "release_nonce_sha256",
    "custody_policy_sha256",
    "validation_file_matches_preregistered_commitment",
    "validation_labels_released_after_registration",
    "candidate_manifest_unchanged_after_registration",
    "posebusters_test_score_partition_present",
    "signature_algorithm",
    "scientifically_validated",
    "production_eligible",
    "claim_safe",
    "scientific_blockers",
    "revoked",
    "superseded",
    "release_receipt_sha256",
}


def _require_release_payload(value: object) -> dict[str, object]:
    payload = _mapping(value, name="validation release payload")
    _exact_keys(
        payload,
        _RELEASE_PAYLOAD_FIELDS,
        name="validation release payload",
    )
    _reject_private_signing_material(payload)
    digest = _digest(
        payload["release_receipt_sha256"],
        name="validation release receipt",
    )
    projection = {
        key: item
        for key, item in payload.items()
        if key != "release_receipt_sha256"
    }
    if digest != _canonical_sha256(projection):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release receipt digest is invalid"
        )
    for name in (
        "registration_receipt_sha256",
        "candidate_manifest_source_file_sha256",
        "candidate_manifest_sha256",
        "training_view_receipt_source_file_sha256",
        "training_view_receipt_sha256",
        "training_partition_sha256",
        "training_partition_identity_sha256",
        "validation_partition_source_file_sha256",
        "validation_partition_sha256",
        "validation_partition_identity_sha256",
        "fit_validation_leakage_audit_sha256",
        "selection_policy_sha256",
        "fit_validation_source_identity_sha256",
        "custody_source_identity_sha256",
        "registrar_identity_sha256",
        "training_operator_identity_sha256",
        "validation_custodian_identity_sha256",
        "evaluation_operator_identity_sha256",
        "release_nonce_sha256",
        "custody_policy_sha256",
    ):
        _digest(payload[name], name=name)
    _validity_window(
        payload["registered_at_utc"],
        payload["expires_at_utc"],
    )
    released = _parse_utc(
        payload["released_at_utc"],
        name="released_at_utc",
    )
    if not (
        _parse_utc(
            payload["registered_at_utc"],
            name="registered_at_utc",
        )
        < released
        <= _parse_utc(
            payload["expires_at_utc"],
            name="expires_at_utc",
        )
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release ordering is invalid"
        )
    _key_id(
        payload["validation_custodian_key_id"],
        name="validation custodian key ID",
    )
    booleans = {
        "validation_file_matches_preregistered_commitment": True,
        "validation_labels_released_after_registration": True,
        "candidate_manifest_unchanged_after_registration": True,
        "posebusters_test_score_partition_present": False,
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
        "revoked": False,
        "superseded": False,
    }
    if (
        payload["schema_id"]
        != PUBLIC_POSE_RANKING_VALIDATION_RELEASE_SCHEMA_ID
        or payload["selection_policy_sha256"]
        != PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256
        or payload["custody_policy_sha256"]
        != PUBLIC_POSE_RANKING_CUSTODY_POLICY_SHA256
        or payload["signature_algorithm"]
        != PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        or payload["scientific_blockers"]
        != list(
            PUBLIC_POSE_RANKING_CUSTODY_ADMISSION_SCIENTIFIC_BLOCKERS
        )
        or any(payload[name] is not expected for name, expected in booleans.items())
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release policy or claim boundary is invalid"
        )
    return json.loads(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )


def build_public_pose_ranking_validation_release_signing_request(
    signed_registration: object,
    *,
    training_view_receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    training_view_receipt_source_file_sha256: str,
    training_view_receipt_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    manifest: PublicPoseRankingFitValidationManifest,
    manifest_source_file_sha256: str,
    manifest_source_file_size_bytes: int,
    trusted_registrar_keys: Mapping[
        str, PublicPoseRankingCustodyTrustAnchor
    ],
    revoked_registrar_key_ids: Sequence[str],
    revoked_registration_receipt_sha256s: Sequence[str],
    superseded_registration_receipt_sha256s: Sequence[str],
    custodian_identity_sha256: str,
    custodian_key_id: str,
    released_at_utc: str,
    release_nonce_sha256: str,
) -> dict[str, object]:
    """Verify registration, then build secret-free custodian signing input."""

    registration = verify_signed_public_pose_ranking_preregistration(
        signed_registration,
        training_view_receipt=training_view_receipt,
        training_view_receipt_source_file_sha256=(
            training_view_receipt_source_file_sha256
        ),
        training_view_receipt_source_file_size_bytes=(
            training_view_receipt_source_file_size_bytes
        ),
        validation_partition=validation_partition,
        manifest=manifest,
        manifest_source_file_sha256=manifest_source_file_sha256,
        manifest_source_file_size_bytes=manifest_source_file_size_bytes,
        trusted_registrar_keys=trusted_registrar_keys,
        checked_at_utc=released_at_utc,
        revoked_registrar_key_ids=revoked_registrar_key_ids,
        revoked_registration_receipt_sha256s=(
            revoked_registration_receipt_sha256s
        ),
        superseded_registration_receipt_sha256s=(
            superseded_registration_receipt_sha256s
        ),
    )
    bound = _validate_bound_inputs(
        training_view_receipt=training_view_receipt,
        training_view_receipt_source_file_sha256=(
            training_view_receipt_source_file_sha256
        ),
        training_view_receipt_source_file_size_bytes=(
            training_view_receipt_source_file_size_bytes
        ),
        validation_partition=validation_partition,
        manifest=manifest,
        manifest_source_file_sha256=manifest_source_file_sha256,
        manifest_source_file_size_bytes=manifest_source_file_size_bytes,
    )
    payload = _release_payload(
        registration=registration,
        bound_inputs=bound,
        custodian_identity_sha256=custodian_identity_sha256,
        custodian_key_id=custodian_key_id,
        released_at_utc=released_at_utc,
        release_nonce_sha256=release_nonce_sha256,
    )
    projection = {
        "schema_id": (
            PUBLIC_POSE_RANKING_VALIDATION_RELEASE_REQUEST_SCHEMA_ID
        ),
        "signature_algorithm": (
            PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        ),
        "validation_custodian_identity_sha256": (
            payload["validation_custodian_identity_sha256"]
        ),
        "validation_custodian_key_id": (
            payload["validation_custodian_key_id"]
        ),
        "release_payload": payload,
        "signing_bytes_sha256": hashlib.sha256(
            _canonical_bytes(payload)
        ).hexdigest(),
    }
    return {
        **projection,
        "request_sha256": _canonical_sha256(projection),
    }


def require_public_pose_ranking_validation_release_signing_request(
    value: object,
) -> dict[str, object]:
    request = _mapping(value, name="validation release signing request")
    _reject_private_signing_material(request)
    _exact_keys(
        request,
        {
            "schema_id",
            "signature_algorithm",
            "validation_custodian_identity_sha256",
            "validation_custodian_key_id",
            "release_payload",
            "signing_bytes_sha256",
            "request_sha256",
        },
        name="validation release signing request",
    )
    digest = _digest(
        request["request_sha256"],
        name="validation release request",
    )
    projection = {
        key: item
        for key, item in request.items()
        if key != "request_sha256"
    }
    payload = _require_release_payload(request["release_payload"])
    if (
        digest != _canonical_sha256(projection)
        or request["schema_id"]
        != PUBLIC_POSE_RANKING_VALIDATION_RELEASE_REQUEST_SCHEMA_ID
        or request["signature_algorithm"]
        != PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
        or request["validation_custodian_identity_sha256"]
        != payload["validation_custodian_identity_sha256"]
        or request["validation_custodian_key_id"]
        != payload["validation_custodian_key_id"]
        or _digest(
            request["signing_bytes_sha256"],
            name="validation release signing bytes",
        )
        != hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release signing request is cross-wired"
        )
    return {
        **projection,
        "release_payload": payload,
        "request_sha256": digest,
    }


def public_pose_ranking_validation_release_signing_bytes(
    value: object,
) -> bytes:
    request = require_public_pose_ranking_validation_release_signing_request(
        value
    )
    return _canonical_bytes(request["release_payload"])


def attach_public_pose_ranking_validation_release_signature(
    request_value: object,
    *,
    signature_hex: str,
    verification_key: bytes | str,
) -> dict[str, object]:
    """Verify and attach a detached validation-custodian signature."""

    request = require_public_pose_ranking_validation_release_signing_request(
        request_value
    )
    public_key = _key_bytes(
        verification_key,
        name="validation custodian verification key",
    )
    signature = _signature_hex(
        signature_hex,
        name="validation release signature",
    )
    try:
        verified = verify_ed25519(
            _canonical_bytes(request["release_payload"]),
            signature,
            public_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release signature verifier is unavailable"
        ) from exc
    if not verified:
        raise PublicPoseRankingFitValidationCustodyError(
            "detached validation release signature verification failed"
        )
    return {
        **request["release_payload"],
        "signature": {
            "algorithm": (
                PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM
            ),
            "key_id": request["validation_custodian_key_id"],
            "value": signature,
        },
    }


def verify_signed_public_pose_ranking_validation_release(
    signed_release_value: object,
    *,
    signed_registration_value: object,
    training_view_receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    training_view_receipt_source_file_sha256: str,
    training_view_receipt_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    manifest: PublicPoseRankingFitValidationManifest,
    manifest_source_file_sha256: str,
    manifest_source_file_size_bytes: int,
    trusted_registrar_keys: Mapping[
        str, PublicPoseRankingCustodyTrustAnchor
    ],
    trusted_custodian_keys: Mapping[
        str, PublicPoseRankingCustodyTrustAnchor
    ],
    checked_at_utc: str,
    revoked_registrar_key_ids: Sequence[str],
    revoked_registration_receipt_sha256s: Sequence[str],
    superseded_registration_receipt_sha256s: Sequence[str],
    revoked_custodian_key_ids: Sequence[str],
    revoked_release_receipt_sha256s: Sequence[str],
    superseded_release_receipt_sha256s: Sequence[str],
) -> dict[str, object]:
    """Verify the complete registration-before-release role chain."""

    payload, signature = _signed_payload(
        signed_release_value,
        receipt_field="release_receipt_sha256",
        payload_require=_require_release_payload,
        name="signed validation release",
    )
    registration = verify_signed_public_pose_ranking_preregistration(
        signed_registration_value,
        training_view_receipt=training_view_receipt,
        training_view_receipt_source_file_sha256=(
            training_view_receipt_source_file_sha256
        ),
        training_view_receipt_source_file_size_bytes=(
            training_view_receipt_source_file_size_bytes
        ),
        validation_partition=validation_partition,
        manifest=manifest,
        manifest_source_file_sha256=manifest_source_file_sha256,
        manifest_source_file_size_bytes=manifest_source_file_size_bytes,
        trusted_registrar_keys=trusted_registrar_keys,
        checked_at_utc=str(payload["released_at_utc"]),
        revoked_registrar_key_ids=revoked_registrar_key_ids,
        revoked_registration_receipt_sha256s=(
            revoked_registration_receipt_sha256s
        ),
        superseded_registration_receipt_sha256s=(
            superseded_registration_receipt_sha256s
        ),
    )
    checked = _parse_utc(checked_at_utc, name="checked_at_utc")
    released = _parse_utc(
        payload["released_at_utc"],
        name="released_at_utc",
    )
    expires = _parse_utc(
        payload["expires_at_utc"],
        name="expires_at_utc",
    )
    if not released <= checked <= expires:
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release is not currently valid"
        )
    key_id = _key_id(
        signature["key_id"],
        name="validation custodian signature key ID",
    )
    if key_id != payload["validation_custodian_key_id"]:
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release signature key is cross-wired"
        )
    anchor = trusted_custodian_keys.get(key_id)
    if not isinstance(anchor, PublicPoseRankingCustodyTrustAnchor):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation custodian key is not trusted"
        )
    if (
        anchor.identity_sha256
        != payload["validation_custodian_identity_sha256"]
        or anchor.identity_sha256
        == registration["registrar_identity_sha256"]
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation custodian identity is cross-wired or aliased"
        )
    _state_allows(
        key_id=key_id,
        receipt_sha256=str(payload["release_receipt_sha256"]),
        revoked_key_ids=revoked_custodian_key_ids,
        revoked_receipt_sha256s=revoked_release_receipt_sha256s,
        superseded_receipt_sha256s=superseded_release_receipt_sha256s,
        role="validation custodian",
    )
    try:
        verified = verify_ed25519(
            _canonical_bytes(payload),
            signature["value"],
            anchor.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release signature verifier is unavailable"
        ) from exc
    if not verified:
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release signature verification failed"
        )
    bound = _validate_bound_inputs(
        training_view_receipt=training_view_receipt,
        training_view_receipt_source_file_sha256=(
            training_view_receipt_source_file_sha256
        ),
        training_view_receipt_source_file_size_bytes=(
            training_view_receipt_source_file_size_bytes
        ),
        validation_partition=validation_partition,
        manifest=manifest,
        manifest_source_file_sha256=manifest_source_file_sha256,
        manifest_source_file_size_bytes=manifest_source_file_size_bytes,
    )
    expected = _release_payload(
        registration=registration,
        bound_inputs=bound,
        custodian_identity_sha256=anchor.identity_sha256,
        custodian_key_id=key_id,
        released_at_utc=str(payload["released_at_utc"]),
        release_nonce_sha256=str(payload["release_nonce_sha256"]),
    )
    if payload != expected:
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release differs from exact reconstruction"
        )
    return payload


def materialize_public_pose_ranking_fit_validation_custody_admission(
    *,
    signed_registration: object,
    signed_release: object,
    training_view_receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    training_view_receipt_source_file_sha256: str,
    training_view_receipt_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    manifest: PublicPoseRankingFitValidationManifest,
    manifest_source_file_sha256: str,
    manifest_source_file_size_bytes: int,
    trusted_registrar_keys: Mapping[
        str, PublicPoseRankingCustodyTrustAnchor
    ],
    trusted_custodian_keys: Mapping[
        str, PublicPoseRankingCustodyTrustAnchor
    ],
    checked_at_utc: str,
    revoked_registrar_key_ids: Sequence[str],
    revoked_registration_receipt_sha256s: Sequence[str],
    superseded_registration_receipt_sha256s: Sequence[str],
    revoked_custodian_key_ids: Sequence[str],
    revoked_release_receipt_sha256s: Sequence[str],
    superseded_release_receipt_sha256s: Sequence[str],
) -> dict[str, object]:
    """Derive execution admission from two current, exact, trusted signatures."""

    registration = verify_signed_public_pose_ranking_preregistration(
        signed_registration,
        training_view_receipt=training_view_receipt,
        training_view_receipt_source_file_sha256=(
            training_view_receipt_source_file_sha256
        ),
        training_view_receipt_source_file_size_bytes=(
            training_view_receipt_source_file_size_bytes
        ),
        validation_partition=validation_partition,
        manifest=manifest,
        manifest_source_file_sha256=manifest_source_file_sha256,
        manifest_source_file_size_bytes=manifest_source_file_size_bytes,
        trusted_registrar_keys=trusted_registrar_keys,
        checked_at_utc=checked_at_utc,
        revoked_registrar_key_ids=revoked_registrar_key_ids,
        revoked_registration_receipt_sha256s=(
            revoked_registration_receipt_sha256s
        ),
        superseded_registration_receipt_sha256s=(
            superseded_registration_receipt_sha256s
        ),
    )
    release = verify_signed_public_pose_ranking_validation_release(
        signed_release,
        signed_registration_value=signed_registration,
        training_view_receipt=training_view_receipt,
        training_view_receipt_source_file_sha256=(
            training_view_receipt_source_file_sha256
        ),
        training_view_receipt_source_file_size_bytes=(
            training_view_receipt_source_file_size_bytes
        ),
        validation_partition=validation_partition,
        manifest=manifest,
        manifest_source_file_sha256=manifest_source_file_sha256,
        manifest_source_file_size_bytes=manifest_source_file_size_bytes,
        trusted_registrar_keys=trusted_registrar_keys,
        trusted_custodian_keys=trusted_custodian_keys,
        checked_at_utc=checked_at_utc,
        revoked_registrar_key_ids=revoked_registrar_key_ids,
        revoked_registration_receipt_sha256s=(
            revoked_registration_receipt_sha256s
        ),
        superseded_registration_receipt_sha256s=(
            superseded_registration_receipt_sha256s
        ),
        revoked_custodian_key_ids=revoked_custodian_key_ids,
        revoked_release_receipt_sha256s=(
            revoked_release_receipt_sha256s
        ),
        superseded_release_receipt_sha256s=(
            superseded_release_receipt_sha256s
        ),
    )
    _, registration_signature = _signed_payload(
        signed_registration,
        receipt_field="registration_receipt_sha256",
        payload_require=_require_registration_payload,
        name="signed preregistration",
    )
    _, release_signature = _signed_payload(
        signed_release,
        receipt_field="release_receipt_sha256",
        payload_require=_require_release_payload,
        name="signed validation release",
    )
    signed_registration_json = json.loads(
        json.dumps(
            {**registration, "signature": registration_signature},
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    signed_release_json = json.loads(
        json.dumps(
            {**release, "signature": release_signature},
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    checked = _utc(checked_at_utc, name="checked_at_utc")
    projection: dict[str, object] = {
        "schema_id": (
            PUBLIC_POSE_RANKING_FIT_VALIDATION_CUSTODY_ADMISSION_SCHEMA_ID
        ),
        "signed_registration": signed_registration_json,
        "registration_receipt_sha256": (
            registration["registration_receipt_sha256"]
        ),
        "signed_release": signed_release_json,
        "release_receipt_sha256": release["release_receipt_sha256"],
        **{
            name: registration[name]
            for name in _BOUND_INPUT_FIELDS
        },
        "selection_policy_sha256": (
            registration["selection_policy_sha256"]
        ),
        "fit_validation_source_identity_sha256": (
            registration["fit_validation_source_identity_sha256"]
        ),
        "custody_source_identity_sha256": (
            registration["custody_source_identity_sha256"]
        ),
        "registrar_identity_sha256": (
            registration["registrar_identity_sha256"]
        ),
        "registrar_key_id": registration["registrar_key_id"],
        "training_operator_identity_sha256": (
            registration["training_operator_identity_sha256"]
        ),
        "validation_custodian_identity_sha256": (
            registration["validation_custodian_identity_sha256"]
        ),
        "validation_custodian_key_id": (
            registration["validation_custodian_key_id"]
        ),
        "evaluation_operator_identity_sha256": (
            registration["evaluation_operator_identity_sha256"]
        ),
        "registered_at_utc": registration["registered_at_utc"],
        "released_at_utc": release["released_at_utc"],
        "expires_at_utc": registration["expires_at_utc"],
        "checked_at_utc": checked,
        "registration_signature_verified": True,
        "release_signature_verified": True,
        "role_separation_verified": True,
        "registration_precedes_release": True,
        "candidate_manifest_unchanged": True,
        "validation_file_matches_commitment": True,
        "posebusters_test_score_partition_present": False,
        "admitted_for_fit_validation_execution": True,
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
        "scientific_blockers": list(
            PUBLIC_POSE_RANKING_CUSTODY_ADMISSION_SCIENTIFIC_BLOCKERS
        ),
    }
    return {
        **projection,
        "custody_admission_sha256": _canonical_sha256(projection),
    }


_ADMISSION_FIELDS = {
    "schema_id",
    "signed_registration",
    "registration_receipt_sha256",
    "signed_release",
    "release_receipt_sha256",
    *_BOUND_INPUT_FIELDS,
    "selection_policy_sha256",
    "fit_validation_source_identity_sha256",
    "custody_source_identity_sha256",
    "registrar_identity_sha256",
    "registrar_key_id",
    "training_operator_identity_sha256",
    "validation_custodian_identity_sha256",
    "validation_custodian_key_id",
    "evaluation_operator_identity_sha256",
    "registered_at_utc",
    "released_at_utc",
    "expires_at_utc",
    "checked_at_utc",
    "registration_signature_verified",
    "release_signature_verified",
    "role_separation_verified",
    "registration_precedes_release",
    "candidate_manifest_unchanged",
    "validation_file_matches_commitment",
    "posebusters_test_score_partition_present",
    "admitted_for_fit_validation_execution",
    "scientifically_validated",
    "production_eligible",
    "claim_safe",
    "scientific_blockers",
    "custody_admission_sha256",
}


def validate_public_pose_ranking_fit_validation_custody_admission_structure(
    value: object,
) -> dict[str, object]:
    """Validate digest, embedded signed artifacts, and claim boundary."""

    admission = _mapping(value, name="custody admission")
    _exact_keys(admission, _ADMISSION_FIELDS, name="custody admission")
    digest = _digest(
        admission["custody_admission_sha256"],
        name="custody admission",
    )
    projection = {
        key: item
        for key, item in admission.items()
        if key != "custody_admission_sha256"
    }
    if digest != _canonical_sha256(projection):
        raise PublicPoseRankingFitValidationCustodyError(
            "custody admission digest is invalid"
        )
    registration, _ = _signed_payload(
        admission["signed_registration"],
        receipt_field="registration_receipt_sha256",
        payload_require=_require_registration_payload,
        name="embedded signed preregistration",
    )
    release, _ = _signed_payload(
        admission["signed_release"],
        receipt_field="release_receipt_sha256",
        payload_require=_require_release_payload,
        name="embedded signed validation release",
    )
    booleans = {
        "registration_signature_verified": True,
        "release_signature_verified": True,
        "role_separation_verified": True,
        "registration_precedes_release": True,
        "candidate_manifest_unchanged": True,
        "validation_file_matches_commitment": True,
        "posebusters_test_score_partition_present": False,
        "admitted_for_fit_validation_execution": True,
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
    }
    if (
        admission["schema_id"]
        != PUBLIC_POSE_RANKING_FIT_VALIDATION_CUSTODY_ADMISSION_SCHEMA_ID
        or admission["registration_receipt_sha256"]
        != registration["registration_receipt_sha256"]
        or admission["release_receipt_sha256"]
        != release["release_receipt_sha256"]
        or release["registration_receipt_sha256"]
        != registration["registration_receipt_sha256"]
        or any(
            admission[name] != registration[name]
            for name in _BOUND_INPUT_FIELDS
        )
        or any(
            release[name] != registration[name]
            for name in _RELEASE_BOUND_FIELDS
        )
        or admission["selection_policy_sha256"]
        != PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256
        or release["selection_policy_sha256"]
        != registration["selection_policy_sha256"]
        or release["fit_validation_source_identity_sha256"]
        != registration["fit_validation_source_identity_sha256"]
        or release["custody_source_identity_sha256"]
        != registration["custody_source_identity_sha256"]
        or admission["fit_validation_source_identity_sha256"]
        != registration["fit_validation_source_identity_sha256"]
        or admission["custody_source_identity_sha256"]
        != registration["custody_source_identity_sha256"]
        or any(
            admission[name] != registration[name]
            or release[name] != registration[name]
            for name in (
                "registrar_identity_sha256",
                "training_operator_identity_sha256",
                "validation_custodian_identity_sha256",
                "evaluation_operator_identity_sha256",
                "registered_at_utc",
                "expires_at_utc",
            )
        )
        or admission["registrar_key_id"]
        != registration["registrar_key_id"]
        or admission["validation_custodian_key_id"]
        != registration["validation_custodian_key_id"]
        or release["validation_custodian_key_id"]
        != registration["validation_custodian_key_id"]
        or admission["released_at_utc"] != release["released_at_utc"]
        or not (
            _parse_utc(
                registration["registered_at_utc"],
                name="registered_at_utc",
            )
            < _parse_utc(
                release["released_at_utc"],
                name="released_at_utc",
            )
            <= _parse_utc(
                registration["expires_at_utc"],
                name="expires_at_utc",
            )
        )
        or not (
            _parse_utc(
                release["released_at_utc"],
                name="released_at_utc",
            )
            <= _parse_utc(
                admission["checked_at_utc"],
                name="checked_at_utc",
            )
            <= _parse_utc(
                registration["expires_at_utc"],
                name="expires_at_utc",
            )
        )
        or admission["scientific_blockers"]
        != list(
            PUBLIC_POSE_RANKING_CUSTODY_ADMISSION_SCIENTIFIC_BLOCKERS
        )
        or any(
            admission[name] is not expected
            for name, expected in booleans.items()
        )
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "custody admission evidence or claim boundary is inconsistent"
        )
    return json.loads(
        json.dumps(
            admission,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )


def require_public_pose_ranking_fit_validation_custody_admission(
    value: object,
    **materialization_arguments: Any,
) -> dict[str, object]:
    observed = (
        validate_public_pose_ranking_fit_validation_custody_admission_structure(
            value
        )
    )
    expected = (
        materialize_public_pose_ranking_fit_validation_custody_admission(
            **materialization_arguments
        )
    )
    if observed != expected:
        raise PublicPoseRankingFitValidationCustodyError(
            "custody admission differs from exact reconstruction"
        )
    return observed


def _write_private_artifact(
    path: str | os.PathLike[str],
    value: Mapping[str, object],
    *,
    maximum_bytes: int,
) -> Path:
    payload = _canonical_bytes(value) + b"\n"
    if not payload or len(payload) > maximum_bytes:
        raise PublicPoseRankingFitValidationCustodyError(
            "custody artifact exceeds its byte bound"
        )
    destination = Path(path)
    if not destination.parent.is_dir():
        raise PublicPoseRankingFitValidationCustodyError(
            "custody artifact parent must already exist"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            "custody artifact output already exists"
        ) from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise PublicPoseRankingFitValidationCustodyError(
                    "custody artifact write made no progress"
                )
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return destination


def write_public_pose_ranking_custody_artifact(
    path: str | os.PathLike[str],
    value: Mapping[str, object],
) -> Path:
    """Write a validated request, signed receipt, or admission privately."""

    artifact = _mapping(value, name="custody artifact")
    schema = artifact.get("schema_id")
    if schema == PUBLIC_POSE_RANKING_PREREGISTRATION_REQUEST_SCHEMA_ID:
        verified = require_public_pose_ranking_preregistration_signing_request(
            artifact
        )
        maximum = PUBLIC_POSE_RANKING_CUSTODY_MAX_REQUEST_BYTES
    elif schema == PUBLIC_POSE_RANKING_VALIDATION_RELEASE_REQUEST_SCHEMA_ID:
        verified = (
            require_public_pose_ranking_validation_release_signing_request(
                artifact
            )
        )
        maximum = PUBLIC_POSE_RANKING_CUSTODY_MAX_REQUEST_BYTES
    elif schema == PUBLIC_POSE_RANKING_PREREGISTRATION_SCHEMA_ID:
        payload, signature = _signed_payload(
            artifact,
            receipt_field="registration_receipt_sha256",
            payload_require=_require_registration_payload,
            name="signed preregistration",
        )
        verified = {**payload, "signature": signature}
        maximum = PUBLIC_POSE_RANKING_CUSTODY_MAX_SIGNED_RECEIPT_BYTES
    elif schema == PUBLIC_POSE_RANKING_VALIDATION_RELEASE_SCHEMA_ID:
        payload, signature = _signed_payload(
            artifact,
            receipt_field="release_receipt_sha256",
            payload_require=_require_release_payload,
            name="signed validation release",
        )
        verified = {**payload, "signature": signature}
        maximum = PUBLIC_POSE_RANKING_CUSTODY_MAX_SIGNED_RECEIPT_BYTES
    elif (
        schema
        == PUBLIC_POSE_RANKING_FIT_VALIDATION_CUSTODY_ADMISSION_SCHEMA_ID
    ):
        verified = (
            validate_public_pose_ranking_fit_validation_custody_admission_structure(
                artifact
            )
        )
        maximum = PUBLIC_POSE_RANKING_CUSTODY_MAX_ADMISSION_BYTES
    else:
        raise PublicPoseRankingFitValidationCustodyError(
            "custody artifact schema is unsupported"
        )
    return _write_private_artifact(
        path,
        verified,
        maximum_bytes=maximum,
    )


def _read_private_artifact(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
    expected_file_sha256: str,
    name: str,
) -> dict[str, object]:
    try:
        data, file_sha256 = _read_regular_file(
            path,
            name=name,
            maximum_bytes=maximum_bytes,
        )
    except PublicPoseRankingCalibrationPartitionIntakeError as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} could not be read safely"
        ) from exc
    if file_sha256 != _digest(
        expected_file_sha256,
        name=f"expected {name} file SHA-256",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} file SHA-256 mismatch"
        )
    metadata = os.stat(path, follow_symlinks=False)
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} mode must be 0600"
        )
    try:
        decoded = _decode_json_object(data, name=name)
    except PublicPoseRankingCalibrationPartitionIntakeError as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} is not valid JSON"
        ) from exc
    if data != _canonical_bytes(decoded) + b"\n":
        raise PublicPoseRankingFitValidationCustodyError(
            f"{name} must use canonical JSON plus one newline"
        )
    return decoded


def read_public_pose_ranking_preregistration_signing_request(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_request_sha256: str,
) -> dict[str, object]:
    decoded = _read_private_artifact(
        path,
        maximum_bytes=PUBLIC_POSE_RANKING_CUSTODY_MAX_REQUEST_BYTES,
        expected_file_sha256=expected_file_sha256,
        name="preregistration signing request",
    )
    request = require_public_pose_ranking_preregistration_signing_request(
        decoded
    )
    if request["request_sha256"] != _digest(
        expected_request_sha256,
        name="expected preregistration request SHA-256",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration request SHA-256 mismatch"
        )
    return request


def read_signed_public_pose_ranking_preregistration(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_registration_receipt_sha256: str,
) -> dict[str, object]:
    decoded = _read_private_artifact(
        path,
        maximum_bytes=PUBLIC_POSE_RANKING_CUSTODY_MAX_SIGNED_RECEIPT_BYTES,
        expected_file_sha256=expected_file_sha256,
        name="signed preregistration",
    )
    payload, _ = _signed_payload(
        decoded,
        receipt_field="registration_receipt_sha256",
        payload_require=_require_registration_payload,
        name="signed preregistration",
    )
    if payload["registration_receipt_sha256"] != _digest(
        expected_registration_receipt_sha256,
        name="expected preregistration receipt SHA-256",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "preregistration receipt SHA-256 mismatch"
        )
    return decoded


def read_public_pose_ranking_validation_release_signing_request(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_request_sha256: str,
) -> dict[str, object]:
    decoded = _read_private_artifact(
        path,
        maximum_bytes=PUBLIC_POSE_RANKING_CUSTODY_MAX_REQUEST_BYTES,
        expected_file_sha256=expected_file_sha256,
        name="validation release signing request",
    )
    request = (
        require_public_pose_ranking_validation_release_signing_request(
            decoded
        )
    )
    if request["request_sha256"] != _digest(
        expected_request_sha256,
        name="expected validation release request SHA-256",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release request SHA-256 mismatch"
        )
    return request


def read_signed_public_pose_ranking_validation_release(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_release_receipt_sha256: str,
) -> dict[str, object]:
    decoded = _read_private_artifact(
        path,
        maximum_bytes=PUBLIC_POSE_RANKING_CUSTODY_MAX_SIGNED_RECEIPT_BYTES,
        expected_file_sha256=expected_file_sha256,
        name="signed validation release",
    )
    payload, _ = _signed_payload(
        decoded,
        receipt_field="release_receipt_sha256",
        payload_require=_require_release_payload,
        name="signed validation release",
    )
    if payload["release_receipt_sha256"] != _digest(
        expected_release_receipt_sha256,
        name="expected validation release receipt SHA-256",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "validation release receipt SHA-256 mismatch"
        )
    return decoded


def read_public_pose_ranking_custody_admission(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_admission_sha256: str,
) -> dict[str, object]:
    decoded = _read_private_artifact(
        path,
        maximum_bytes=PUBLIC_POSE_RANKING_CUSTODY_MAX_ADMISSION_BYTES,
        expected_file_sha256=expected_file_sha256,
        name="custody admission",
    )
    admission = (
        validate_public_pose_ranking_fit_validation_custody_admission_structure(
            decoded
        )
    )
    if admission["custody_admission_sha256"] != _digest(
        expected_admission_sha256,
        name="expected custody admission SHA-256",
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "custody admission SHA-256 mismatch"
        )
    return admission


_CUSTODY_STATE_FIELDS = {
    "revoked_registrar_key_ids",
    "revoked_registration_receipt_sha256s",
    "superseded_registration_receipt_sha256s",
    "revoked_custodian_key_ids",
    "revoked_release_receipt_sha256s",
    "superseded_release_receipt_sha256s",
}


def parse_public_pose_ranking_custody_state_json(
    value: str,
) -> dict[str, tuple[str, ...]]:
    """Parse an explicitly supplied current revocation/supersession snapshot."""

    if not isinstance(value, str) or len(value) > 1024 * 1024:
        raise PublicPoseRankingFitValidationCustodyError(
            "custody state JSON is missing or exceeds its byte bound"
        )
    try:
        decoded = json.loads(value)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise PublicPoseRankingFitValidationCustodyError(
            "custody state JSON is invalid"
        ) from exc
    state = _mapping(decoded, name="custody state")
    _exact_keys(state, _CUSTODY_STATE_FIELDS, name="custody state")
    normalized: dict[str, tuple[str, ...]] = {}
    for name in (
        "revoked_registrar_key_ids",
        "revoked_custodian_key_ids",
    ):
        normalized[name] = _normalized_key_state(
            _sequence(state[name], name=name),
            name=name,
        )
    for name in (
        "revoked_registration_receipt_sha256s",
        "superseded_registration_receipt_sha256s",
        "revoked_release_receipt_sha256s",
        "superseded_release_receipt_sha256s",
    ):
        normalized[name] = _normalized_digest_state(
            _sequence(state[name], name=name),
            name=name,
        )
    return normalized


def public_pose_ranking_custody_verification_context(
    *,
    registrar_key_id: str,
    registrar_identity_sha256: str,
    registrar_public_key_hex: str,
    custodian_key_id: str,
    custodian_identity_sha256: str,
    custodian_public_key_hex: str,
    custody_state_json: str,
) -> dict[str, object]:
    """Build public-key-only trust maps plus explicit current state."""

    registrar_id = _key_id(registrar_key_id, name="registrar key ID")
    custodian_id = _key_id(custodian_key_id, name="custodian key ID")
    registrar_identity = _digest(
        registrar_identity_sha256,
        name="registrar identity",
    )
    custodian_identity = _digest(
        custodian_identity_sha256,
        name="validation custodian identity",
    )
    registrar_key = _key_bytes(
        registrar_public_key_hex,
        name="registrar public key",
    )
    custodian_key = _key_bytes(
        custodian_public_key_hex,
        name="validation custodian public key",
    )
    if (
        registrar_id == custodian_id
        or registrar_identity == custodian_identity
        or registrar_key == custodian_key
    ):
        raise PublicPoseRankingFitValidationCustodyError(
            "registrar and validation custodian trust anchors must be distinct"
        )
    return {
        "trusted_registrar_keys": {
            registrar_id: PublicPoseRankingCustodyTrustAnchor(
                identity_sha256=registrar_identity,
                verification_key=registrar_key,
            )
        },
        "trusted_custodian_keys": {
            custodian_id: PublicPoseRankingCustodyTrustAnchor(
                identity_sha256=custodian_identity,
                verification_key=custodian_key,
            )
        },
        **parse_public_pose_ranking_custody_state_json(
            custody_state_json
        ),
    }


def _add_bound_file_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--training-view-receipt", required=True)
    parser.add_argument(
        "--expected-training-view-receipt-file-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-training-view-receipt-sha256",
        required=True,
    )
    parser.add_argument("--ancestry-arguments", required=True)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument(
        "--expected-candidate-manifest-file-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-candidate-manifest-sha256",
        required=True,
    )


def _add_verification_context_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("--registrar-key-id", required=True)
    parser.add_argument("--registrar-identity-sha256", required=True)
    parser.add_argument("--registrar-public-key-hex", required=True)
    parser.add_argument("--custodian-key-id", required=True)
    parser.add_argument("--custodian-identity-sha256", required=True)
    parser.add_argument("--custodian-public-key-hex", required=True)
    parser.add_argument(
        "--custody-state-json",
        required=True,
        help=(
            "JSON object containing all six current revoked/superseded "
            "key and receipt arrays; use explicit empty arrays when none"
        ),
    )


def _add_signed_registration_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("--signed-registration", required=True)
    parser.add_argument(
        "--expected-signed-registration-file-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-registration-receipt-sha256",
        required=True,
    )


def _add_signed_release_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("--signed-release", required=True)
    parser.add_argument(
        "--expected-signed-release-file-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-release-receipt-sha256",
        required=True,
    )


def _bound_inputs_from_cli(args: argparse.Namespace) -> dict[str, object]:
    return load_public_pose_ranking_fit_validation_bound_inputs_from_files(
        training_view_receipt_path=args.training_view_receipt,
        expected_training_view_receipt_file_sha256=(
            args.expected_training_view_receipt_file_sha256
        ),
        expected_training_view_receipt_sha256=(
            args.expected_training_view_receipt_sha256
        ),
        ancestry_arguments_path=args.ancestry_arguments,
        candidate_manifest_path=args.candidate_manifest,
        expected_candidate_manifest_file_sha256=(
            args.expected_candidate_manifest_file_sha256
        ),
        expected_candidate_manifest_sha256=(
            args.expected_candidate_manifest_sha256
        ),
    )


def _verification_context_from_cli(
    args: argparse.Namespace,
) -> dict[str, object]:
    return public_pose_ranking_custody_verification_context(
        registrar_key_id=args.registrar_key_id,
        registrar_identity_sha256=args.registrar_identity_sha256,
        registrar_public_key_hex=args.registrar_public_key_hex,
        custodian_key_id=args.custodian_key_id,
        custodian_identity_sha256=args.custodian_identity_sha256,
        custodian_public_key_hex=args.custodian_public_key_hex,
        custody_state_json=args.custody_state_json,
    )


def _signed_registration_from_cli(
    args: argparse.Namespace,
) -> dict[str, object]:
    return read_signed_public_pose_ranking_preregistration(
        args.signed_registration,
        expected_file_sha256=(
            args.expected_signed_registration_file_sha256
        ),
        expected_registration_receipt_sha256=(
            args.expected_registration_receipt_sha256
        ),
    )


def _signed_release_from_cli(
    args: argparse.Namespace,
) -> dict[str, object]:
    return read_signed_public_pose_ranking_validation_release(
        args.signed_release,
        expected_file_sha256=args.expected_signed_release_file_sha256,
        expected_release_receipt_sha256=(
            args.expected_release_receipt_sha256
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-public-ranking-custody",
        description=(
            "Create and verify public-key-only, label-blind pose-ranking "
            "preregistration, later validation release, and execution "
            "admission artifacts."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build_registration = commands.add_parser(
        "build-registration-request"
    )
    _add_bound_file_arguments(build_registration)
    build_registration.add_argument(
        "--registrar-identity-sha256",
        required=True,
    )
    build_registration.add_argument("--registrar-key-id", required=True)
    build_registration.add_argument(
        "--training-operator-identity-sha256",
        required=True,
    )
    build_registration.add_argument(
        "--custodian-identity-sha256",
        required=True,
    )
    build_registration.add_argument("--custodian-key-id", required=True)
    build_registration.add_argument(
        "--evaluation-operator-identity-sha256",
        required=True,
    )
    build_registration.add_argument("--registered-at-utc", required=True)
    build_registration.add_argument("--expires-at-utc", required=True)
    build_registration.add_argument(
        "--registration-nonce-sha256",
        required=True,
    )
    build_registration.add_argument("--output", required=True)

    attach_registration = commands.add_parser("attach-registration")
    attach_registration.add_argument(
        "--registration-request",
        required=True,
    )
    attach_registration.add_argument(
        "--expected-registration-request-file-sha256",
        required=True,
    )
    attach_registration.add_argument(
        "--expected-registration-request-sha256",
        required=True,
    )
    attach_registration.add_argument("--signature-hex", required=True)
    attach_registration.add_argument(
        "--verification-public-key-hex",
        required=True,
    )
    attach_registration.add_argument("--output", required=True)

    verify_registration = commands.add_parser("verify-registration")
    _add_bound_file_arguments(verify_registration)
    _add_signed_registration_arguments(verify_registration)
    _add_verification_context_arguments(verify_registration)
    verify_registration.add_argument("--checked-at-utc", required=True)

    build_release = commands.add_parser("build-release-request")
    _add_bound_file_arguments(build_release)
    _add_signed_registration_arguments(build_release)
    _add_verification_context_arguments(build_release)
    build_release.add_argument("--released-at-utc", required=True)
    build_release.add_argument("--release-nonce-sha256", required=True)
    build_release.add_argument("--output", required=True)

    attach_release = commands.add_parser("attach-release")
    attach_release.add_argument("--release-request", required=True)
    attach_release.add_argument(
        "--expected-release-request-file-sha256",
        required=True,
    )
    attach_release.add_argument(
        "--expected-release-request-sha256",
        required=True,
    )
    attach_release.add_argument("--signature-hex", required=True)
    attach_release.add_argument(
        "--verification-public-key-hex",
        required=True,
    )
    attach_release.add_argument("--output", required=True)

    verify_release = commands.add_parser("verify-release")
    _add_bound_file_arguments(verify_release)
    _add_signed_registration_arguments(verify_release)
    _add_signed_release_arguments(verify_release)
    _add_verification_context_arguments(verify_release)
    verify_release.add_argument("--checked-at-utc", required=True)

    admit = commands.add_parser("admit")
    _add_bound_file_arguments(admit)
    _add_signed_registration_arguments(admit)
    _add_signed_release_arguments(admit)
    _add_verification_context_arguments(admit)
    admit.add_argument("--checked-at-utc", required=True)
    admit.add_argument("--output", required=True)

    verify_admission = commands.add_parser("verify-admission")
    _add_bound_file_arguments(verify_admission)
    _add_verification_context_arguments(verify_admission)
    verify_admission.add_argument("--custody-admission", required=True)
    verify_admission.add_argument(
        "--expected-custody-admission-file-sha256",
        required=True,
    )
    verify_admission.add_argument(
        "--expected-custody-admission-sha256",
        required=True,
    )
    verify_admission.add_argument("--checked-at-utc", required=True)
    return parser


def _artifact_summary(artifact: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_id": artifact["schema_id"],
        **{
            name: artifact[name]
            for name in (
                "request_sha256",
                "registration_receipt_sha256",
                "release_receipt_sha256",
                "custody_admission_sha256",
            )
            if name in artifact
        },
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = args.command
    artifact: dict[str, object]

    if command == "build-registration-request":
        bound = _bound_inputs_from_cli(args)
        artifact = (
            build_public_pose_ranking_preregistration_signing_request(
                **bound,
                registrar_identity_sha256=args.registrar_identity_sha256,
                registrar_key_id=args.registrar_key_id,
                training_operator_identity_sha256=(
                    args.training_operator_identity_sha256
                ),
                validation_custodian_identity_sha256=(
                    args.custodian_identity_sha256
                ),
                validation_custodian_key_id=args.custodian_key_id,
                evaluation_operator_identity_sha256=(
                    args.evaluation_operator_identity_sha256
                ),
                registered_at_utc=args.registered_at_utc,
                expires_at_utc=args.expires_at_utc,
                registration_nonce_sha256=(
                    args.registration_nonce_sha256
                ),
            )
        )
        write_public_pose_ranking_custody_artifact(args.output, artifact)
    elif command == "attach-registration":
        request = (
            read_public_pose_ranking_preregistration_signing_request(
                args.registration_request,
                expected_file_sha256=(
                    args.expected_registration_request_file_sha256
                ),
                expected_request_sha256=(
                    args.expected_registration_request_sha256
                ),
            )
        )
        artifact = attach_public_pose_ranking_preregistration_signature(
            request,
            signature_hex=args.signature_hex,
            verification_key=args.verification_public_key_hex,
        )
        write_public_pose_ranking_custody_artifact(args.output, artifact)
    elif command == "verify-registration":
        signed_registration = _signed_registration_from_cli(args)
        bound = _bound_inputs_from_cli(args)
        context = _verification_context_from_cli(args)
        artifact = verify_signed_public_pose_ranking_preregistration(
            signed_registration,
            **bound,
            trusted_registrar_keys=context["trusted_registrar_keys"],
            checked_at_utc=args.checked_at_utc,
            revoked_registrar_key_ids=context[
                "revoked_registrar_key_ids"
            ],
            revoked_registration_receipt_sha256s=context[
                "revoked_registration_receipt_sha256s"
            ],
            superseded_registration_receipt_sha256s=context[
                "superseded_registration_receipt_sha256s"
            ],
        )
    elif command == "build-release-request":
        signed_registration = _signed_registration_from_cli(args)
        bound = _bound_inputs_from_cli(args)
        context = _verification_context_from_cli(args)
        artifact = (
            build_public_pose_ranking_validation_release_signing_request(
                signed_registration,
                **bound,
                trusted_registrar_keys=context[
                    "trusted_registrar_keys"
                ],
                revoked_registrar_key_ids=context[
                    "revoked_registrar_key_ids"
                ],
                revoked_registration_receipt_sha256s=context[
                    "revoked_registration_receipt_sha256s"
                ],
                superseded_registration_receipt_sha256s=context[
                    "superseded_registration_receipt_sha256s"
                ],
                custodian_identity_sha256=args.custodian_identity_sha256,
                custodian_key_id=args.custodian_key_id,
                released_at_utc=args.released_at_utc,
                release_nonce_sha256=args.release_nonce_sha256,
            )
        )
        write_public_pose_ranking_custody_artifact(args.output, artifact)
    elif command == "attach-release":
        request = (
            read_public_pose_ranking_validation_release_signing_request(
                args.release_request,
                expected_file_sha256=(
                    args.expected_release_request_file_sha256
                ),
                expected_request_sha256=(
                    args.expected_release_request_sha256
                ),
            )
        )
        artifact = attach_public_pose_ranking_validation_release_signature(
            request,
            signature_hex=args.signature_hex,
            verification_key=args.verification_public_key_hex,
        )
        write_public_pose_ranking_custody_artifact(args.output, artifact)
    elif command == "verify-release":
        signed_registration = _signed_registration_from_cli(args)
        signed_release = _signed_release_from_cli(args)
        bound = _bound_inputs_from_cli(args)
        context = _verification_context_from_cli(args)
        artifact = verify_signed_public_pose_ranking_validation_release(
            signed_release,
            signed_registration_value=signed_registration,
            **bound,
            trusted_registrar_keys=context["trusted_registrar_keys"],
            trusted_custodian_keys=context["trusted_custodian_keys"],
            checked_at_utc=args.checked_at_utc,
            revoked_registrar_key_ids=context[
                "revoked_registrar_key_ids"
            ],
            revoked_registration_receipt_sha256s=context[
                "revoked_registration_receipt_sha256s"
            ],
            superseded_registration_receipt_sha256s=context[
                "superseded_registration_receipt_sha256s"
            ],
            revoked_custodian_key_ids=context[
                "revoked_custodian_key_ids"
            ],
            revoked_release_receipt_sha256s=context[
                "revoked_release_receipt_sha256s"
            ],
            superseded_release_receipt_sha256s=context[
                "superseded_release_receipt_sha256s"
            ],
        )
    elif command == "admit":
        signed_registration = _signed_registration_from_cli(args)
        signed_release = _signed_release_from_cli(args)
        bound = _bound_inputs_from_cli(args)
        context = _verification_context_from_cli(args)
        artifact = (
            materialize_public_pose_ranking_fit_validation_custody_admission(
                signed_registration=signed_registration,
                signed_release=signed_release,
                **bound,
                trusted_registrar_keys=context[
                    "trusted_registrar_keys"
                ],
                trusted_custodian_keys=context[
                    "trusted_custodian_keys"
                ],
                checked_at_utc=args.checked_at_utc,
                revoked_registrar_key_ids=context[
                    "revoked_registrar_key_ids"
                ],
                revoked_registration_receipt_sha256s=context[
                    "revoked_registration_receipt_sha256s"
                ],
                superseded_registration_receipt_sha256s=context[
                    "superseded_registration_receipt_sha256s"
                ],
                revoked_custodian_key_ids=context[
                    "revoked_custodian_key_ids"
                ],
                revoked_release_receipt_sha256s=context[
                    "revoked_release_receipt_sha256s"
                ],
                superseded_release_receipt_sha256s=context[
                    "superseded_release_receipt_sha256s"
                ],
            )
        )
        write_public_pose_ranking_custody_artifact(args.output, artifact)
    else:
        artifact = read_public_pose_ranking_custody_admission(
            args.custody_admission,
            expected_file_sha256=(
                args.expected_custody_admission_file_sha256
            ),
            expected_admission_sha256=(
                args.expected_custody_admission_sha256
            ),
        )
        bound = _bound_inputs_from_cli(args)
        context = _verification_context_from_cli(args)
        artifact = (
            require_public_pose_ranking_fit_validation_custody_admission(
                artifact,
                signed_registration=artifact["signed_registration"],
                signed_release=artifact["signed_release"],
                **bound,
                trusted_registrar_keys=context[
                    "trusted_registrar_keys"
                ],
                trusted_custodian_keys=context[
                    "trusted_custodian_keys"
                ],
                checked_at_utc=args.checked_at_utc,
                revoked_registrar_key_ids=context[
                    "revoked_registrar_key_ids"
                ],
                revoked_registration_receipt_sha256s=context[
                    "revoked_registration_receipt_sha256s"
                ],
                superseded_registration_receipt_sha256s=context[
                    "superseded_registration_receipt_sha256s"
                ],
                revoked_custodian_key_ids=context[
                    "revoked_custodian_key_ids"
                ],
                revoked_release_receipt_sha256s=context[
                    "revoked_release_receipt_sha256s"
                ],
                superseded_release_receipt_sha256s=context[
                    "superseded_release_receipt_sha256s"
                ],
            )
        )
    print(
        json.dumps(
            _artifact_summary(artifact),
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "PUBLIC_POSE_RANKING_CUSTODY_ADMISSION_SCIENTIFIC_BLOCKERS",
    "PUBLIC_POSE_RANKING_CUSTODY_MAX_ADMISSION_BYTES",
    "PUBLIC_POSE_RANKING_CUSTODY_MAX_REQUEST_BYTES",
    "PUBLIC_POSE_RANKING_CUSTODY_MAX_SIGNED_RECEIPT_BYTES",
    "PUBLIC_POSE_RANKING_CUSTODY_MAX_VALIDITY",
    "PUBLIC_POSE_RANKING_CUSTODY_POLICY",
    "PUBLIC_POSE_RANKING_CUSTODY_POLICY_SHA256",
    "PUBLIC_POSE_RANKING_CUSTODY_SIGNATURE_ALGORITHM",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_CUSTODY_ADMISSION_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_PREREGISTRATION_REQUEST_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_PREREGISTRATION_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_VALIDATION_RELEASE_REQUEST_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_VALIDATION_RELEASE_SCHEMA_ID",
    "PublicPoseRankingCustodyTrustAnchor",
    "PublicPoseRankingFitValidationCustodyError",
    "attach_public_pose_ranking_preregistration_signature",
    "attach_public_pose_ranking_validation_release_signature",
    "build_public_pose_ranking_preregistration_signing_request",
    "build_public_pose_ranking_validation_release_signing_request",
    "materialize_public_pose_ranking_fit_validation_custody_admission",
    "parse_public_pose_ranking_custody_state_json",
    "public_pose_ranking_custody_verification_context",
    "public_pose_ranking_preregistration_signing_bytes",
    "public_pose_ranking_validation_release_signing_bytes",
    "read_public_pose_ranking_custody_admission",
    "read_public_pose_ranking_preregistration_signing_request",
    "read_public_pose_ranking_validation_release_signing_request",
    "read_signed_public_pose_ranking_preregistration",
    "read_signed_public_pose_ranking_validation_release",
    "require_public_pose_ranking_fit_validation_custody_admission",
    "require_public_pose_ranking_preregistration_signing_request",
    "require_public_pose_ranking_validation_release_signing_request",
    "validate_public_pose_ranking_fit_validation_custody_admission_structure",
    "verify_signed_public_pose_ranking_preregistration",
    "verify_signed_public_pose_ranking_validation_release",
    "write_public_pose_ranking_custody_artifact",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
