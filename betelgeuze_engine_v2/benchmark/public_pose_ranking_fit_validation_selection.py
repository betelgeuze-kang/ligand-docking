"""Fit-only PDBbind calibration and CASF validation model selection.

The workflow reverifies the public-corpus, partition-intake, and success-only
training-view ancestry before fitting every preregistered candidate. Candidate
models consume only the embedded PDBbind fit rows. CASF labels are used only
for failure-inclusive validation evaluation and deterministic model selection.
A PoseBusters test score partition is not accepted by this API.

The result remains claim-closed: it is a fit/validation workflow, not a test
benchmark, independent rerun, scientifically validated scorer, or product
promotion.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from importlib import import_module
import json
import math
import os
from pathlib import Path
import platform
import stat
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import torch

from ..docking.calibration import (
    MAX_BOOTSTRAP_SAMPLES,
    MAX_CALIBRATION_TERMS,
    MAX_TRAINING_PAIRS,
    PoseRankingCalibrationConfig,
    PoseRankingCalibrationError,
    PoseRankingCalibrationPartition,
    PoseRankingEvaluationConfig,
    evaluate_pose_ranking_calibration,
)
from .public_pose_ranking_calibration_partition_intake import (
    PublicPoseRankingCalibrationPartitionIntakeError,
    _canonical_bytes,
    _canonical_sha256,
    _decode_json_object,
    _read_regular_file,
    load_public_pose_ranking_calibration_partition_file,
)
from .public_pose_ranking_calibration_training_view import (
    PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES,
    PublicPoseRankingCalibrationTrainingViewError,
    PublicPoseRankingCalibrationTrainingViewReceipt,
    fit_public_pose_ranking_calibration_training_view,
    verify_public_pose_ranking_calibration_training_view_receipt,
)


PUBLIC_POSE_RANKING_FIT_VALIDATION_CANDIDATE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_fit_validation_candidate/1.0.0"
)
PUBLIC_POSE_RANKING_FIT_VALIDATION_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_fit_validation_manifest/1.0.0"
)
PUBLIC_POSE_RANKING_FIT_VALIDATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_fit_validation_receipt/1.0.0"
)
PUBLIC_POSE_RANKING_FIT_VALIDATION_ANCESTRY_ARGUMENTS_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_fit_validation_ancestry_"
    "arguments/1.0.0"
)
PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_CANDIDATES = 32
PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_MANIFEST_BYTES = 1024 * 1024
PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_ARGUMENTS_BYTES = 4 * 1024 * 1024
PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_RECEIPT_BYTES = 512 * 1024 * 1024

PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY: Mapping[str, object] = (
    MappingProxyType(
        {
            "primary_metric": "average_precision_pr_auc",
            "primary_direction": "maximize",
            "tie_breaker_metrics": (
                "top1_native_like_rate",
                "top5_native_like_rate",
            ),
            "final_tie_breaker": "candidate_id_ascending",
            "require_all_preregistered_candidates_complete": True,
            "require_primary_metric_available": True,
            "test_partition_access": "forbidden",
        }
    )
)
PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256 = (
    _canonical_sha256(
        dict(PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY)
    )
)

PUBLIC_POSE_RANKING_FIT_VALIDATION_SCIENTIFIC_BLOCKERS = (
    "validation_selection_is_not_posebusters_test_evaluation",
    "candidate_manifest_independent_preregistration_custody_is_not_established",
    "selected_model_is_not_independently_reproduced",
    "pose_ranking_confidence_calibration_is_not_fitted",
    "scientific_acceptance_thresholds_are_not_independently_reviewed",
    "supported_chemistry_applicability_is_not_validated",
    "public_docking_product_claim_is_not_authorized",
)


class PublicPoseRankingFitValidationSelectionError(ValueError):
    """A fit, validation, selection, identity, or receipt check failed closed."""


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _plain_json(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _text(
    value: object,
    *,
    name: str,
    maximum: int = 256,
) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} must be text"
        )
    result = value.strip()
    if (
        not result
        or len(result) > maximum
        or any(character in "\r\n\x00" for character in result)
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} is outside the frozen text bound"
        )
    return result


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} must be a lowercase SHA-256"
        )
    result = value.strip().lower()
    if len(result) != 64 or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} must be a lowercase SHA-256"
        )
    return result


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
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} must be an integer in [{minimum},{maximum}]"
        )
    return int(value)


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} must be a finite number"
        )
    result = float(value)
    if (
        not math.isfinite(result)
        or positive
        and result <= 0.0
        or nonnegative
        and result < 0.0
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} is outside its numeric bound"
        )
    return result


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} must be an object"
        )
    return {str(key): item for key, item in value.items()}


def _sequence(value: object, *, name: str) -> list[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
    ):
        raise PublicPoseRankingFitValidationSelectionError(
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
        raise PublicPoseRankingFitValidationSelectionError(
            f"{name} keys differ; "
            f"missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _calibration_config(value: object) -> PoseRankingCalibrationConfig:
    payload = _mapping(value, name="candidate calibration config")
    _exact_keys(
        payload,
        {
            "term_ids",
            "learning_rate",
            "l2_penalty",
            "iterations",
            "trace_interval",
            "max_training_pairs",
        },
        name="candidate calibration config",
    )
    terms = tuple(
        _text(item, name="candidate term ID")
        for item in _sequence(payload["term_ids"], name="candidate term IDs")
    )
    if not 1 <= len(terms) <= MAX_CALIBRATION_TERMS:
        raise PublicPoseRankingFitValidationSelectionError(
            "candidate term count is outside the calibration bound"
        )
    try:
        return PoseRankingCalibrationConfig(
            term_ids=terms,
            learning_rate=_finite(
                payload["learning_rate"],
                name="candidate learning_rate",
                positive=True,
            ),
            l2_penalty=_finite(
                payload["l2_penalty"],
                name="candidate l2_penalty",
                nonnegative=True,
            ),
            iterations=_integer(
                payload["iterations"],
                name="candidate iterations",
                minimum=1,
                maximum=100_000,
            ),
            trace_interval=_integer(
                payload["trace_interval"],
                name="candidate trace_interval",
                minimum=1,
                maximum=100_000,
            ),
            max_training_pairs=_integer(
                payload["max_training_pairs"],
                name="candidate max_training_pairs",
                minimum=1,
                maximum=MAX_TRAINING_PAIRS,
            ),
        )
    except PoseRankingCalibrationError as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "candidate calibration config is invalid"
        ) from exc


def _evaluation_config(value: object) -> PoseRankingEvaluationConfig:
    payload = _mapping(value, name="validation evaluation config")
    _exact_keys(
        payload,
        {"confidence_level", "bootstrap_samples", "seed"},
        name="validation evaluation config",
    )
    try:
        return PoseRankingEvaluationConfig(
            confidence_level=_finite(
                payload["confidence_level"],
                name="validation confidence_level",
                positive=True,
            ),
            bootstrap_samples=_integer(
                payload["bootstrap_samples"],
                name="validation bootstrap_samples",
                minimum=1,
                maximum=MAX_BOOTSTRAP_SAMPLES,
            ),
            seed=_integer(
                payload["seed"],
                name="validation seed",
                minimum=0,
                maximum=2**63 - 1,
            ),
        )
    except PoseRankingCalibrationError as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "validation evaluation config is invalid"
        ) from exc


@dataclass(frozen=True, slots=True)
class PublicPoseRankingFitValidationCandidate:
    candidate_id: str
    config: PoseRankingCalibrationConfig
    schema_id: str = PUBLIC_POSE_RANKING_FIT_VALIDATION_CANDIDATE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != (
            PUBLIC_POSE_RANKING_FIT_VALIDATION_CANDIDATE_SCHEMA_ID
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate schema is unsupported"
            )
        object.__setattr__(
            self,
            "candidate_id",
            _text(self.candidate_id, name="candidate_id", maximum=128),
        )
        if not isinstance(self.config, PoseRankingCalibrationConfig):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate config has the wrong type"
            )

    @property
    def candidate_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "candidate_id": self.candidate_id,
            "config": self.config.to_dict(),
            "config_sha256": self.config.fingerprint_sha256,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "candidate_sha256": self.candidate_sha256}

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> PublicPoseRankingFitValidationCandidate:
        payload = _mapping(value, name="candidate")
        _exact_keys(
            payload,
            {
                "schema_id",
                "candidate_id",
                "config",
                "config_sha256",
                "candidate_sha256",
            },
            name="candidate",
        )
        candidate = cls(
            schema_id=_text(payload["schema_id"], name="candidate schema"),
            candidate_id=_text(
                payload["candidate_id"],
                name="candidate_id",
                maximum=128,
            ),
            config=_calibration_config(payload["config"]),
        )
        if (
            _digest(
                payload["config_sha256"],
                name="candidate config SHA-256",
            )
            != candidate.config.fingerprint_sha256
            or _digest(
                payload["candidate_sha256"],
                name="candidate SHA-256",
            )
            != candidate.candidate_sha256
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate digest mismatch"
            )
        return candidate


@dataclass(frozen=True, slots=True)
class PublicPoseRankingFitValidationManifest:
    candidates: tuple[PublicPoseRankingFitValidationCandidate, ...]
    evaluation_config: PoseRankingEvaluationConfig
    selection_policy: Mapping[str, object] = (
        PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY
    )
    schema_id: str = PUBLIC_POSE_RANKING_FIT_VALIDATION_MANIFEST_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != (
            PUBLIC_POSE_RANKING_FIT_VALIDATION_MANIFEST_SCHEMA_ID
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "fit/validation manifest schema is unsupported"
            )
        candidates = tuple(self.candidates)
        if (
            not 1
            <= len(candidates)
            <= PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_CANDIDATES
            or any(
                not isinstance(
                    item,
                    PublicPoseRankingFitValidationCandidate,
                )
                for item in candidates
            )
            or tuple(item.candidate_id for item in candidates)
            != tuple(sorted(item.candidate_id for item in candidates))
            or len({item.candidate_id for item in candidates})
            != len(candidates)
            or len({item.candidate_sha256 for item in candidates})
            != len(candidates)
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidates must be unique and canonically ordered"
            )
        if not isinstance(
            self.evaluation_config,
            PoseRankingEvaluationConfig,
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "evaluation config has the wrong type"
            )
        policy = _plain_json(self.selection_policy)
        frozen = _plain_json(
            PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY
        )
        if policy != frozen:
            raise PublicPoseRankingFitValidationSelectionError(
                "selection policy differs from the frozen policy"
            )
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(
            self,
            "selection_policy",
            PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY,
        )

    @property
    def manifest_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "selection_policy": _plain_json(self.selection_policy),
            "evaluation_config": self.evaluation_config.to_dict(),
            "candidates": [item.to_dict() for item in self.candidates],
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "manifest_sha256": self.manifest_sha256}

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> PublicPoseRankingFitValidationManifest:
        payload = _mapping(value, name="fit/validation manifest")
        _exact_keys(
            payload,
            {
                "schema_id",
                "selection_policy",
                "evaluation_config",
                "candidates",
                "manifest_sha256",
            },
            name="fit/validation manifest",
        )
        candidates = tuple(
            PublicPoseRankingFitValidationCandidate.from_dict(item)
            for item in _sequence(
                payload["candidates"],
                name="fit/validation candidates",
            )
        )
        manifest = cls(
            schema_id=_text(
                payload["schema_id"],
                name="fit/validation manifest schema",
            ),
            selection_policy=_mapping(
                payload["selection_policy"],
                name="selection policy",
            ),
            evaluation_config=_evaluation_config(
                payload["evaluation_config"]
            ),
            candidates=candidates,
        )
        if _digest(
            payload["manifest_sha256"],
            name="fit/validation manifest SHA-256",
        ) != manifest.manifest_sha256:
            raise PublicPoseRankingFitValidationSelectionError(
                "fit/validation manifest digest mismatch"
            )
        return manifest


def load_public_pose_ranking_fit_validation_manifest(
    path: str | os.PathLike[str],
    *,
    expected_file_sha256: str,
    expected_manifest_sha256: str,
) -> tuple[PublicPoseRankingFitValidationManifest, str, int]:
    """Load one canonical preregistered candidate manifest."""

    data, file_sha256 = _read_regular_file(
        path,
        name="fit/validation candidate manifest",
        maximum_bytes=PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_MANIFEST_BYTES,
    )
    if file_sha256 != _digest(
        expected_file_sha256,
        name="expected candidate manifest file SHA-256",
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "candidate manifest file SHA-256 mismatch"
        )
    try:
        decoded = _decode_json_object(
            data,
            name="fit/validation candidate manifest",
        )
    except PublicPoseRankingCalibrationPartitionIntakeError as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "candidate manifest is not valid canonical JSON"
        ) from exc
    manifest = PublicPoseRankingFitValidationManifest.from_dict(decoded)
    if data != _canonical_bytes(manifest.to_dict()) + b"\n":
        raise PublicPoseRankingFitValidationSelectionError(
            "candidate manifest must use canonical JSON plus one newline"
        )
    if manifest.manifest_sha256 != _digest(
        expected_manifest_sha256,
        name="expected candidate manifest SHA-256",
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "candidate manifest SHA-256 mismatch"
        )
    return manifest, file_sha256, len(data)


def _hash_regular_file(
    path: Path,
    *,
    maximum_bytes: int = 512 * 1024**2,
) -> dict[str, object]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "source or dependency identity file is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_size < 0
        or metadata.st_size > maximum_bytes
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "source or dependency identity requires a bounded regular file"
        )
    digest = hashlib.sha256()
    observed = 0
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024**2)
            if not block:
                break
            observed += len(block)
            if observed > maximum_bytes:
                raise PublicPoseRankingFitValidationSelectionError(
                    "source or dependency identity exceeded its bound"
                )
            digest.update(block)
    if observed != metadata.st_size:
        raise PublicPoseRankingFitValidationSelectionError(
            "source or dependency identity changed while hashing"
        )
    return {"sha256": digest.hexdigest(), "size_bytes": observed}


def _source_identity() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    relative_paths = (
        "betelgeuze_engine_v2/benchmark/"
        "public_pose_ranking_fit_validation_selection.py",
        "betelgeuze_engine_v2/benchmark/"
        "public_pose_ranking_calibration_training_view.py",
        "betelgeuze_engine_v2/benchmark/"
        "public_pose_ranking_calibration_partition_intake.py",
        "betelgeuze_engine_v2/docking/calibration.py",
    )
    rows = [
        {"path": relative, **_hash_regular_file(root / relative)}
        for relative in relative_paths
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


def _runtime_identity() -> dict[str, object]:
    torch_wrapper = Path(torch.__file__).resolve(strict=True)
    torch_native = Path(
        import_module("torch._C").__file__
    ).resolve(strict=True)
    projection = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "torch_version": str(torch.__version__),
        "torch_wrapper": _hash_regular_file(torch_wrapper),
        "torch_native_extension": _hash_regular_file(torch_native),
        "torch_configuration_sha256": hashlib.sha256(
            torch.__config__.show().encode("utf-8")
        ).hexdigest(),
        "device": "cpu",
        "dtype": "float64",
        "torch_num_threads": int(torch.get_num_threads()),
        "torch_num_interop_threads": int(torch.get_num_interop_threads()),
        "path_values_disclosed": False,
    }
    return {
        **projection,
        "runtime_identity_sha256": _canonical_sha256(projection),
    }


def _selection_metrics(report: object) -> dict[str, object]:
    pose_metrics = getattr(report, "overall_pose_metrics", ())
    case_metrics = getattr(report, "overall_metrics", ())
    if len(pose_metrics) != 1:
        raise PublicPoseRankingFitValidationSelectionError(
            "validation report does not contain one pose metric"
        )
    by_id = {
        str(metric.metric_id): metric
        for metric in case_metrics
    }
    required = {
        "top1_native_like_rate",
        "top5_native_like_rate",
        "scored_case_coverage",
    }
    if set(by_id) != required:
        raise PublicPoseRankingFitValidationSelectionError(
            "validation report case metrics are incomplete"
        )
    pose = pose_metrics[0]
    return {
        "average_precision_pr_auc": pose.value,
        "average_precision_pr_auc_confidence_interval_low": (
            pose.confidence_interval_low
        ),
        "average_precision_pr_auc_confidence_interval_high": (
            pose.confidence_interval_high
        ),
        "top1_native_like_rate": by_id[
            "top1_native_like_rate"
        ].value,
        "top5_native_like_rate": by_id[
            "top5_native_like_rate"
        ].value,
        "scored_case_coverage": by_id[
            "scored_case_coverage"
        ].value,
        "all_case_denominator": int(report.all_case_denominator),
        "all_pose_denominator": int(report.all_pose_denominator),
        "successful_labeled_pose_count": (
            pose.successful_labeled_pose_count
        ),
        "failed_pose_count": pose.failed_pose_count,
        "primary_metric_available": pose.available,
        "primary_metric_blockers": list(pose.blockers),
    }


def _candidate_result(
    *,
    training_view: PublicPoseRankingCalibrationTrainingViewReceipt,
    validation_partition: PoseRankingCalibrationPartition,
    candidate: PublicPoseRankingFitValidationCandidate,
    evaluation_config: PoseRankingEvaluationConfig,
) -> dict[str, object]:
    model = None
    report = None
    status = "fit_failed"
    failure_code = ""
    try:
        model = fit_public_pose_ranking_calibration_training_view(
            training_view,
            candidate.config,
        )
    except (
        PublicPoseRankingCalibrationTrainingViewError,
        PoseRankingCalibrationError,
        RuntimeError,
    ):
        failure_code = "receipt_bound_fit_failed"
    if model is not None:
        status = "evaluation_failed"
        try:
            report = evaluate_pose_ranking_calibration(
                model,
                validation_partition,
                training_view.fit_validation_training_leakage_audit,
                config=evaluation_config,
            )
        except (PoseRankingCalibrationError, RuntimeError):
            failure_code = "casf_validation_evaluation_failed"
    metrics = None
    if report is not None:
        metrics = _selection_metrics(report)
        if metrics["primary_metric_available"] is True:
            status = "completed"
            failure_code = ""
        else:
            status = "primary_metric_unavailable"
            failure_code = "validation_average_precision_pr_auc_unavailable"
    projection = {
        "candidate_id": candidate.candidate_id,
        "candidate_manifest_entry_sha256": candidate.candidate_sha256,
        "config": candidate.config.to_dict(),
        "config_sha256": candidate.config.fingerprint_sha256,
        "status": status,
        "failure_code": failure_code,
        "model": model.to_dict() if model is not None else None,
        "model_sha256": (
            model.fingerprint_sha256 if model is not None else None
        ),
        "validation_report": (
            report.to_dict() if report is not None else None
        ),
        "validation_report_sha256": (
            report.fingerprint_sha256 if report is not None else None
        ),
        "selection_metrics": metrics,
        "validation_labels_used_for_fit": False,
        "validation_labels_evaluated": report is not None,
        "test_partition_loaded": False,
    }
    return {
        **projection,
        "candidate_result_sha256": _canonical_sha256(projection),
    }


def _selected_row(
    rows: Sequence[Mapping[str, object]],
) -> Mapping[str, object] | None:
    if not rows or any(row.get("status") != "completed" for row in rows):
        return None

    def key(row: Mapping[str, object]) -> tuple[float, float, float, str]:
        metrics = _mapping(
            row.get("selection_metrics"),
            name="candidate selection metrics",
        )
        return (
            -_finite(
                metrics["average_precision_pr_auc"],
                name="candidate validation PR-AUC",
                nonnegative=True,
            ),
            -_finite(
                metrics["top1_native_like_rate"],
                name="candidate validation Top-1",
                nonnegative=True,
            ),
            -_finite(
                metrics["top5_native_like_rate"],
                name="candidate validation Top-5",
                nonnegative=True,
            ),
            _text(
                row.get("candidate_id"),
                name="candidate result ID",
                maximum=128,
            ),
        )

    return sorted(rows, key=key)[0]


def materialize_public_pose_ranking_fit_validation_selection(
    *,
    training_view_receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    training_view_receipt_source_file_sha256: str,
    training_view_receipt_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    manifest: PublicPoseRankingFitValidationManifest,
    manifest_source_file_sha256: str,
    manifest_source_file_size_bytes: int,
) -> dict[str, object]:
    """Fit all preregistered candidates and select only on bound CASF labels."""

    if not isinstance(
        training_view_receipt,
        PublicPoseRankingCalibrationTrainingViewReceipt,
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "training-view receipt has the wrong type"
        )
    if not training_view_receipt.ready_for_fit:
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation selection requires a ready training view"
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
        raise PublicPoseRankingFitValidationSelectionError(
            "CASF validation partition is not bound to the training view"
        )
    if not isinstance(manifest, PublicPoseRankingFitValidationManifest):
        raise PublicPoseRankingFitValidationSelectionError(
            "candidate manifest has the wrong type"
        )
    if any(
        candidate.config.term_ids
        != training_view_receipt.training_partition.term_ids
        for candidate in manifest.candidates
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "candidate term order differs from the training partition"
        )
    training_file_sha256 = _digest(
        training_view_receipt_source_file_sha256,
        name="training-view receipt source file SHA-256",
    )
    manifest_file_sha256 = _digest(
        manifest_source_file_sha256,
        name="candidate manifest source file SHA-256",
    )
    training_file_size = _integer(
        training_view_receipt_source_file_size_bytes,
        name="training-view receipt source file size",
        minimum=1,
        maximum=(
            PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES
        ),
    )
    manifest_file_size = _integer(
        manifest_source_file_size_bytes,
        name="candidate manifest source file size",
        minimum=1,
        maximum=PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_MANIFEST_BYTES,
    )
    rows = tuple(
        _candidate_result(
            training_view=training_view_receipt,
            validation_partition=validation_partition,
            candidate=candidate,
            evaluation_config=manifest.evaluation_config,
        )
        for candidate in manifest.candidates
    )
    selected = _selected_row(rows)
    selection_complete = selected is not None
    selection_blockers = (
        ()
        if selection_complete
        else ("preregistered_candidate_or_primary_metric_incomplete",)
    )
    source_identity = _source_identity()
    runtime_identity = _runtime_identity()
    projection = {
        "schema_id": PUBLIC_POSE_RANKING_FIT_VALIDATION_RECEIPT_SCHEMA_ID,
        "training_view_receipt_source_file_sha256": training_file_sha256,
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
        "validation_partition_sha256": (
            validation_partition.fingerprint_sha256
        ),
        "validation_partition_identity_sha256": (
            validation_partition.identity_fingerprint_sha256
        ),
        "fit_validation_leakage_audit_sha256": (
            training_view_receipt.fit_validation_training_leakage_audit.fingerprint_sha256
        ),
        "candidate_manifest_source_file_sha256": manifest_file_sha256,
        "candidate_manifest_source_file_size_bytes": manifest_file_size,
        "candidate_manifest": manifest.to_dict(),
        "candidate_manifest_sha256": manifest.manifest_sha256,
        "selection_policy": _plain_json(
            PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY
        ),
        "selection_policy_sha256": (
            PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256
        ),
        "source_identity": source_identity,
        "runtime_identity": runtime_identity,
        "candidate_results": list(rows),
        "candidate_count": len(rows),
        "completed_candidate_count": sum(
            row["status"] == "completed" for row in rows
        ),
        "failed_or_unavailable_candidate_count": sum(
            row["status"] != "completed" for row in rows
        ),
        "selection_complete": selection_complete,
        "selection_blockers": list(selection_blockers),
        "selected_candidate_id": (
            selected["candidate_id"] if selected is not None else None
        ),
        "selected_model_sha256": (
            selected["model_sha256"] if selected is not None else None
        ),
        "selected_validation_report_sha256": (
            selected["validation_report_sha256"]
            if selected is not None
            else None
        ),
        "fit_rows_used": len(
            training_view_receipt.training_partition.rows
        ),
        "validation_rows_evaluated": (
            len(validation_partition.rows)
            if any(
                row["validation_report"] is not None for row in rows
            )
            else 0
        ),
        "validation_labels_used_for_fit": False,
        "validation_labels_used_for_selection": selection_complete,
        "posebusters_test_score_partition_loaded": False,
        "posebusters_test_labels_used": False,
        "posebusters_test_benchmark_executed": False,
        "selected_model_is_fit_validation_only": True,
        "independent_external_rerun_complete": False,
        "independent_scientific_review_complete": False,
        "scientifically_validated": False,
        "production_eligible": False,
        "claim_safe": False,
        "scientific_blockers": list(
            PUBLIC_POSE_RANKING_FIT_VALIDATION_SCIENTIFIC_BLOCKERS
        ),
    }
    return {
        **projection,
        "receipt_sha256": _canonical_sha256(projection),
    }


def _validate_file_identity(
    value: object,
    *,
    name: str,
) -> dict[str, object]:
    payload = _mapping(value, name=name)
    _exact_keys(payload, {"sha256", "size_bytes"}, name=name)
    payload["sha256"] = _digest(
        payload["sha256"],
        name=f"{name} SHA-256",
    )
    payload["size_bytes"] = _integer(
        payload["size_bytes"],
        name=f"{name} size",
        minimum=1,
        maximum=512 * 1024**2,
    )
    return payload


def _validate_source_identity(value: object) -> dict[str, object]:
    payload = _mapping(value, name="source identity")
    _exact_keys(
        payload,
        {
            "source_files",
            "source_manifest_sha256",
            "absolute_paths_disclosed",
            "source_identity_sha256",
        },
        name="source identity",
    )
    rows: list[dict[str, object]] = []
    for index, item in enumerate(
        _sequence(payload["source_files"], name="source identity files")
    ):
        row = _mapping(item, name=f"source identity file {index}")
        _exact_keys(
            row,
            {"path", "sha256", "size_bytes"},
            name=f"source identity file {index}",
        )
        path = _text(
            row["path"],
            name=f"source identity file {index} path",
            maximum=512,
        )
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise PublicPoseRankingFitValidationSelectionError(
                "source identity path must remain repository-relative"
            )
        identity = _validate_file_identity(
            {
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
            },
            name=f"source identity file {index}",
        )
        rows.append({"path": path, **identity})
    if (
        not rows
        or len({str(row["path"]) for row in rows}) != len(rows)
        or payload["absolute_paths_disclosed"] is not False
        or _digest(
            payload["source_manifest_sha256"],
            name="source manifest SHA-256",
        )
        != _canonical_sha256(rows)
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "source identity rows or disclosure policy are invalid"
        )
    projection = {
        "source_files": rows,
        "source_manifest_sha256": payload["source_manifest_sha256"],
        "absolute_paths_disclosed": False,
    }
    if _digest(
        payload["source_identity_sha256"],
        name="source identity SHA-256",
    ) != _canonical_sha256(projection):
        raise PublicPoseRankingFitValidationSelectionError(
            "source identity digest mismatch"
        )
    return {**projection, "source_identity_sha256": payload[
        "source_identity_sha256"
    ]}


def _validate_runtime_identity(value: object) -> dict[str, object]:
    payload = _mapping(value, name="runtime identity")
    expected = {
        "python_implementation",
        "python_version",
        "torch_version",
        "torch_wrapper",
        "torch_native_extension",
        "torch_configuration_sha256",
        "device",
        "dtype",
        "torch_num_threads",
        "torch_num_interop_threads",
        "path_values_disclosed",
        "runtime_identity_sha256",
    }
    _exact_keys(payload, expected, name="runtime identity")
    projection = {
        "python_implementation": _text(
            payload["python_implementation"],
            name="Python implementation",
        ),
        "python_version": _text(
            payload["python_version"],
            name="Python version",
        ),
        "torch_version": _text(
            payload["torch_version"],
            name="Torch version",
        ),
        "torch_wrapper": _validate_file_identity(
            payload["torch_wrapper"],
            name="Torch wrapper",
        ),
        "torch_native_extension": _validate_file_identity(
            payload["torch_native_extension"],
            name="Torch native extension",
        ),
        "torch_configuration_sha256": _digest(
            payload["torch_configuration_sha256"],
            name="Torch configuration SHA-256",
        ),
        "device": payload["device"],
        "dtype": payload["dtype"],
        "torch_num_threads": _integer(
            payload["torch_num_threads"],
            name="Torch thread count",
            minimum=1,
            maximum=1_000_000,
        ),
        "torch_num_interop_threads": _integer(
            payload["torch_num_interop_threads"],
            name="Torch interop thread count",
            minimum=1,
            maximum=1_000_000,
        ),
        "path_values_disclosed": payload["path_values_disclosed"],
    }
    if (
        projection["device"] != "cpu"
        or projection["dtype"] != "float64"
        or projection["path_values_disclosed"] is not False
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "runtime identity execution or disclosure policy drifted"
        )
    if _digest(
        payload["runtime_identity_sha256"],
        name="runtime identity SHA-256",
    ) != _canonical_sha256(projection):
        raise PublicPoseRankingFitValidationSelectionError(
            "runtime identity digest mismatch"
        )
    return {
        **projection,
        "runtime_identity_sha256": payload["runtime_identity_sha256"],
    }


def _selection_metrics_from_report_payload(
    value: object,
) -> dict[str, object]:
    report = _mapping(value, name="validation report")
    pose_metrics = _sequence(
        report.get("overall_pose_metrics"),
        name="validation report pose metrics",
    )
    case_metrics = _sequence(
        report.get("overall_metrics"),
        name="validation report case metrics",
    )
    if len(pose_metrics) != 1:
        raise PublicPoseRankingFitValidationSelectionError(
            "validation report does not retain one pose metric"
        )
    pose = _mapping(
        pose_metrics[0],
        name="validation report pose metric",
    )
    by_id = {
        _text(
            _mapping(item, name="validation report case metric").get(
                "metric_id"
            ),
            name="validation report case metric ID",
        ): _mapping(item, name="validation report case metric")
        for item in case_metrics
    }
    required = {
        "top1_native_like_rate",
        "top5_native_like_rate",
        "scored_case_coverage",
    }
    if set(by_id) != required:
        raise PublicPoseRankingFitValidationSelectionError(
            "validation report case metrics are incomplete"
        )
    blockers = _sequence(
        pose.get("blockers"),
        name="validation pose metric blockers",
    )
    return {
        "average_precision_pr_auc": pose.get("value"),
        "average_precision_pr_auc_confidence_interval_low": pose.get(
            "confidence_interval_low"
        ),
        "average_precision_pr_auc_confidence_interval_high": pose.get(
            "confidence_interval_high"
        ),
        "top1_native_like_rate": by_id[
            "top1_native_like_rate"
        ].get("value"),
        "top5_native_like_rate": by_id[
            "top5_native_like_rate"
        ].get("value"),
        "scored_case_coverage": by_id[
            "scored_case_coverage"
        ].get("value"),
        "all_case_denominator": report.get("all_case_denominator"),
        "all_pose_denominator": report.get("all_pose_denominator"),
        "successful_labeled_pose_count": pose.get(
            "successful_labeled_pose_count"
        ),
        "failed_pose_count": pose.get("failed_pose_count"),
        "primary_metric_available": pose.get("available"),
        "primary_metric_blockers": blockers,
    }


def _validate_receipt_digest(value: object) -> dict[str, object]:
    receipt = _mapping(value, name="fit/validation receipt")
    expected = {
        "schema_id",
        "training_view_receipt_source_file_sha256",
        "training_view_receipt_source_file_size_bytes",
        "training_view_receipt_sha256",
        "training_partition_sha256",
        "training_partition_identity_sha256",
        "validation_partition_sha256",
        "validation_partition_identity_sha256",
        "fit_validation_leakage_audit_sha256",
        "candidate_manifest_source_file_sha256",
        "candidate_manifest_source_file_size_bytes",
        "candidate_manifest",
        "candidate_manifest_sha256",
        "selection_policy",
        "selection_policy_sha256",
        "source_identity",
        "runtime_identity",
        "candidate_results",
        "candidate_count",
        "completed_candidate_count",
        "failed_or_unavailable_candidate_count",
        "selection_complete",
        "selection_blockers",
        "selected_candidate_id",
        "selected_model_sha256",
        "selected_validation_report_sha256",
        "fit_rows_used",
        "validation_rows_evaluated",
        "validation_labels_used_for_fit",
        "validation_labels_used_for_selection",
        "posebusters_test_score_partition_loaded",
        "posebusters_test_labels_used",
        "posebusters_test_benchmark_executed",
        "selected_model_is_fit_validation_only",
        "independent_external_rerun_complete",
        "independent_scientific_review_complete",
        "scientifically_validated",
        "production_eligible",
        "claim_safe",
        "scientific_blockers",
        "receipt_sha256",
    }
    _exact_keys(receipt, expected, name="fit/validation receipt")
    digest = _digest(
        receipt["receipt_sha256"],
        name="fit/validation receipt SHA-256",
    )
    projection = {
        key: item
        for key, item in receipt.items()
        if key != "receipt_sha256"
    }
    if digest != _canonical_sha256(projection):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt digest mismatch"
        )
    if (
        receipt["schema_id"]
        != PUBLIC_POSE_RANKING_FIT_VALIDATION_RECEIPT_SCHEMA_ID
        or receipt["validation_labels_used_for_fit"] is not False
        or receipt["posebusters_test_score_partition_loaded"] is not False
        or receipt["posebusters_test_labels_used"] is not False
        or receipt["posebusters_test_benchmark_executed"] is not False
        or receipt["scientifically_validated"] is not False
        or receipt["production_eligible"] is not False
        or receipt["claim_safe"] is not False
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt overstates its data use or claim"
        )
    manifest = PublicPoseRankingFitValidationManifest.from_dict(
        receipt["candidate_manifest"]
    )
    if (
        manifest.manifest_sha256
        != receipt["candidate_manifest_sha256"]
        or _plain_json(receipt["selection_policy"])
        != _plain_json(
            PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY
        )
        or receipt["selection_policy_sha256"]
        != PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt manifest or policy mismatch"
        )
    digest_fields = (
        "training_view_receipt_source_file_sha256",
        "training_view_receipt_sha256",
        "training_partition_sha256",
        "training_partition_identity_sha256",
        "validation_partition_sha256",
        "validation_partition_identity_sha256",
        "fit_validation_leakage_audit_sha256",
        "candidate_manifest_source_file_sha256",
        "candidate_manifest_sha256",
        "selection_policy_sha256",
    )
    if any(
        _digest(receipt[name], name=name) != receipt[name]
        for name in digest_fields
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt contains a noncanonical digest"
        )
    _integer(
        receipt["training_view_receipt_source_file_size_bytes"],
        name="training-view receipt source file size",
        minimum=1,
        maximum=(
            PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES
        ),
    )
    _integer(
        receipt["candidate_manifest_source_file_size_bytes"],
        name="candidate manifest source file size",
        minimum=1,
        maximum=PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_MANIFEST_BYTES,
    )
    _validate_source_identity(receipt["source_identity"])
    _validate_runtime_identity(receipt["runtime_identity"])

    row_values = _sequence(
        receipt["candidate_results"],
        name="candidate results",
    )
    candidate_count = _integer(
        receipt["candidate_count"],
        name="candidate count",
        minimum=1,
        maximum=PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_CANDIDATES,
    )
    completed_count = _integer(
        receipt["completed_candidate_count"],
        name="completed candidate count",
        minimum=0,
        maximum=candidate_count,
    )
    failed_count = _integer(
        receipt["failed_or_unavailable_candidate_count"],
        name="failed candidate count",
        minimum=0,
        maximum=candidate_count,
    )
    if (
        len(row_values) != candidate_count
        or candidate_count != len(manifest.candidates)
        or completed_count + failed_count != candidate_count
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt candidate counts do not reconcile"
        )
    row_expected = {
        "candidate_id",
        "candidate_manifest_entry_sha256",
        "config",
        "config_sha256",
        "status",
        "failure_code",
        "model",
        "model_sha256",
        "validation_report",
        "validation_report_sha256",
        "selection_metrics",
        "validation_labels_used_for_fit",
        "validation_labels_evaluated",
        "test_partition_loaded",
        "candidate_result_sha256",
    }
    rows: list[dict[str, object]] = []
    report_pose_counts: set[int] = set()
    for index, (row, candidate) in enumerate(
        zip(row_values, manifest.candidates, strict=True)
    ):
        original = _mapping(row, name=f"candidate result {index}")
        _exact_keys(
            original,
            row_expected,
            name=f"candidate result {index}",
        )
        payload = dict(original)
        row_digest = _digest(
            payload.pop("candidate_result_sha256", None),
            name="candidate result SHA-256",
        )
        if row_digest != _canonical_sha256(payload):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate result digest mismatch"
            )
        if (
            payload["candidate_id"] != candidate.candidate_id
            or payload["candidate_manifest_entry_sha256"]
            != candidate.candidate_sha256
            or payload["config"] != candidate.config.to_dict()
            or payload["config_sha256"]
            != candidate.config.fingerprint_sha256
            or payload["validation_labels_used_for_fit"] is not False
            or payload["test_partition_loaded"] is not False
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate result does not match its preregistered entry"
            )
        status_value = payload["status"]
        if status_value not in {
            "fit_failed",
            "evaluation_failed",
            "primary_metric_unavailable",
            "completed",
        }:
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate result status is unsupported"
            )
        failure_code = payload["failure_code"]
        if (
            not isinstance(failure_code, str)
            or len(failure_code) > 128
            or any(character in "\r\n\x00" for character in failure_code)
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate failure code is invalid"
            )
        model = payload["model"]
        report = payload["validation_report"]
        metrics = payload["selection_metrics"]
        model_sha256 = payload["model_sha256"]
        report_sha256 = payload["validation_report_sha256"]
        expected_failure_code = {
            "fit_failed": "receipt_bound_fit_failed",
            "evaluation_failed": "casf_validation_evaluation_failed",
            "primary_metric_unavailable": (
                "validation_average_precision_pr_auc_unavailable"
            ),
            "completed": "",
        }[str(status_value)]
        if failure_code != expected_failure_code:
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate status and failure disposition disagree"
            )
        if status_value == "fit_failed":
            if (
                model is not None
                or model_sha256 is not None
                or report is not None
                or report_sha256 is not None
                or metrics is not None
                or payload["validation_labels_evaluated"] is not False
            ):
                raise PublicPoseRankingFitValidationSelectionError(
                    "fit-failed candidate retains impossible downstream data"
                )
            rows.append(original)
            continue

        model_payload = _mapping(model, name="candidate model")
        model_digest = _digest(
            model_sha256,
            name="candidate model SHA-256",
        )
        if (
            model_digest != _canonical_sha256(model_payload)
            or model_payload.get("config_sha256")
            != candidate.config.fingerprint_sha256
            or model_payload.get("term_ids")
            != list(candidate.config.term_ids)
            or model_payload.get("fit_partition_sha256")
            != receipt["training_partition_sha256"]
            or model_payload.get("evaluation_identity_sha256")
            != receipt["validation_partition_identity_sha256"]
            or model_payload.get("leakage_audit_sha256")
            != receipt["fit_validation_leakage_audit_sha256"]
            or model_payload.get("fit_complete") is not True
            or model_payload.get("holdout_validated") is not False
            or model_payload.get("scientifically_validated") is not False
            or model_payload.get("claim_safe") is not False
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate model identity or claim boundary is invalid"
            )
        if status_value == "evaluation_failed":
            if (
                report is not None
                or report_sha256 is not None
                or metrics is not None
                or payload["validation_labels_evaluated"] is not False
            ):
                raise PublicPoseRankingFitValidationSelectionError(
                    "evaluation-failed candidate retains impossible report data"
                )
            rows.append(original)
            continue

        report_payload = _mapping(
            report,
            name="candidate validation report",
        )
        report_digest = _digest(
            report_sha256,
            name="candidate validation report SHA-256",
        )
        report_cases = [
            _mapping(item, name="validation report case")
            for item in _sequence(
                report_payload.get("cases"),
                name="validation report cases",
            )
        ]
        family_metrics = _sequence(
            report_payload.get("family_metrics"),
            name="validation report family metrics",
        )
        report_all_cases = _integer(
            report_payload.get("all_case_denominator"),
            name="validation all-case denominator",
            minimum=1,
            maximum=10_000_000,
        )
        report_all_poses = _integer(
            report_payload.get("all_pose_denominator"),
            name="validation all-pose denominator",
            minimum=1,
            maximum=100_000_000,
        )
        if (
            report_digest != _canonical_sha256(report_payload)
            or report_payload.get("model_sha256") != model_digest
            or report_payload.get("evaluation_partition_sha256")
            != receipt["validation_partition_sha256"]
            or report_payload.get("leakage_audit_sha256")
            != receipt["fit_validation_leakage_audit_sha256"]
            or report_payload.get("config")
            != manifest.evaluation_config.to_dict()
            or report_payload.get("claim_safe") is not False
            or len(report_cases) != report_all_cases
            or not family_metrics
            or sum(
                _integer(
                    case.get("total_pose_count"),
                    name="validation case pose count",
                    minimum=1,
                    maximum=10_000_000,
                )
                for case in report_cases
            )
            != report_all_poses
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate validation report identity or denominator is invalid"
            )
        expected_metrics = _selection_metrics_from_report_payload(
            report_payload
        )
        if (
            metrics != expected_metrics
            or payload["validation_labels_evaluated"] is not True
            or expected_metrics["primary_metric_available"]
            is not (
                expected_metrics["average_precision_pr_auc"] is not None
            )
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate selection metrics do not match the validation report"
            )
        metric_payload = _mapping(
            metrics,
            name="candidate selection metrics",
        )
        if (
            metric_payload["all_case_denominator"] != report_all_cases
            or metric_payload["all_pose_denominator"] != report_all_poses
            or metric_payload["failed_pose_count"]
            != sum(
                _integer(
                    case.get("failed_pose_count"),
                    name="validation case failure count",
                    minimum=0,
                    maximum=10_000_000,
                )
                for case in report_cases
            )
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate selection-metric denominators are invalid"
            )
        if (
            status_value == "completed"
            and metric_payload["primary_metric_available"] is not True
            or status_value == "primary_metric_unavailable"
            and metric_payload["primary_metric_available"] is not False
        ):
            raise PublicPoseRankingFitValidationSelectionError(
                "candidate status and primary metric availability disagree"
            )
        report_pose_counts.add(report_all_poses)
        rows.append(original)

    if (
        sum(row["status"] == "completed" for row in rows)
        != completed_count
        or sum(row["status"] != "completed" for row in rows)
        != failed_count
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt candidate status counts do not reconcile"
        )
    selected = _selected_row(rows)
    selection_complete = selected is not None
    expected_blockers = (
        []
        if selection_complete
        else ["preregistered_candidate_or_primary_metric_incomplete"]
    )
    if (
        receipt["selection_complete"] is not selection_complete
        or receipt["selection_blockers"] != expected_blockers
        or receipt["selected_candidate_id"]
        != (selected["candidate_id"] if selected is not None else None)
        or receipt["selected_model_sha256"]
        != (selected["model_sha256"] if selected is not None else None)
        or receipt["selected_validation_report_sha256"]
        != (
            selected["validation_report_sha256"]
            if selected is not None
            else None
        )
        or receipt["validation_labels_used_for_selection"]
        is not selection_complete
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt selection summary is inconsistent"
        )
    fit_rows_used = _integer(
        receipt["fit_rows_used"],
        name="fit rows used",
        minimum=1,
        maximum=100_000_000,
    )
    validation_rows_evaluated = _integer(
        receipt["validation_rows_evaluated"],
        name="validation rows evaluated",
        minimum=0,
        maximum=100_000_000,
    )
    if (
        fit_rows_used < 1
        or len(report_pose_counts) > 1
        or validation_rows_evaluated
        != (next(iter(report_pose_counts)) if report_pose_counts else 0)
        or receipt["selected_model_is_fit_validation_only"] is not True
        or receipt["independent_external_rerun_complete"] is not False
        or receipt["independent_scientific_review_complete"] is not False
        or receipt["scientific_blockers"]
        != list(PUBLIC_POSE_RANKING_FIT_VALIDATION_SCIENTIFIC_BLOCKERS)
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt accounting or claim blockers are invalid"
        )
    return json.loads(
        json.dumps(
            receipt,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )


def require_public_pose_ranking_fit_validation_selection(
    value: object,
    *,
    training_view_receipt: PublicPoseRankingCalibrationTrainingViewReceipt,
    training_view_receipt_source_file_sha256: str,
    training_view_receipt_source_file_size_bytes: int,
    validation_partition: PoseRankingCalibrationPartition,
    manifest: PublicPoseRankingFitValidationManifest,
    manifest_source_file_sha256: str,
    manifest_source_file_size_bytes: int,
) -> dict[str, object]:
    """Digest-check and exactly reproduce one fit/validation receipt."""

    observed = _validate_receipt_digest(value)
    expected = materialize_public_pose_ranking_fit_validation_selection(
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
    if observed != expected:
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt differs from exact reconstruction"
        )
    return observed


def write_public_pose_ranking_fit_validation_selection(
    path: str | os.PathLike[str],
    receipt: Mapping[str, object],
) -> Path:
    """Write one digest-checked mode-0600 receipt without replacement."""

    verified = _validate_receipt_digest(receipt)
    payload = _canonical_bytes(verified) + b"\n"
    if len(payload) > PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_RECEIPT_BYTES:
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt exceeds its byte bound"
        )
    destination = Path(path)
    if not destination.parent.is_dir():
        raise PublicPoseRankingFitValidationSelectionError(
            "receipt output parent must already exist"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o600)
    except FileExistsError as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt output already exists"
        ) from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise PublicPoseRankingFitValidationSelectionError(
                    "fit/validation receipt write made no progress"
                )
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(
        destination.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return destination


def read_public_pose_ranking_fit_validation_selection(
    path: str | os.PathLike[str],
) -> dict[str, object]:
    """Read and structurally authenticate one private receipt."""

    data, _ = _read_regular_file(
        path,
        name="fit/validation receipt",
        maximum_bytes=PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_RECEIPT_BYTES,
    )
    metadata = os.stat(path, follow_symlinks=False)
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt mode must be 0600"
        )
    try:
        decoded = _decode_json_object(data, name="fit/validation receipt")
    except PublicPoseRankingCalibrationPartitionIntakeError as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt is not valid JSON"
        ) from exc
    verified = _validate_receipt_digest(decoded)
    if data != _canonical_bytes(verified) + b"\n":
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt must use canonical JSON plus one newline"
        )
    return verified


def _load_ancestry_arguments(
    path: str | os.PathLike[str],
) -> dict[str, Any]:
    data, _ = _read_regular_file(
        path,
        name="fit/validation ancestry arguments",
        maximum_bytes=PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_ARGUMENTS_BYTES,
    )
    try:
        decoded = _decode_json_object(
            data,
            name="fit/validation ancestry arguments",
        )
    except PublicPoseRankingCalibrationPartitionIntakeError as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation ancestry arguments are not valid JSON"
        ) from exc
    _exact_keys(
        decoded,
        {
            "schema_id",
            "training_view_materialization_arguments",
        },
        name="fit/validation ancestry arguments",
    )
    if (
        decoded["schema_id"]
        != PUBLIC_POSE_RANKING_FIT_VALIDATION_ANCESTRY_ARGUMENTS_SCHEMA_ID
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation ancestry arguments schema is unsupported"
        )
    arguments = _mapping(
        decoded["training_view_materialization_arguments"],
        name="training-view materialization arguments",
    )

    def reject_test_partition(value: object) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                normalized = str(key).strip().lower().replace("-", "_")
                if normalized in {
                    "test_partition",
                    "test_partition_path",
                    "expected_test_partition_sha256",
                    "expected_test_partition_file_sha256",
                } or (
                    "test" in normalized
                    and "partition" in normalized
                    and (
                        "score" in normalized
                        or "posebusters" in normalized
                    )
                ):
                    raise PublicPoseRankingFitValidationSelectionError(
                        "PoseBusters test score partition input is forbidden"
                    )
                reject_test_partition(item)
        elif isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            for item in value:
                reject_test_partition(item)

    reject_test_partition(arguments)
    return arguments


def _validation_partition_from_arguments(
    arguments: Mapping[str, Any],
) -> PoseRankingCalibrationPartition:
    partition_arguments = _mapping(
        arguments.get("partition_intake_materialization_arguments"),
        name="partition-intake materialization arguments",
    )
    try:
        return load_public_pose_ranking_calibration_partition_file(
            partition_arguments["validation_partition_path"],
            expected_file_sha256=partition_arguments[
                "expected_validation_partition_file_sha256"
            ],
            expected_partition_sha256=partition_arguments[
                "expected_validation_partition_sha256"
            ],
            split_role="validation",
        )
    except (KeyError, PublicPoseRankingCalibrationPartitionIntakeError) as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "bound CASF validation partition could not be loaded"
        ) from exc


def materialize_public_pose_ranking_fit_validation_selection_from_files(
    *,
    training_view_receipt_path: str | os.PathLike[str],
    expected_training_view_receipt_file_sha256: str,
    expected_training_view_receipt_sha256: str,
    ancestry_arguments_path: str | os.PathLike[str],
    candidate_manifest_path: str | os.PathLike[str],
    expected_candidate_manifest_file_sha256: str,
    expected_candidate_manifest_sha256: str,
) -> dict[str, object]:
    """Reverify all ancestry and execute the frozen fit/validation workflow."""

    arguments = _load_ancestry_arguments(ancestry_arguments_path)
    try:
        training_view = (
            verify_public_pose_ranking_calibration_training_view_receipt(
                training_view_receipt_path=training_view_receipt_path,
                **arguments,
            )
        )
    except PublicPoseRankingCalibrationTrainingViewError as exc:
        raise PublicPoseRankingFitValidationSelectionError(
            "training-view ancestry verification failed"
        ) from exc
    training_data, training_file_sha256 = _read_regular_file(
        training_view_receipt_path,
        name="calibration training-view receipt",
        maximum_bytes=(
            PUBLIC_POSE_RANKING_CALIBRATION_TRAINING_VIEW_MAX_RECEIPT_BYTES
        ),
    )
    if training_file_sha256 != _digest(
        expected_training_view_receipt_file_sha256,
        name="expected training-view receipt file SHA-256",
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "training-view receipt file SHA-256 mismatch"
        )
    if training_view.receipt_sha256 != _digest(
        expected_training_view_receipt_sha256,
        name="expected training-view receipt SHA-256",
    ):
        raise PublicPoseRankingFitValidationSelectionError(
            "training-view receipt SHA-256 mismatch"
        )
    validation = _validation_partition_from_arguments(arguments)
    manifest, manifest_file_sha256, manifest_size = (
        load_public_pose_ranking_fit_validation_manifest(
            candidate_manifest_path,
            expected_file_sha256=(
                expected_candidate_manifest_file_sha256
            ),
            expected_manifest_sha256=expected_candidate_manifest_sha256,
        )
    )
    return materialize_public_pose_ranking_fit_validation_selection(
        training_view_receipt=training_view,
        training_view_receipt_source_file_sha256=training_file_sha256,
        training_view_receipt_source_file_size_bytes=len(training_data),
        validation_partition=validation,
        manifest=manifest,
        manifest_source_file_sha256=manifest_file_sha256,
        manifest_source_file_size_bytes=manifest_size,
    )


def verify_public_pose_ranking_fit_validation_selection_receipt(
    *,
    receipt_path: str | os.PathLike[str],
    **materialization_arguments: Any,
) -> dict[str, object]:
    """Reexecute all fits/evaluations and byte-compare the receipt."""

    observed = read_public_pose_ranking_fit_validation_selection(receipt_path)
    expected = (
        materialize_public_pose_ranking_fit_validation_selection_from_files(
            **materialization_arguments
        )
    )
    if observed != expected:
        raise PublicPoseRankingFitValidationSelectionError(
            "fit/validation receipt differs from exact reexecution"
        )
    return observed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-public-ranking-fit-validation",
        description=(
            "Fit preregistered PDBbind candidates and select only on bound "
            "CASF validation labels without loading a PoseBusters test "
            "score partition."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--training-view-receipt", required=True)
        subparser.add_argument(
            "--expected-training-view-receipt-file-sha256",
            required=True,
        )
        subparser.add_argument(
            "--expected-training-view-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--ancestry-arguments", required=True)
        subparser.add_argument("--candidate-manifest", required=True)
        subparser.add_argument(
            "--expected-candidate-manifest-file-sha256",
            required=True,
        )
        subparser.add_argument(
            "--expected-candidate-manifest-sha256",
            required=True,
        )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument("--receipt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "training_view_receipt_path": args.training_view_receipt,
        "expected_training_view_receipt_file_sha256": (
            args.expected_training_view_receipt_file_sha256
        ),
        "expected_training_view_receipt_sha256": (
            args.expected_training_view_receipt_sha256
        ),
        "ancestry_arguments_path": args.ancestry_arguments,
        "candidate_manifest_path": args.candidate_manifest,
        "expected_candidate_manifest_file_sha256": (
            args.expected_candidate_manifest_file_sha256
        ),
        "expected_candidate_manifest_sha256": (
            args.expected_candidate_manifest_sha256
        ),
    }
    if args.command == "materialize":
        receipt = (
            materialize_public_pose_ranking_fit_validation_selection_from_files(
                **common
            )
        )
        write_public_pose_ranking_fit_validation_selection(
            args.output,
            receipt,
        )
    else:
        receipt = (
            verify_public_pose_ranking_fit_validation_selection_receipt(
                receipt_path=args.receipt,
                **common,
            )
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt["receipt_sha256"],
                "candidate_count": receipt["candidate_count"],
                "completed_candidate_count": (
                    receipt["completed_candidate_count"]
                ),
                "selection_complete": receipt["selection_complete"],
                "selected_candidate_id": receipt[
                    "selected_candidate_id"
                ],
                "validation_labels_used_for_fit": False,
                "posebusters_test_score_partition_loaded": False,
                "scientifically_validated": False,
                "claim_safe": False,
            },
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_ANCESTRY_ARGUMENTS_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_CANDIDATE_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_MANIFEST_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_ARGUMENTS_BYTES",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_CANDIDATES",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_MANIFEST_BYTES",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_MAX_RECEIPT_BYTES",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_RECEIPT_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_SCIENTIFIC_BLOCKERS",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY",
    "PUBLIC_POSE_RANKING_FIT_VALIDATION_SELECTION_POLICY_SHA256",
    "PublicPoseRankingFitValidationCandidate",
    "PublicPoseRankingFitValidationManifest",
    "PublicPoseRankingFitValidationSelectionError",
    "load_public_pose_ranking_fit_validation_manifest",
    "materialize_public_pose_ranking_fit_validation_selection",
    "materialize_public_pose_ranking_fit_validation_selection_from_files",
    "read_public_pose_ranking_fit_validation_selection",
    "require_public_pose_ranking_fit_validation_selection",
    "verify_public_pose_ranking_fit_validation_selection_receipt",
    "write_public_pose_ranking_fit_validation_selection",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
