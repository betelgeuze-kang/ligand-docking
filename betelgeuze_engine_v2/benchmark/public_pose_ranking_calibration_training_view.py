"""Bound success-only training view for public pose-ranking calibration.

Every successful PDBbind fit row is included unchanged. Every explicit failure
row is excluded only from the executable training partition and retained as a
source-bound disposition. CASF validation rows are used only to recompute
identity leakage; validation labels are never used for selection or fitting.

The resulting receipt embeds the exact training partition but performs no
production fit, hyperparameter selection, test access, benchmark, or claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from ..docking.calibration import (
    PoseRankingCalibrationConfig,
    PoseRankingCalibrationError,
    PoseRankingCalibrationModel,
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
    PoseRankingLeakageAudit,
    PoseRankingLeakagePolicy,
    audit_pose_ranking_leakage,
    fit_pose_ranking_calibration,
)
from .public_pose_ranking_calibration_partition_intake import (
    PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_RECEIPT_BYTES,
    PublicPoseRankingCalibrationPartitionIdentity,
    PublicPoseRankingCalibrationPartitionIntakeError,
    PublicPoseRankingCalibrationPartitionIntakeReceipt,
    _canonical_bytes,
    _canonical_sha256,
    _expected_pose_leakage_blockers,
    _read_regular_file,
    load_public_pose_ranking_calibration_partition_file,
    verify_public_pose_ranking_calibration_partition_intake_receipt,
)


PUBLIC_POSE_RANKING_TRAINING_ROW_DISPOSITION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_training_row_disposition/1.0.0"
)
PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_calibration_training_view/1.0.0"
)
PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES = (
    512 * 1024 * 1024
)

_FROZEN_TRAINING_VIEW_LEAKAGE_POLICY = PoseRankingLeakagePolicy()
_PARTITION_INTAKE_MATERIALIZATION_ARGUMENT_KEYS = frozenset(
    {
        "corpus_receipt_path",
        "expected_corpus_receipt_file_sha256",
        "expected_corpus_receipt_sha256",
        "corpus_materialization_arguments",
        "fit_partition_path",
        "expected_fit_partition_file_sha256",
        "expected_fit_partition_sha256",
        "validation_partition_path",
        "expected_validation_partition_file_sha256",
        "expected_validation_partition_sha256",
    }
)
_SCIENTIFIC_BLOCKERS = (
    "training_view_materialization_is_not_a_production_model_fit",
    "calibration_configuration_is_not_frozen_by_this_receipt",
    "casf_validation_selection_is_not_performed",
    "posebusters_test_partition_is_not_loaded",
    "public_benchmark_metrics_are_absent",
    "independent_external_rerun_is_absent",
    "independent_scientific_review_is_absent",
    "public_docking_product_claim_is_not_authorized",
)


class PublicPoseRankingCalibrationTrainingViewError(ValueError):
    """A source row, selection, leakage, or receipt binding failed closed."""


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _plain_json(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingCalibrationTrainingViewError(
            f"{name} must be a lowercase SHA-256"
        )
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise PublicPoseRankingCalibrationTrainingViewError(
            f"{name} must be a lowercase SHA-256"
        )
    return digest


def _text(
    value: object,
    *,
    name: str,
    maximum: int = 256,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingCalibrationTrainingViewError(
            f"{name} must be text"
        )
    text = value.strip()
    if (
        (not text and not allow_empty)
        or len(text) > maximum
        or any(character in "\r\n\x00" for character in text)
    ):
        raise PublicPoseRankingCalibrationTrainingViewError(
            f"{name} is outside the frozen text bound"
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
        raise PublicPoseRankingCalibrationTrainingViewError(
            f"{name} must be an integer"
        )
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        raise PublicPoseRankingCalibrationTrainingViewError(
            f"{name} is outside bounds"
        )
    return integer


PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION: Mapping[
    str, Any
] = MappingProxyType(
    {
        "schema_id": (
            "betelgeuze.engine_v2_public_pose_ranking_calibration_training_"
            "view_configuration/1.0.0"
        ),
        "source_role": "pdbbind_fit_failure_inclusive_partition",
        "selection_fields": ("status",),
        "included_status": "success",
        "excluded_status": "failure",
        "included_row_policy": "byte_semantic_row_object_unchanged",
        "failure_policy": "retain_one_disposition_per_excluded_source_row",
        "validation_use": "identity_leakage_audit_only",
        "validation_labels_for_selection_or_fit": "forbidden",
        "test_partition": "absent_and_forbidden",
        "leakage_policy": MappingProxyType(
            _FROZEN_TRAINING_VIEW_LEAKAGE_POLICY.to_dict()
        ),
        "receipt_write_policy": "mode_0600_no_overwrite",
    }
)
PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION_SHA256 = (
    _canonical_sha256(
        dict(PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION)
    )
)


@dataclass(frozen=True, slots=True)
class PublicPoseRankingTrainingRowDisposition:
    source_row_sha256: str
    case_id: str
    pose_id: str
    source_status: str
    selection: str
    reason: str
    source_error_code: str
    schema_id: str = (
        PUBLIC_POSE_RANKING_TRAINING_ROW_DISPOSITION_SCHEMA_ID
    )

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != PUBLIC_POSE_RANKING_TRAINING_ROW_DISPOSITION_SCHEMA_ID
        ):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "unsupported training-row disposition schema"
            )
        object.__setattr__(
            self,
            "source_row_sha256",
            _digest(self.source_row_sha256, name="source row SHA-256"),
        )
        for name in ("case_id", "pose_id"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name=name),
            )
        status = _text(self.source_status, name="source row status")
        selection = _text(self.selection, name="row selection")
        reason = _text(self.reason, name="row selection reason")
        error_code = _text(
            self.source_error_code,
            name="source error code",
            allow_empty=True,
        )
        if status == "success":
            expected = (
                "included",
                "included_success_row_unchanged",
                "",
            )
        elif status == "failure":
            expected = (
                "excluded",
                "excluded_failure_row_without_terms_or_label",
                error_code,
            )
            if not error_code:
                raise PublicPoseRankingCalibrationTrainingViewError(
                    "excluded failure disposition requires an error code"
                )
        else:
            raise PublicPoseRankingCalibrationTrainingViewError(
                "source row status must be success or failure"
            )
        if (selection, reason, error_code) != expected:
            raise PublicPoseRankingCalibrationTrainingViewError(
                "row disposition differs from the frozen status-only rule"
            )
        object.__setattr__(self, "source_status", status)
        object.__setattr__(self, "selection", selection)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "source_error_code", error_code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "source_row_sha256": self.source_row_sha256,
            "case_id": self.case_id,
            "pose_id": self.pose_id,
            "source_status": self.source_status,
            "selection": self.selection,
            "reason": self.reason,
            "source_error_code": self.source_error_code,
        }


def _disposition(
    row: PoseRankingCalibrationRow,
) -> PublicPoseRankingTrainingRowDisposition:
    if row.status == "success":
        return PublicPoseRankingTrainingRowDisposition(
            source_row_sha256=row.fingerprint_sha256,
            case_id=row.case_id,
            pose_id=row.pose_id,
            source_status="success",
            selection="included",
            reason="included_success_row_unchanged",
            source_error_code="",
        )
    return PublicPoseRankingTrainingRowDisposition(
        source_row_sha256=row.fingerprint_sha256,
        case_id=row.case_id,
        pose_id=row.pose_id,
        source_status="failure",
        selection="excluded",
        reason="excluded_failure_row_without_terms_or_label",
        source_error_code=row.error_code,
    )


def _pairwise_uninformative_case_ids(
    partition: PoseRankingCalibrationPartition,
) -> tuple[str, ...]:
    case_rows: dict[str, list[PoseRankingCalibrationRow]] = {}
    for row in partition.rows:
        case_rows.setdefault(row.case_id, []).append(row)
    return tuple(
        sorted(
            case_id
            for case_id, rows in case_rows.items()
            if not any(row.native_like is True for row in rows)
            or not any(row.native_like is False for row in rows)
        )
    )


@dataclass(frozen=True, slots=True)
class PublicPoseRankingCalibrationTrainingViewReceipt:
    partition_intake_receipt_source_file_sha256: str
    partition_intake_receipt_source_file_size_bytes: int
    partition_intake_receipt_sha256: str
    partition_intake_corpus_receipt_sha256: str
    partition_intake_fit_validation_leakage_audit_sha256: str
    source_fit_partition: PublicPoseRankingCalibrationPartitionIdentity
    validation_partition: PublicPoseRankingCalibrationPartitionIdentity
    training_partition: PoseRankingCalibrationPartition
    row_dispositions: tuple[PublicPoseRankingTrainingRowDisposition, ...]
    fit_validation_training_leakage_audit: PoseRankingLeakageAudit
    blockers: tuple[str, ...]
    schema_id: str = PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_SCHEMA_ID

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_SCHEMA_ID
        ):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "unsupported calibration training-view schema"
            )
        for name in (
            "partition_intake_receipt_source_file_sha256",
            "partition_intake_receipt_sha256",
            "partition_intake_corpus_receipt_sha256",
            "partition_intake_fit_validation_leakage_audit_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        object.__setattr__(
            self,
            "partition_intake_receipt_source_file_size_bytes",
            _integer(
                self.partition_intake_receipt_source_file_size_bytes,
                name="partition-intake receipt source file size",
                minimum=1,
                maximum=(
                    PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_RECEIPT_BYTES
                ),
            ),
        )
        if (
            not isinstance(
                self.source_fit_partition,
                PublicPoseRankingCalibrationPartitionIdentity,
            )
            or self.source_fit_partition.role != "fit_partition"
            or not isinstance(
                self.validation_partition,
                PublicPoseRankingCalibrationPartitionIdentity,
            )
            or self.validation_partition.role != "validation_partition"
        ):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "source partition identities are missing or cross-wired"
            )
        training = self.training_partition
        if (
            not isinstance(training, PoseRankingCalibrationPartition)
            or training.split_role != "fit"
            or training.dataset_id != self.source_fit_partition.dataset_id
            or training.dataset_version
            != self.source_fit_partition.dataset_version
            or training.term_ids != self.source_fit_partition.term_ids
            or len(training.rows)
            != self.source_fit_partition.successful_row_count
            or len(training.case_ids) != self.source_fit_partition.case_count
            or any(row.status != "success" for row in training.rows)
        ):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training partition does not preserve the admitted fit source"
            )
        if _pairwise_uninformative_case_ids(training):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training partition contains a pairwise-uninformative case"
            )
        dispositions = tuple(self.row_dispositions)
        if (
            len(dispositions) != self.source_fit_partition.row_count
            or any(
                not isinstance(
                    item,
                    PublicPoseRankingTrainingRowDisposition,
                )
                for item in dispositions
            )
            or tuple((item.case_id, item.pose_id) for item in dispositions)
            != tuple(
                sorted((item.case_id, item.pose_id) for item in dispositions)
            )
            or len(
                {
                    (item.case_id, item.pose_id)
                    for item in dispositions
                }
            )
            != len(dispositions)
            or len({item.source_row_sha256 for item in dispositions})
            != len(dispositions)
        ):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training row dispositions are incomplete or duplicated"
            )
        included = {
            (item.case_id, item.pose_id, item.source_row_sha256)
            for item in dispositions
            if item.selection == "included"
        }
        training_rows = {
            (row.case_id, row.pose_id, row.fingerprint_sha256)
            for row in training.rows
        }
        excluded = tuple(
            item for item in dispositions if item.selection == "excluded"
        )
        if (
            included != training_rows
            or len(included)
            != self.source_fit_partition.successful_row_count
            or len(excluded) != self.source_fit_partition.failure_row_count
            or {
                item.case_id for item in dispositions
            }
            != set(training.case_ids)
        ):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training view row accounting does not reconcile"
            )
        leakage = self.fit_validation_training_leakage_audit
        if not isinstance(leakage, PoseRankingLeakageAudit):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training-view leakage audit has the wrong type"
            )
        if (
            leakage.fit_partition_sha256 != training.fingerprint_sha256
            or leakage.evaluation_partition_sha256
            != self.validation_partition.partition_sha256
            or leakage.fit_identity_sha256
            != training.identity_fingerprint_sha256
            or leakage.evaluation_identity_sha256
            != self.validation_partition.partition_identity_sha256
            or leakage.policy.to_dict()
            != _FROZEN_TRAINING_VIEW_LEAKAGE_POLICY.to_dict()
        ):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training-view leakage audit is not bound to the receipt"
            )
        if leakage.blockers != _expected_pose_leakage_blockers(leakage):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training-view leakage blockers do not match overlaps"
            )
        blockers = tuple(
            _text(item, name="training-view blocker")
            for item in self.blockers
        )
        expected_blockers = tuple(
            f"fit_validation_{item}" for item in leakage.blockers
        )
        if blockers != expected_blockers:
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training-view blockers do not match the evidence"
            )
        object.__setattr__(self, "row_dispositions", dispositions)
        object.__setattr__(self, "blockers", blockers)

    @property
    def ready_for_fit(self) -> bool:
        return not self.blockers

    @property
    def receipt_sha256(self) -> str:
        return _canonical_sha256(self._payload_without_receipt_sha256())

    def _payload_without_receipt_sha256(self) -> dict[str, Any]:
        included_count = sum(
            item.selection == "included" for item in self.row_dispositions
        )
        excluded_count = len(self.row_dispositions) - included_count
        return {
            "schema_id": self.schema_id,
            "configuration": _plain_json(
                PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION
            ),
            "configuration_sha256": (
                PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION_SHA256
            ),
            "partition_intake_receipt_source_file_sha256": (
                self.partition_intake_receipt_source_file_sha256
            ),
            "partition_intake_receipt_source_file_size_bytes": (
                self.partition_intake_receipt_source_file_size_bytes
            ),
            "partition_intake_receipt_sha256": (
                self.partition_intake_receipt_sha256
            ),
            "partition_intake_corpus_receipt_sha256": (
                self.partition_intake_corpus_receipt_sha256
            ),
            "partition_intake_fit_validation_leakage_audit_sha256": (
                self.partition_intake_fit_validation_leakage_audit_sha256
            ),
            "source_fit_partition": self.source_fit_partition.to_dict(),
            "validation_partition": self.validation_partition.to_dict(),
            "training_partition": self.training_partition.to_dict(),
            "training_partition_sha256": (
                self.training_partition.fingerprint_sha256
            ),
            "training_partition_identity_sha256": (
                self.training_partition.identity_fingerprint_sha256
            ),
            "row_dispositions": [
                item.to_dict() for item in self.row_dispositions
            ],
            "source_row_count": len(self.row_dispositions),
            "included_success_row_count": included_count,
            "excluded_failure_row_count": excluded_count,
            "source_failure_rows_retained_as_dispositions": True,
            "fit_validation_training_leakage_audit": (
                self.fit_validation_training_leakage_audit.to_dict()
            ),
            "blockers": list(self.blockers),
            "ready_for_fit": self.ready_for_fit,
            "selection_fields": ["status"],
            "validation_partition_loaded_for_leakage_only": True,
            "validation_labels_used_for_selection": False,
            "validation_labels_used_for_fit": False,
            "test_partition_present": False,
            "test_labels_present": False,
            "fit_performed": False,
            "model_selection_performed": False,
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
            raise PublicPoseRankingCalibrationTrainingViewError(
                "receipt output parent must already exist"
            )
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if (
            len(payload)
            > PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES
        ):
            raise PublicPoseRankingCalibrationTrainingViewError(
                "training-view receipt exceeds the frozen size bound"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(destination, flags, 0o600)
        except OSError as exc:
            raise PublicPoseRankingCalibrationTrainingViewError(
                "receipt output exists or cannot be created safely"
            ) from exc
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise PublicPoseRankingCalibrationTrainingViewError(
                        "receipt write did not make progress"
                    )
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def materialize_public_pose_ranking_calibration_training_view(
    *,
    partition_intake_receipt: (
        PublicPoseRankingCalibrationPartitionIntakeReceipt
    ),
    partition_intake_receipt_source_file_sha256: str,
    partition_intake_receipt_source_file_size_bytes: int,
    fit_partition: PoseRankingCalibrationPartition,
    validation_partition: PoseRankingCalibrationPartition,
) -> PublicPoseRankingCalibrationTrainingViewReceipt:
    """Derive the exact success-only fit view under the frozen status rule."""

    if not isinstance(
        partition_intake_receipt,
        PublicPoseRankingCalibrationPartitionIntakeReceipt,
    ):
        raise PublicPoseRankingCalibrationTrainingViewError(
            "partition-intake receipt has the wrong type"
        )
    if not partition_intake_receipt.passed:
        raise PublicPoseRankingCalibrationTrainingViewError(
            "training view requires a passing partition-intake receipt"
        )
    source_fit = partition_intake_receipt.fit_partition
    source_validation = partition_intake_receipt.validation_partition
    if (
        not isinstance(fit_partition, PoseRankingCalibrationPartition)
        or fit_partition.fingerprint_sha256 != source_fit.partition_sha256
        or fit_partition.identity_fingerprint_sha256
        != source_fit.partition_identity_sha256
        or len(fit_partition.rows) != source_fit.row_count
        or not isinstance(
            validation_partition,
            PoseRankingCalibrationPartition,
        )
        or validation_partition.fingerprint_sha256
        != source_validation.partition_sha256
        or validation_partition.identity_fingerprint_sha256
        != source_validation.partition_identity_sha256
        or len(validation_partition.rows) != source_validation.row_count
    ):
        raise PublicPoseRankingCalibrationTrainingViewError(
            "fit/validation partitions are not bound to the intake receipt"
        )
    # The view is derived before validation rows are used for any computation.
    training_rows = tuple(
        row for row in fit_partition.rows if row.status == "success"
    )
    dispositions = tuple(_disposition(row) for row in fit_partition.rows)
    try:
        training_partition = PoseRankingCalibrationPartition(
            dataset_id=fit_partition.dataset_id,
            dataset_version=fit_partition.dataset_version,
            split_role="fit",
            rows=training_rows,
        )
        leakage = audit_pose_ranking_leakage(
            training_partition,
            validation_partition,
            policy=_FROZEN_TRAINING_VIEW_LEAKAGE_POLICY,
        )
    except PoseRankingCalibrationError as exc:
        raise PublicPoseRankingCalibrationTrainingViewError(
            "training partition or leakage reconstruction failed"
        ) from exc
    blockers = tuple(
        f"fit_validation_{item}" for item in leakage.blockers
    )
    return PublicPoseRankingCalibrationTrainingViewReceipt(
        partition_intake_receipt_source_file_sha256=(
            partition_intake_receipt_source_file_sha256
        ),
        partition_intake_receipt_source_file_size_bytes=(
            partition_intake_receipt_source_file_size_bytes
        ),
        partition_intake_receipt_sha256=(
            partition_intake_receipt.receipt_sha256
        ),
        partition_intake_corpus_receipt_sha256=(
            partition_intake_receipt.corpus_receipt_sha256
        ),
        partition_intake_fit_validation_leakage_audit_sha256=(
            partition_intake_receipt.fit_validation_leakage_audit.fingerprint_sha256
        ),
        source_fit_partition=source_fit,
        validation_partition=source_validation,
        training_partition=training_partition,
        row_dispositions=dispositions,
        fit_validation_training_leakage_audit=leakage,
        blockers=blockers,
    )


def fit_public_pose_ranking_calibration_training_view(
    receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    config: PoseRankingCalibrationConfig,
) -> PoseRankingCalibrationModel:
    """Fit only the receipt-bound training view under an explicit config."""

    if not isinstance(
        receipt,
        PublicPoseRankingCalibrationTrainingViewReceipt,
    ):
        raise PublicPoseRankingCalibrationTrainingViewError(
            "training-view receipt has the wrong type"
        )
    if not receipt.ready_for_fit:
        raise PublicPoseRankingCalibrationTrainingViewError(
            "training-view receipt is not ready for fit"
        )
    if not isinstance(config, PoseRankingCalibrationConfig):
        raise PublicPoseRankingCalibrationTrainingViewError(
            "calibration config has the wrong type"
        )
    try:
        model = fit_pose_ranking_calibration(
            receipt.training_partition,
            receipt.fit_validation_training_leakage_audit,
            config,
        )
    except PoseRankingCalibrationError as exc:
        raise PublicPoseRankingCalibrationTrainingViewError(
            "receipt-bound calibration fit failed"
        ) from exc
    if (
        model.fit_partition_sha256
        != receipt.training_partition.fingerprint_sha256
        or model.evaluation_identity_sha256
        != receipt.validation_partition.partition_identity_sha256
        or model.leakage_audit_sha256
        != receipt.fit_validation_training_leakage_audit.fingerprint_sha256
    ):
        raise PublicPoseRankingCalibrationTrainingViewError(
            "fitted model is not bound to the training-view receipt"
        )
    return model


def _normalize_partition_intake_arguments(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(
        _PARTITION_INTAKE_MATERIALIZATION_ARGUMENT_KEYS
    ):
        raise PublicPoseRankingCalibrationTrainingViewError(
            "partition-intake materialization arguments are incomplete"
        )
    return dict(value)


def materialize_public_pose_ranking_calibration_training_view_from_files(
    *,
    partition_intake_receipt_path: str | os.PathLike[str],
    expected_partition_intake_receipt_file_sha256: str,
    expected_partition_intake_receipt_sha256: str,
    partition_intake_materialization_arguments: Mapping[str, Any],
) -> PublicPoseRankingCalibrationTrainingViewReceipt:
    """Reverify the full ancestry and derive one canonical training view."""

    arguments = _normalize_partition_intake_arguments(
        partition_intake_materialization_arguments
    )
    try:
        partition_intake = (
            verify_public_pose_ranking_calibration_partition_intake_receipt(
                partition_intake_receipt_path=(
                    partition_intake_receipt_path
                ),
                **arguments,
            )
        )
        fit_partition = load_public_pose_ranking_calibration_partition_file(
            arguments["fit_partition_path"],
            expected_file_sha256=arguments[
                "expected_fit_partition_file_sha256"
            ],
            expected_partition_sha256=arguments[
                "expected_fit_partition_sha256"
            ],
            split_role="fit",
        )
        validation_partition = (
            load_public_pose_ranking_calibration_partition_file(
                arguments["validation_partition_path"],
                expected_file_sha256=arguments[
                    "expected_validation_partition_file_sha256"
                ],
                expected_partition_sha256=arguments[
                    "expected_validation_partition_sha256"
                ],
                split_role="validation",
            )
        )
    except PublicPoseRankingCalibrationPartitionIntakeError as exc:
        raise PublicPoseRankingCalibrationTrainingViewError(
            "partition-intake ancestry verification failed"
        ) from exc
    expected_file = _digest(
        expected_partition_intake_receipt_file_sha256,
        name="expected partition-intake receipt file SHA-256",
    )
    expected_receipt = _digest(
        expected_partition_intake_receipt_sha256,
        name="expected partition-intake receipt SHA-256",
    )
    data, file_sha256 = _read_regular_file(
        partition_intake_receipt_path,
        name="calibration partition-intake receipt",
        maximum_bytes=(
            PUBLIC_POSE_RANKING_CALIBRATION_PARTITION_MAX_RECEIPT_BYTES
        ),
    )
    if file_sha256 != expected_file:
        raise PublicPoseRankingCalibrationTrainingViewError(
            "partition-intake receipt file SHA-256 mismatch"
        )
    if partition_intake.receipt_sha256 != expected_receipt:
        raise PublicPoseRankingCalibrationTrainingViewError(
            "partition-intake receipt SHA-256 mismatch"
        )
    return materialize_public_pose_ranking_calibration_training_view(
        partition_intake_receipt=partition_intake,
        partition_intake_receipt_source_file_sha256=file_sha256,
        partition_intake_receipt_source_file_size_bytes=len(data),
        fit_partition=fit_partition,
        validation_partition=validation_partition,
    )


def verify_public_pose_ranking_calibration_training_view_receipt(
    *,
    training_view_receipt_path: str | os.PathLike[str],
    **materialization_arguments: Any,
) -> PublicPoseRankingCalibrationTrainingViewReceipt:
    """Reconstruct and byte-compare one canonical training-view receipt."""

    expected = (
        materialize_public_pose_ranking_calibration_training_view_from_files(
            **materialization_arguments
        )
    )
    data, _ = _read_regular_file(
        training_view_receipt_path,
        name="calibration training-view receipt",
        maximum_bytes=(
            PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES
        ),
    )
    metadata = os.stat(
        training_view_receipt_path,
        follow_symlinks=False,
    )
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PublicPoseRankingCalibrationTrainingViewError(
            "calibration training-view receipt mode must be 0600"
        )
    if data != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PublicPoseRankingCalibrationTrainingViewError(
            "calibration training-view receipt differs from reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=(
            "betelgeuze-engine-v2-public-ranking-calibration-training-view"
        ),
        description=(
            "Derive an exact success-only PDBbind training view while "
            "retaining every excluded failure disposition."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--partition-intake-receipt", required=True)
        subparser.add_argument(
            "--expected-partition-intake-receipt-file-sha256",
            required=True,
        )
        subparser.add_argument(
            "--expected-partition-intake-receipt-sha256",
            required=True,
        )
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
            subparser.add_argument(f"--{role}-partition", required=True)
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
        "--training-view-receipt",
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


def _partition_intake_arguments(
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
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


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common: dict[str, Any] = {
        "partition_intake_receipt_path": args.partition_intake_receipt,
        "expected_partition_intake_receipt_file_sha256": (
            args.expected_partition_intake_receipt_file_sha256
        ),
        "expected_partition_intake_receipt_sha256": (
            args.expected_partition_intake_receipt_sha256
        ),
        "partition_intake_materialization_arguments": (
            _partition_intake_arguments(args)
        ),
    }
    if args.command == "materialize":
        receipt = (
            materialize_public_pose_ranking_calibration_training_view_from_files(
                **common
            )
        )
        receipt.write_json(args.output)
    else:
        receipt = (
            verify_public_pose_ranking_calibration_training_view_receipt(
                training_view_receipt_path=args.training_view_receipt,
                **common,
            )
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.receipt_sha256,
                "ready_for_fit": receipt.ready_for_fit,
                "source_row_count": len(receipt.row_dispositions),
                "included_success_row_count": len(
                    receipt.training_partition.rows
                ),
                "excluded_failure_row_count": (
                    receipt.source_fit_partition.failure_row_count
                ),
                "training_case_count": len(
                    receipt.training_partition.case_ids
                ),
                "blockers": list(receipt.blockers),
                "validation_labels_used_for_fit": False,
                "test_partition_present": False,
                "fit_performed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION",
    "PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_CONFIGURATION_SHA256",
    "PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES",
    "PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_TRAINING_ROW_DISPOSITION_SCHEMA_ID",
    "PublicPoseRankingCalibrationTrainingViewError",
    "PublicPoseRankingCalibrationTrainingViewReceipt",
    "PublicPoseRankingTrainingRowDisposition",
    "fit_public_pose_ranking_calibration_training_view",
    "materialize_public_pose_ranking_calibration_training_view",
    "materialize_public_pose_ranking_calibration_training_view_from_files",
    "verify_public_pose_ranking_calibration_training_view_receipt",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
