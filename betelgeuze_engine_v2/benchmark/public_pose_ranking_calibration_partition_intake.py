"""Leakage-closed PDBbind-fit and CASF-validation partition intake.

This module admits exact, canonical ``PoseRankingCalibrationPartition`` files
only after the three-way PDBbind/CASF/PoseBusters corpus intake has passed.  It
recomputes public-manifest bindings and pose-level fit/validation leakage while
retaining failure and label denominators.

No scorer fitting, validation-based model selection, test-partition access,
benchmark execution, independent rerun, or product claim is performed here.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ..docking.calibration import (
    MAX_CALIBRATION_ROWS,
    POSE_RANKING_CALIBRATION_PARTITION_SCHEMA_ID,
    POSE_RANKING_CALIBRATION_ROW_SCHEMA_ID,
    PoseRankingCalibrationError,
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
    PoseRankingLeakageAudit,
    PoseRankingLeakagePolicy,
    audit_pose_ranking_leakage,
)
from .public_pose_ranking_corpus_intake import (
    FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY,
    PUBLIC_POSE_RANKING_CORPUS_MAX_RECEIPT_BYTES,
    PublicPoseRankingCorpusIntakeError,
    PublicPoseRankingCorpusIntakeReceipt,
    load_public_docking_split_manifest_file,
    verify_public_pose_ranking_corpus_intake_receipt,
)
from .public_split_provenance import (
    CASF_2016_DATASET_ID,
    PDBBIND_V2020_DATASET_ID,
    PublicDockingPartitionBinding,
    PublicDockingSplitError,
    PublicDockingSplitManifest,
    bind_pose_ranking_partition_to_public_split,
)


PUBLIC_POSE_RANKING_PARTITION_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_partition_identity/1.0.0"
)
PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_calibration_partition_intake/1.0.0"
)
PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_INPUT_BYTES = (
    256 * 1024 * 1024
)
PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_RECEIPT_BYTES = (
    4 * 1024 * 1024
)

_PARTITION_ROLES = ("fit_partition", "validation_partition")
_ROLE_TO_SPLIT = {
    "fit_partition": "fit",
    "validation_partition": "validation",
}
_LEAKAGE_OVERLAP_FIELDS = (
    "case_id",
    "pose_sha256",
    "target_id",
    "target_family",
    "receptor_sha256",
    "ligand_sha256",
    "scaffold_sha256",
    "scoring_protocol_sha256",
    "preparation_profile_sha256",
)
_FROZEN_PARTITION_LEAKAGE_POLICY = PoseRankingLeakagePolicy()
_SCIENTIFIC_BLOCKERS = (
    "partition_scores_and_labels_are_caller_provided_not_generated_here",
    "failure_inclusive_fit_view_selection_is_not_performed",
    "scorer_fit_is_not_performed",
    "validation_model_selection_is_not_performed",
    "posebusters_test_partition_is_not_loaded",
    "public_benchmark_metrics_are_absent",
    "independent_external_rerun_is_absent",
    "independent_scientific_review_is_absent",
    "public_docking_product_claim_is_not_authorized",
)
_CORPUS_MATERIALIZATION_ARGUMENT_KEYS = frozenset(
    {
        "fit_manifest_path",
        "validation_manifest_path",
        "test_manifest_path",
        "fit_validation_sequence_receipt_path",
        "fit_test_sequence_receipt_path",
        "validation_test_sequence_receipt_path",
        "expected_fit_manifest_file_sha256",
        "expected_fit_manifest_sha256",
        "expected_validation_manifest_file_sha256",
        "expected_validation_manifest_sha256",
        "expected_test_manifest_file_sha256",
        "expected_test_manifest_sha256",
        "expected_fit_validation_sequence_file_sha256",
        "expected_fit_validation_sequence_receipt_sha256",
        "expected_fit_test_sequence_file_sha256",
        "expected_fit_test_sequence_receipt_sha256",
        "expected_validation_test_sequence_file_sha256",
        "expected_validation_test_sequence_receipt_sha256",
    }
)
_ROW_KEYS = {
    "schema_id",
    "suite_id",
    "case_id",
    "pose_id",
    "target_id",
    "target_family",
    "split_role",
    "scoring_protocol_sha256",
    "preparation_profile_sha256",
    "receptor_sha256",
    "ligand_sha256",
    "scaffold_sha256",
    "pose_sha256",
    "status",
    "term_values",
    "native_like",
    "error_code",
}
_PARTITION_KEYS = {
    "schema_id",
    "dataset_id",
    "dataset_version",
    "split_role",
    "term_ids",
    "rows",
}


class PublicPoseRankingCalibrationPartitionIntakeError(ValueError):
    """A partition, corpus binding, or canonical receipt failed closed."""


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _plain_json(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            _plain_json(value),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "partition intake value is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION: Mapping[
    str, Any
] = MappingProxyType(
    {
        "schema_id": (
            "betelgeuze.engine_v2_public_pose_ranking_calibration_partition_"
            "intake_configuration/1.0.0"
        ),
        "corpus_policy_sha256": (
            FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY.fingerprint_sha256
        ),
        "partition_leakage_policy": MappingProxyType(
            _FROZEN_PARTITION_LEAKAGE_POLICY.to_dict()
        ),
        "partition_roles": _PARTITION_ROLES,
        "fit_label_policy": "allowed_for_fit_only",
        "validation_label_policy": "evaluation_only_never_fit",
        "test_partition_policy": "absent_and_forbidden",
        "receipt_write_policy": "mode_0600_no_overwrite",
    }
)
PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION_SHA256 = (
    _canonical_sha256(
        dict(
            PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION
        )
    )
)


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} must be a lowercase SHA-256"
        )
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} must be a lowercase SHA-256"
        )
    return digest


def _text(value: object, *, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} must be text"
        )
    text = value.strip()
    if not text or len(text) > maximum:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} must contain 1..{maximum} characters"
        )
    return text


def _integer(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} must be an integer"
        )
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} is outside bounds"
        )
    return integer


def _object(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in value
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} must be a JSON object with text keys"
        )
    return dict(value)


def _array(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} must be a JSON array"
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
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} keys differ; "
            f"missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _json_object_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PublicPoseRankingCalibrationPartitionIntakeError(
        f"non-finite JSON constant is forbidden: {value}"
    )


def _decode_json_object(data: bytes, *, name: str) -> dict[str, Any]:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} must be canonical ASCII JSON"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PublicPoseRankingCalibrationPartitionIntakeError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} is not valid JSON"
        ) from exc
    return _object(value, name=name)


def _read_regular_file(
    path: str | os.PathLike[str],
    *,
    name: str,
    maximum_bytes: int,
) -> tuple[bytes, str]:
    candidate = Path(path)
    try:
        path_metadata = os.lstat(candidate)
    except OSError as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} cannot be opened as a regular non-symlink file"
        ) from exc
    if stat.S_ISLNK(path_metadata.st_mode):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} cannot be opened as a regular non-symlink file"
        )
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{name} cannot be opened as a regular non-symlink file"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            metadata.st_dev != path_metadata.st_dev
            or metadata.st_ino != path_metadata.st_ino
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                f"{name} changed before read"
            )
        if not stat.S_ISREG(metadata.st_mode):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                f"{name} must be a regular file"
            )
        if metadata.st_size < 1 or metadata.st_size > maximum_bytes:
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                f"{name} size is outside the frozen bound"
            )
        chunks: list[bytes] = []
        remaining = metadata.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise PublicPoseRankingCalibrationPartitionIntakeError(
                    f"{name} changed during read"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                f"{name} changed during read"
            )
        data = b"".join(chunks)
    finally:
        os.close(descriptor)
    return data, hashlib.sha256(data).hexdigest()


def _parse_partition_row(value: object) -> PoseRankingCalibrationRow:
    payload = _object(value, name="calibration row")
    _exact_keys(payload, _ROW_KEYS, name="calibration row")
    term_values = _object(
        payload["term_values"],
        name="calibration row term_values",
    )
    try:
        row = PoseRankingCalibrationRow(
            schema_id=payload["schema_id"],
            suite_id=payload["suite_id"],
            case_id=payload["case_id"],
            pose_id=payload["pose_id"],
            target_id=payload["target_id"],
            target_family=payload["target_family"],
            split_role=payload["split_role"],
            scoring_protocol_sha256=payload["scoring_protocol_sha256"],
            preparation_profile_sha256=payload[
                "preparation_profile_sha256"
            ],
            receptor_sha256=payload["receptor_sha256"],
            ligand_sha256=payload["ligand_sha256"],
            scaffold_sha256=payload["scaffold_sha256"],
            pose_sha256=payload["pose_sha256"],
            status=payload["status"],
            term_values=term_values,
            native_like=payload["native_like"],
            error_code=payload["error_code"],
        )
    except (PoseRankingCalibrationError, TypeError) as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration row failed reconstruction"
        ) from exc
    if row.to_dict() != payload:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration row derived fields do not reconstruct exactly"
        )
    return row


def _parse_partition(
    value: object,
    *,
    expected_split_role: str,
) -> PoseRankingCalibrationPartition:
    payload = _object(value, name="calibration partition")
    _exact_keys(payload, _PARTITION_KEYS, name="calibration partition")
    rows = tuple(
        _parse_partition_row(item)
        for item in _array(payload["rows"], name="calibration partition rows")
    )
    if tuple((row.case_id, row.pose_id) for row in rows) != tuple(
        sorted((row.case_id, row.pose_id) for row in rows)
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration rows must be canonically ordered by case_id/pose_id"
        )
    try:
        partition = PoseRankingCalibrationPartition(
            schema_id=payload["schema_id"],
            dataset_id=payload["dataset_id"],
            dataset_version=payload["dataset_version"],
            split_role=payload["split_role"],
            rows=rows,
        )
    except (PoseRankingCalibrationError, TypeError) as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration partition failed reconstruction"
        ) from exc
    if partition.split_role != expected_split_role:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"calibration partition must use split_role={expected_split_role}"
        )
    if partition.to_dict() != payload:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration partition derived fields do not reconstruct exactly"
        )
    return partition


@dataclass(frozen=True, slots=True)
class PublicPoseRankingCalibrationPartitionIdentity:
    role: str
    source_file_sha256: str
    source_file_size_bytes: int
    partition_sha256: str
    partition_identity_sha256: str
    dataset_id: str
    dataset_version: str
    split_role: str
    term_ids: tuple[str, ...]
    row_count: int
    case_count: int
    successful_row_count: int
    failure_row_count: int
    positive_row_count: int
    negative_row_count: int
    pairwise_uninformative_case_ids: tuple[str, ...]
    schema_id: str = PUBLIC_POSE_RANKING_PARTITION_IDENTITY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_POSE_RANKING_PARTITION_IDENTITY_SCHEMA_ID:
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "unsupported calibration partition-identity schema"
            )
        role = _text(self.role, name="partition identity role")
        if role not in _PARTITION_ROLES:
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "unsupported calibration partition identity role"
            )
        split_role = _text(self.split_role, name="partition split role")
        if split_role != _ROLE_TO_SPLIT[role]:
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "partition identity role and split are cross-wired"
            )
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "split_role", split_role)
        for name in (
            "source_file_sha256",
            "partition_sha256",
            "partition_identity_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        object.__setattr__(
            self,
            "source_file_size_bytes",
            _integer(
                self.source_file_size_bytes,
                name="partition source file size",
                minimum=1,
                maximum=(
                    PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_INPUT_BYTES
                ),
            ),
        )
        object.__setattr__(
            self,
            "dataset_id",
            _text(self.dataset_id, name="partition dataset ID"),
        )
        object.__setattr__(
            self,
            "dataset_version",
            _text(self.dataset_version, name="partition dataset version"),
        )
        terms = tuple(
            _text(item, name="partition term ID") for item in self.term_ids
        )
        if not terms or terms != tuple(sorted(set(terms))):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "partition term IDs must be non-empty, unique, and sorted"
            )
        object.__setattr__(self, "term_ids", terms)
        row_count = _integer(
            self.row_count,
            name="partition row count",
            minimum=1,
            maximum=MAX_CALIBRATION_ROWS,
        )
        case_count = _integer(
            self.case_count,
            name="partition case count",
            minimum=1,
            maximum=row_count,
        )
        successful = _integer(
            self.successful_row_count,
            name="successful row count",
            minimum=1,
            maximum=row_count,
        )
        failure = _integer(
            self.failure_row_count,
            name="failure row count",
            minimum=0,
            maximum=row_count,
        )
        positive = _integer(
            self.positive_row_count,
            name="positive row count",
            minimum=0,
            maximum=successful,
        )
        negative = _integer(
            self.negative_row_count,
            name="negative row count",
            minimum=0,
            maximum=successful,
        )
        if successful + failure != row_count or positive + negative != successful:
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "partition row denominators do not reconcile"
            )
        uninformative = tuple(
            sorted(
                _text(item, name="pairwise-uninformative case ID")
                for item in self.pairwise_uninformative_case_ids
            )
        )
        if (
            len(uninformative) != len(set(uninformative))
            or len(uninformative) > case_count
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "pairwise-uninformative case IDs are duplicated or excessive"
            )
        object.__setattr__(self, "row_count", row_count)
        object.__setattr__(self, "case_count", case_count)
        object.__setattr__(self, "successful_row_count", successful)
        object.__setattr__(self, "failure_row_count", failure)
        object.__setattr__(self, "positive_row_count", positive)
        object.__setattr__(self, "negative_row_count", negative)
        object.__setattr__(
            self,
            "pairwise_uninformative_case_ids",
            uninformative,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "role": self.role,
            "source_file_sha256": self.source_file_sha256,
            "source_file_size_bytes": self.source_file_size_bytes,
            "partition_schema_id": (
                POSE_RANKING_CALIBRATION_PARTITION_SCHEMA_ID
            ),
            "row_schema_id": POSE_RANKING_CALIBRATION_ROW_SCHEMA_ID,
            "partition_sha256": self.partition_sha256,
            "partition_identity_sha256": self.partition_identity_sha256,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "split_role": self.split_role,
            "term_ids": list(self.term_ids),
            "row_count": self.row_count,
            "case_count": self.case_count,
            "successful_row_count": self.successful_row_count,
            "failure_row_count": self.failure_row_count,
            "positive_row_count": self.positive_row_count,
            "negative_row_count": self.negative_row_count,
            "pairwise_uninformative_case_ids": list(
                self.pairwise_uninformative_case_ids
            ),
        }


def _partition_identity(
    partition: PoseRankingCalibrationPartition,
    *,
    role: str,
    source_file_sha256: str,
    source_file_size_bytes: int,
) -> PublicPoseRankingCalibrationPartitionIdentity:
    case_rows: dict[str, list[PoseRankingCalibrationRow]] = {}
    for row in partition.rows:
        case_rows.setdefault(row.case_id, []).append(row)
    successful = tuple(
        row for row in partition.rows if row.status == "success"
    )
    positive = tuple(row for row in successful if row.native_like is True)
    negative = tuple(row for row in successful if row.native_like is False)
    uninformative = tuple(
        sorted(
            case_id
            for case_id, rows in case_rows.items()
            if not any(
                row.status == "success" and row.native_like is True
                for row in rows
            )
            or not any(
                row.status == "success" and row.native_like is False
                for row in rows
            )
        )
    )
    return PublicPoseRankingCalibrationPartitionIdentity(
        role=role,
        source_file_sha256=source_file_sha256,
        source_file_size_bytes=source_file_size_bytes,
        partition_sha256=partition.fingerprint_sha256,
        partition_identity_sha256=partition.identity_fingerprint_sha256,
        dataset_id=partition.dataset_id,
        dataset_version=partition.dataset_version,
        split_role=partition.split_role,
        term_ids=partition.term_ids,
        row_count=len(partition.rows),
        case_count=len(partition.case_ids),
        successful_row_count=len(successful),
        failure_row_count=len(partition.rows) - len(successful),
        positive_row_count=len(positive),
        negative_row_count=len(negative),
        pairwise_uninformative_case_ids=uninformative,
    )


def _load_partition_file(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_partition_sha256: str,
    role: str,
) -> tuple[
    PoseRankingCalibrationPartition,
    PublicPoseRankingCalibrationPartitionIdentity,
]:
    if role not in _PARTITION_ROLES:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "unsupported partition file role"
        )
    expected_file = _digest(
        expected_file_sha256,
        name=f"{role} expected file SHA-256",
    )
    expected_partition = _digest(
        expected_partition_sha256,
        name=f"{role} expected partition SHA-256",
    )
    data, file_sha256 = _read_regular_file(
        path,
        name=role,
        maximum_bytes=(
            PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_INPUT_BYTES
        ),
    )
    if file_sha256 != expected_file:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{role} file SHA-256 mismatch"
        )
    partition = _parse_partition(
        _decode_json_object(data, name=role),
        expected_split_role=_ROLE_TO_SPLIT[role],
    )
    if data != _canonical_bytes(partition.to_dict()) + b"\n":
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{role} must use canonical JSON plus one newline"
        )
    if partition.fingerprint_sha256 != expected_partition:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            f"{role} partition SHA-256 mismatch"
        )
    return partition, _partition_identity(
        partition,
        role=role,
        source_file_sha256=file_sha256,
        source_file_size_bytes=len(data),
    )


def load_public_pose_ranking_calibration_partition_file(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_partition_sha256: str,
    split_role: str,
) -> PoseRankingCalibrationPartition:
    """Load an exact canonical PDBbind-fit or CASF-validation partition."""

    normalized = _text(split_role, name="expected partition split role")
    role_by_split = {value: key for key, value in _ROLE_TO_SPLIT.items()}
    if normalized not in role_by_split:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "partition loader accepts only fit or validation"
        )
    partition, _ = _load_partition_file(
        path,
        expected_file_sha256=expected_file_sha256,
        expected_partition_sha256=expected_partition_sha256,
        role=role_by_split[normalized],
    )
    return partition


def _expected_pose_leakage_blockers(
    audit: PoseRankingLeakageAudit,
) -> tuple[str, ...]:
    overlaps = audit.overlaps
    if set(overlaps) != set(_LEAKAGE_OVERLAP_FIELDS):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "pose-level leakage overlap fields are incomplete"
        )
    policy = audit.policy
    required = {
        "case_id": True,
        "pose_sha256": True,
        "target_id": policy.require_target_disjoint,
        "target_family": policy.require_family_disjoint,
        "receptor_sha256": policy.require_receptor_disjoint,
        "ligand_sha256": policy.require_ligand_disjoint,
        "scaffold_sha256": policy.require_scaffold_disjoint,
    }
    blockers = [
        f"{field_name}_overlap"
        for field_name in _LEAKAGE_OVERLAP_FIELDS[:7]
        if required[field_name] and overlaps[field_name]
    ]
    if not overlaps["scoring_protocol_sha256"]:
        blockers.append("scoring_protocol_mismatch")
    if not overlaps["preparation_profile_sha256"]:
        blockers.append("preparation_profile_mismatch")
    return tuple(blockers)


@dataclass(frozen=True, slots=True)
class PublicPoseRankingCalibrationPartitionIntakeReceipt:
    corpus_receipt_source_file_sha256: str
    corpus_receipt_source_file_size_bytes: int
    corpus_receipt_sha256: str
    corpus_audit_sha256: str
    public_fit_validation_audit_sha256: str
    fit_manifest_sha256: str
    validation_manifest_sha256: str
    fit_partition: PublicPoseRankingCalibrationPartitionIdentity
    validation_partition: PublicPoseRankingCalibrationPartitionIdentity
    fit_binding: PublicDockingPartitionBinding
    validation_binding: PublicDockingPartitionBinding
    fit_validation_leakage_audit: PoseRankingLeakageAudit
    blockers: tuple[str, ...]
    schema_id: str = (
        PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_SCHEMA_ID
    )

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_SCHEMA_ID
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "unsupported calibration partition-intake schema"
            )
        for name in (
            "corpus_receipt_source_file_sha256",
            "corpus_receipt_sha256",
            "corpus_audit_sha256",
            "public_fit_validation_audit_sha256",
            "fit_manifest_sha256",
            "validation_manifest_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        object.__setattr__(
            self,
            "corpus_receipt_source_file_size_bytes",
            _integer(
                self.corpus_receipt_source_file_size_bytes,
                name="corpus receipt source file size",
                minimum=1,
                maximum=PUBLIC_POSE_RANKING_CORPUS_MAX_RECEIPT_BYTES,
            ),
        )
        if (
            not isinstance(
                self.fit_partition,
                PublicPoseRankingCalibrationPartitionIdentity,
            )
            or self.fit_partition.role != "fit_partition"
            or not isinstance(
                self.validation_partition,
                PublicPoseRankingCalibrationPartitionIdentity,
            )
            or self.validation_partition.role != "validation_partition"
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "partition identities are missing or cross-wired"
            )
        if not isinstance(self.fit_binding, PublicDockingPartitionBinding):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "fit public binding has the wrong type"
            )
        if not isinstance(
            self.validation_binding,
            PublicDockingPartitionBinding,
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "validation public binding has the wrong type"
            )
        if (
            self.fit_binding.split_manifest_sha256
            != self.fit_manifest_sha256
            or self.fit_binding.calibration_partition_sha256
            != self.fit_partition.partition_sha256
            or self.fit_binding.calibration_identity_sha256
            != self.fit_partition.partition_identity_sha256
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "fit public binding is not bound to the intake"
            )
        if (
            self.validation_binding.split_manifest_sha256
            != self.validation_manifest_sha256
            or self.validation_binding.calibration_partition_sha256
            != self.validation_partition.partition_sha256
            or self.validation_binding.calibration_identity_sha256
            != self.validation_partition.partition_identity_sha256
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "validation public binding is not bound to the intake"
            )
        leakage = self.fit_validation_leakage_audit
        if not isinstance(leakage, PoseRankingLeakageAudit):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "fit-validation leakage audit has the wrong type"
            )
        if (
            leakage.fit_partition_sha256
            != self.fit_partition.partition_sha256
            or leakage.evaluation_partition_sha256
            != self.validation_partition.partition_sha256
            or leakage.fit_identity_sha256
            != self.fit_partition.partition_identity_sha256
            or leakage.evaluation_identity_sha256
            != self.validation_partition.partition_identity_sha256
            or leakage.policy.to_dict()
            != _FROZEN_PARTITION_LEAKAGE_POLICY.to_dict()
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "fit-validation leakage audit is not bound to the intake"
            )
        if leakage.blockers != _expected_pose_leakage_blockers(leakage):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "fit-validation leakage blockers do not match overlaps"
            )
        blockers = tuple(
            _text(item, name="partition-intake blocker")
            for item in self.blockers
        )
        if len(blockers) != len(set(blockers)):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "partition-intake blockers must be unique"
            )
        expected_blockers: list[str] = []
        expected_blockers.extend(
            f"fit_binding_{item}" for item in self.fit_binding.blockers
        )
        expected_blockers.extend(
            f"validation_binding_{item}"
            for item in self.validation_binding.blockers
        )
        expected_blockers.extend(
            f"fit_validation_{item}" for item in leakage.blockers
        )
        if self.fit_partition.term_ids != self.validation_partition.term_ids:
            expected_blockers.append("fit_validation_term_schema_mismatch")
        if self.fit_partition.pairwise_uninformative_case_ids:
            expected_blockers.append(
                "fit_pairwise_training_case_coverage_incomplete"
            )
        if blockers != tuple(dict.fromkeys(expected_blockers)):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "partition-intake blockers do not match the evidence"
            )
        object.__setattr__(self, "blockers", blockers)

    @property
    def passed(self) -> bool:
        return not self.blockers

    @property
    def ready_for_direct_fit(self) -> bool:
        return self.passed and self.fit_partition.failure_row_count == 0

    @property
    def receipt_sha256(self) -> str:
        return _canonical_sha256(self._payload_without_receipt_sha256())

    def _payload_without_receipt_sha256(self) -> dict[str, Any]:
        direct_fit_blockers = []
        if not self.passed:
            direct_fit_blockers.append("partition_intake_not_ready")
        if self.fit_partition.failure_row_count:
            direct_fit_blockers.append(
                "fit_failure_rows_require_bound_success_training_view"
            )
        return {
            "schema_id": self.schema_id,
            "configuration": _plain_json(
                PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION
            ),
            "configuration_sha256": (
                PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION_SHA256
            ),
            "corpus_receipt_source_file_sha256": (
                self.corpus_receipt_source_file_sha256
            ),
            "corpus_receipt_source_file_size_bytes": (
                self.corpus_receipt_source_file_size_bytes
            ),
            "corpus_receipt_sha256": self.corpus_receipt_sha256,
            "corpus_audit_sha256": self.corpus_audit_sha256,
            "public_fit_validation_audit_sha256": (
                self.public_fit_validation_audit_sha256
            ),
            "fit_manifest_sha256": self.fit_manifest_sha256,
            "validation_manifest_sha256": self.validation_manifest_sha256,
            "fit_partition": self.fit_partition.to_dict(),
            "validation_partition": self.validation_partition.to_dict(),
            "fit_binding": self.fit_binding.to_dict(),
            "validation_binding": self.validation_binding.to_dict(),
            "fit_validation_leakage_audit": (
                self.fit_validation_leakage_audit.to_dict()
            ),
            "blockers": list(self.blockers),
            "partition_intake_ready": self.passed,
            "ready_for_failure_inclusive_training_view_materialization": (
                self.passed
            ),
            "direct_fit_blockers": direct_fit_blockers,
            "ready_for_direct_fit": self.ready_for_direct_fit,
            "fit_labels_present": True,
            "validation_labels_present": True,
            "validation_labels_used_for_fit": False,
            "test_partition_present": False,
            "test_labels_present": False,
            "test_labels_used_for_fit": False,
            "test_labels_used_for_model_selection": False,
            "fit_or_model_selection_performed": False,
            "benchmark_executed": False,
            "scientifically_validated": False,
            "public_docking_claim_authorized": False,
            "claim_safe": False,
            "scientific_blockers": list(_SCIENTIFIC_BLOCKERS),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload_without_receipt_sha256()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload

    def write_json(self, path: str | os.PathLike[str]) -> None:
        destination = Path(path)
        if not destination.parent.is_dir():
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "receipt output parent must already exist"
            )
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if (
            len(payload)
            > PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_RECEIPT_BYTES
        ):
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "partition-intake receipt exceeds the frozen size bound"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(destination, flags, 0o600)
        except OSError as exc:
            raise PublicPoseRankingCalibrationPartitionIntakeError(
                "receipt output exists or cannot be created safely"
            ) from exc
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise PublicPoseRankingCalibrationPartitionIntakeError(
                        "receipt write did not make progress"
                    )
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def audit_public_pose_ranking_calibration_partitions(
    *,
    corpus_intake_receipt: PublicPoseRankingCorpusIntakeReceipt,
    corpus_receipt_source_file_sha256: str,
    corpus_receipt_source_file_size_bytes: int,
    fit_manifest: PublicDockingSplitManifest,
    validation_manifest: PublicDockingSplitManifest,
    fit_partition: PoseRankingCalibrationPartition,
    fit_partition_source_file_sha256: str,
    fit_partition_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    validation_partition_source_file_sha256: str,
    validation_partition_source_file_size_bytes: int,
) -> PublicPoseRankingCalibrationPartitionIntakeReceipt:
    """Bind failure-inclusive fit/validation partitions to a passing corpus."""

    if not isinstance(
        corpus_intake_receipt,
        PublicPoseRankingCorpusIntakeReceipt,
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "corpus intake receipt has the wrong type"
        )
    if not corpus_intake_receipt.audit.passed:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration partition intake requires a passing corpus intake"
        )
    if (
        corpus_intake_receipt.audit.policy.fingerprint_sha256
        != FROZEN_PUBLIC_POSE_RANKING_CORPUS_POLICY.fingerprint_sha256
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration partition intake requires the frozen corpus policy"
        )
    if (
        not isinstance(fit_manifest, PublicDockingSplitManifest)
        or not isinstance(validation_manifest, PublicDockingSplitManifest)
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "fit and validation manifests have the wrong type"
        )
    audit = corpus_intake_receipt.audit
    if (
        fit_manifest.source.dataset_id != PDBBIND_V2020_DATASET_ID
        or fit_manifest.split_role != "fit"
        or validation_manifest.source.dataset_id != CASF_2016_DATASET_ID
        or validation_manifest.split_role != "validation"
        or fit_manifest.fingerprint_sha256 != audit.fit_manifest_sha256
        or validation_manifest.fingerprint_sha256
        != audit.validation_manifest_sha256
        or len(fit_manifest.cases) != audit.fit_case_count
        or len(validation_manifest.cases) != audit.validation_case_count
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "fit/validation manifests are not bound to the corpus intake"
        )
    if not isinstance(fit_partition, PoseRankingCalibrationPartition):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "fit partition has the wrong type"
        )
    if not isinstance(
        validation_partition,
        PoseRankingCalibrationPartition,
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "validation partition has the wrong type"
        )
    fit_identity = _partition_identity(
        fit_partition,
        role="fit_partition",
        source_file_sha256=fit_partition_source_file_sha256,
        source_file_size_bytes=fit_partition_source_file_size_bytes,
    )
    validation_identity = _partition_identity(
        validation_partition,
        role="validation_partition",
        source_file_sha256=validation_partition_source_file_sha256,
        source_file_size_bytes=validation_partition_source_file_size_bytes,
    )
    try:
        fit_binding = bind_pose_ranking_partition_to_public_split(
            fit_partition,
            fit_manifest,
        )
        validation_binding = bind_pose_ranking_partition_to_public_split(
            validation_partition,
            validation_manifest,
        )
        leakage = audit_pose_ranking_leakage(
            fit_partition,
            validation_partition,
            policy=_FROZEN_PARTITION_LEAKAGE_POLICY,
        )
    except (PublicDockingSplitError, PoseRankingCalibrationError) as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "partition binding or leakage reconstruction failed"
        ) from exc
    blockers: list[str] = []
    blockers.extend(
        f"fit_binding_{item}" for item in fit_binding.blockers
    )
    blockers.extend(
        f"validation_binding_{item}" for item in validation_binding.blockers
    )
    blockers.extend(
        f"fit_validation_{item}" for item in leakage.blockers
    )
    if fit_identity.term_ids != validation_identity.term_ids:
        blockers.append("fit_validation_term_schema_mismatch")
    if fit_identity.pairwise_uninformative_case_ids:
        blockers.append("fit_pairwise_training_case_coverage_incomplete")
    return PublicPoseRankingCalibrationPartitionIntakeReceipt(
        corpus_receipt_source_file_sha256=(
            corpus_receipt_source_file_sha256
        ),
        corpus_receipt_source_file_size_bytes=(
            corpus_receipt_source_file_size_bytes
        ),
        corpus_receipt_sha256=corpus_intake_receipt.receipt_sha256,
        corpus_audit_sha256=audit.fingerprint_sha256,
        public_fit_validation_audit_sha256=(
            audit.fit_validation_audit.fingerprint_sha256
        ),
        fit_manifest_sha256=fit_manifest.fingerprint_sha256,
        validation_manifest_sha256=validation_manifest.fingerprint_sha256,
        fit_partition=fit_identity,
        validation_partition=validation_identity,
        fit_binding=fit_binding,
        validation_binding=validation_binding,
        fit_validation_leakage_audit=leakage,
        blockers=tuple(dict.fromkeys(blockers)),
    )


def _normalize_corpus_arguments(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(
        _CORPUS_MATERIALIZATION_ARGUMENT_KEYS
    ):
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "corpus materialization arguments are incomplete or unexpected"
        )
    return dict(value)


def materialize_public_pose_ranking_calibration_partition_intake(
    *,
    corpus_receipt_path: str | os.PathLike[str],
    expected_corpus_receipt_file_sha256: str,
    expected_corpus_receipt_sha256: str,
    corpus_materialization_arguments: Mapping[str, Any],
    fit_partition_path: str | os.PathLike[str],
    expected_fit_partition_file_sha256: str,
    expected_fit_partition_sha256: str,
    validation_partition_path: str | os.PathLike[str],
    expected_validation_partition_file_sha256: str,
    expected_validation_partition_sha256: str,
) -> PublicPoseRankingCalibrationPartitionIntakeReceipt:
    """Verify the corpus and materialize exact fit/validation partition intake."""

    corpus_arguments = _normalize_corpus_arguments(
        corpus_materialization_arguments
    )
    try:
        corpus = verify_public_pose_ranking_corpus_intake_receipt(
            corpus_receipt_path=corpus_receipt_path,
            **corpus_arguments,
        )
        fit_manifest = load_public_docking_split_manifest_file(
            corpus_arguments["fit_manifest_path"],
            expected_file_sha256=corpus_arguments[
                "expected_fit_manifest_file_sha256"
            ],
            expected_manifest_sha256=corpus_arguments[
                "expected_fit_manifest_sha256"
            ],
        )
        validation_manifest = load_public_docking_split_manifest_file(
            corpus_arguments["validation_manifest_path"],
            expected_file_sha256=corpus_arguments[
                "expected_validation_manifest_file_sha256"
            ],
            expected_manifest_sha256=corpus_arguments[
                "expected_validation_manifest_sha256"
            ],
        )
    except PublicPoseRankingCorpusIntakeError as exc:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "public corpus verification failed"
        ) from exc
    expected_corpus_file = _digest(
        expected_corpus_receipt_file_sha256,
        name="expected corpus receipt file SHA-256",
    )
    expected_corpus_receipt = _digest(
        expected_corpus_receipt_sha256,
        name="expected corpus receipt SHA-256",
    )
    corpus_data, corpus_file_sha256 = _read_regular_file(
        corpus_receipt_path,
        name="public corpus intake receipt",
        maximum_bytes=PUBLIC_POSE_RANKING_CORPUS_MAX_RECEIPT_BYTES,
    )
    if corpus_file_sha256 != expected_corpus_file:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "public corpus receipt file SHA-256 mismatch"
        )
    if corpus.receipt_sha256 != expected_corpus_receipt:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "public corpus receipt SHA-256 mismatch"
        )
    fit_partition, fit_identity = _load_partition_file(
        fit_partition_path,
        expected_file_sha256=expected_fit_partition_file_sha256,
        expected_partition_sha256=expected_fit_partition_sha256,
        role="fit_partition",
    )
    validation_partition, validation_identity = _load_partition_file(
        validation_partition_path,
        expected_file_sha256=expected_validation_partition_file_sha256,
        expected_partition_sha256=expected_validation_partition_sha256,
        role="validation_partition",
    )
    return audit_public_pose_ranking_calibration_partitions(
        corpus_intake_receipt=corpus,
        corpus_receipt_source_file_sha256=corpus_file_sha256,
        corpus_receipt_source_file_size_bytes=len(corpus_data),
        fit_manifest=fit_manifest,
        validation_manifest=validation_manifest,
        fit_partition=fit_partition,
        fit_partition_source_file_sha256=(
            fit_identity.source_file_sha256
        ),
        fit_partition_source_file_size_bytes=(
            fit_identity.source_file_size_bytes
        ),
        validation_partition=validation_partition,
        validation_partition_source_file_sha256=(
            validation_identity.source_file_sha256
        ),
        validation_partition_source_file_size_bytes=(
            validation_identity.source_file_size_bytes
        ),
    )


def verify_public_pose_ranking_calibration_partition_intake_receipt(
    *,
    partition_intake_receipt_path: str | os.PathLike[str],
    **materialization_arguments: Any,
) -> PublicPoseRankingCalibrationPartitionIntakeReceipt:
    """Reconstruct and byte-compare one canonical partition-intake receipt."""

    expected = (
        materialize_public_pose_ranking_calibration_partition_intake(
            **materialization_arguments
        )
    )
    data, _ = _read_regular_file(
        partition_intake_receipt_path,
        name="calibration partition-intake receipt",
        maximum_bytes=(
            PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_RECEIPT_BYTES
        ),
    )
    metadata = os.stat(
        partition_intake_receipt_path,
        follow_symlinks=False,
    )
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration partition-intake receipt mode must be 0600"
        )
    if data != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PublicPoseRankingCalibrationPartitionIntakeError(
            "calibration partition-intake receipt differs from reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=(
            "betelgeuze-engine-v2-public-ranking-calibration-partition-intake"
        ),
        description=(
            "Bind PDBbind fit and CASF validation score partitions only after "
            "the three-way public corpus intake passes."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--corpus-receipt", required=True)
        subparser.add_argument(
            "--expected-corpus-receipt-file-sha256",
            required=True,
        )
        subparser.add_argument(
            "--expected-corpus-receipt-sha256",
            required=True,
        )
        for role in ("fit", "validation", "test"):
            subparser.add_argument(f"--{role}-manifest", required=True)
            subparser.add_argument(
                f"--expected-{role}-manifest-file-sha256",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{role}-manifest-sha256",
                required=True,
            )
        for role in (
            "fit-validation",
            "fit-test",
            "validation-test",
        ):
            subparser.add_argument(
                f"--{role}-sequence-receipt",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{role}-sequence-file-sha256",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{role}-sequence-receipt-sha256",
                required=True,
            )
        for role in ("fit", "validation"):
            subparser.add_argument(
                f"--{role}-partition",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{role}-partition-file-sha256",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{role}-partition-sha256",
                required=True,
            )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--partition-intake-receipt",
        required=True,
    )
    return parser


def _corpus_arguments(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "fit_manifest_path": args.fit_manifest,
        "validation_manifest_path": args.validation_manifest,
        "test_manifest_path": args.test_manifest,
        "fit_validation_sequence_receipt_path": (
            args.fit_validation_sequence_receipt
        ),
        "fit_test_sequence_receipt_path": args.fit_test_sequence_receipt,
        "validation_test_sequence_receipt_path": (
            args.validation_test_sequence_receipt
        ),
        "expected_fit_manifest_file_sha256": (
            args.expected_fit_manifest_file_sha256
        ),
        "expected_fit_manifest_sha256": (
            args.expected_fit_manifest_sha256
        ),
        "expected_validation_manifest_file_sha256": (
            args.expected_validation_manifest_file_sha256
        ),
        "expected_validation_manifest_sha256": (
            args.expected_validation_manifest_sha256
        ),
        "expected_test_manifest_file_sha256": (
            args.expected_test_manifest_file_sha256
        ),
        "expected_test_manifest_sha256": (
            args.expected_test_manifest_sha256
        ),
        "expected_fit_validation_sequence_file_sha256": (
            args.expected_fit_validation_sequence_file_sha256
        ),
        "expected_fit_validation_sequence_receipt_sha256": (
            args.expected_fit_validation_sequence_receipt_sha256
        ),
        "expected_fit_test_sequence_file_sha256": (
            args.expected_fit_test_sequence_file_sha256
        ),
        "expected_fit_test_sequence_receipt_sha256": (
            args.expected_fit_test_sequence_receipt_sha256
        ),
        "expected_validation_test_sequence_file_sha256": (
            args.expected_validation_test_sequence_file_sha256
        ),
        "expected_validation_test_sequence_receipt_sha256": (
            args.expected_validation_test_sequence_receipt_sha256
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common: dict[str, Any] = {
        "corpus_receipt_path": args.corpus_receipt,
        "expected_corpus_receipt_file_sha256": (
            args.expected_corpus_receipt_file_sha256
        ),
        "expected_corpus_receipt_sha256": (
            args.expected_corpus_receipt_sha256
        ),
        "corpus_materialization_arguments": _corpus_arguments(args),
        "fit_partition_path": args.fit_partition,
        "expected_fit_partition_file_sha256": (
            args.expected_fit_partition_file_sha256
        ),
        "expected_fit_partition_sha256": (
            args.expected_fit_partition_sha256
        ),
        "validation_partition_path": args.validation_partition,
        "expected_validation_partition_file_sha256": (
            args.expected_validation_partition_file_sha256
        ),
        "expected_validation_partition_sha256": (
            args.expected_validation_partition_sha256
        ),
    }
    if args.command == "materialize":
        receipt = (
            materialize_public_pose_ranking_calibration_partition_intake(
                **common
            )
        )
        receipt.write_json(args.output)
    else:
        receipt = (
            verify_public_pose_ranking_calibration_partition_intake_receipt(
                partition_intake_receipt_path=(
                    args.partition_intake_receipt
                ),
                **common,
            )
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.receipt_sha256,
                "partition_intake_ready": receipt.passed,
                "ready_for_direct_fit": receipt.ready_for_direct_fit,
                "fit_case_count": receipt.fit_partition.case_count,
                "validation_case_count": (
                    receipt.validation_partition.case_count
                ),
                "fit_failure_row_count": (
                    receipt.fit_partition.failure_row_count
                ),
                "validation_failure_row_count": (
                    receipt.validation_partition.failure_row_count
                ),
                "blockers": list(receipt.blockers),
                "validation_labels_used_for_fit": False,
                "test_partition_present": False,
                "fit_or_model_selection_performed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION",
    "PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_INTAKE_CONFIGURATION_SHA256",
    "PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_INPUT_BYTES",
    "PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_RECEIPT_BYTES",
    "PUBLIC_POSE_RANKING_PARTITION_IDENTITY_SCHEMA_ID",
    "PublicPoseRankingCalibrationPartitionIdentity",
    "PublicPoseRankingCalibrationPartitionIntakeError",
    "PublicPoseRankingCalibrationPartitionIntakeReceipt",
    "audit_public_pose_ranking_calibration_partitions",
    "load_public_pose_ranking_calibration_partition_file",
    "materialize_public_pose_ranking_calibration_partition_intake",
    "verify_public_pose_ranking_calibration_partition_intake_receipt",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
