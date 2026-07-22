"""Leakage-audited pose-ranking calibration and failure-inclusive evaluation.

The fitting API consumes only a fit partition.  A separate audit binds that
partition to one evaluation identity commitment and rejects configured identity
overlap before fitting.  No public dataset, fitted model, benchmark result, or
scientific promotion is bundled by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from numbers import Real
import random
from types import MappingProxyType
from typing import Mapping, Sequence

import torch
import torch.nn.functional as functional

from .scoring import (
    DockingScoreBreakdown,
    DockingScoreDescriptor,
    DockingScoreTerm,
    ScoreDirection,
    component_contract_fingerprint,
    scorer_descriptor,
)


POSE_RANKING_CALIBRATION_ROW_SCHEMA_ID = (
    "betelgeuze.engine_v2_pose_ranking_calibration_row/1.0.0"
)
POSE_RANKING_CALIBRATION_PARTITION_SCHEMA_ID = (
    "betelgeuze.engine_v2_pose_ranking_calibration_partition/1.0.0"
)
POSE_RANKING_LEAKAGE_AUDIT_SCHEMA_ID = (
    "betelgeuze.engine_v2_pose_ranking_leakage_audit/1.0.0"
)
POSE_RANKING_CALIBRATION_MODEL_SCHEMA_ID = (
    "betelgeuze.engine_v2_pose_ranking_calibration_model/1.0.0"
)
POSE_RANKING_EVALUATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_pose_ranking_evaluation/1.0.0"
)

MAX_CALIBRATION_ROWS = 100_000
MAX_CALIBRATION_TERMS = 64
MAX_TRAINING_PAIRS = 1_000_000
MAX_BOOTSTRAP_SAMPLES = 10_000
_SPLIT_ROLES = {"fit", "validation", "test", "ood"}


class PoseRankingCalibrationError(ValueError):
    """A calibration, leakage, fitting, or evaluation contract failed closed."""


def _token(value: object, *, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PoseRankingCalibrationError(f"{name} must be non-empty")
    return text


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseRankingCalibrationError(f"{name} must be a SHA-256 string")
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise PoseRankingCalibrationError(f"{name} must be a lowercase SHA-256")
    return digest


def _finite_float(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PoseRankingCalibrationError(f"{name} must be a finite real number")
    number = float(value)
    if not math.isfinite(number):
        raise PoseRankingCalibrationError(f"{name} must be finite")
    return number


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PoseRankingCalibrationError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        upper = "" if maximum is None else f" and at most {maximum}"
        raise PoseRankingCalibrationError(
            f"{name} must be at least {minimum}{upper}"
        )
    return integer


def _canonical_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_terms(value: Mapping[str, float]) -> Mapping[str, float]:
    if not isinstance(value, Mapping):
        raise PoseRankingCalibrationError("term_values must be a mapping")
    terms = {
        _token(key, name="term ID"): _finite_float(item, name=f"term {key}")
        for key, item in value.items()
    }
    if not terms or len(terms) > MAX_CALIBRATION_TERMS:
        raise PoseRankingCalibrationError(
            f"successful rows require 1..{MAX_CALIBRATION_TERMS} score terms"
        )
    return MappingProxyType(dict(sorted(terms.items())))


@dataclass(frozen=True)
class PoseRankingCalibrationRow:
    suite_id: str
    case_id: str
    pose_id: str
    target_id: str
    target_family: str
    split_role: str
    scoring_protocol_sha256: str
    preparation_profile_sha256: str
    receptor_sha256: str
    ligand_sha256: str
    scaffold_sha256: str
    pose_sha256: str
    status: str
    term_values: Mapping[str, float] = field(default_factory=dict)
    native_like: bool | None = None
    error_code: str = ""
    schema_id: str = POSE_RANKING_CALIBRATION_ROW_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSE_RANKING_CALIBRATION_ROW_SCHEMA_ID:
            raise PoseRankingCalibrationError("unsupported calibration row schema")
        for name in (
            "suite_id",
            "case_id",
            "pose_id",
            "target_id",
            "target_family",
        ):
            object.__setattr__(self, name, _token(getattr(self, name), name=name))
        split = _token(self.split_role, name="split_role").lower()
        if split not in _SPLIT_ROLES:
            raise PoseRankingCalibrationError(
                "split_role must be fit, validation, test, or ood"
            )
        object.__setattr__(self, "split_role", split)
        for name in (
            "scoring_protocol_sha256",
            "preparation_profile_sha256",
            "receptor_sha256",
            "ligand_sha256",
            "scaffold_sha256",
            "pose_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        status = _token(self.status, name="status").lower()
        if status not in {"success", "failure"}:
            raise PoseRankingCalibrationError("status must be success or failure")
        object.__setattr__(self, "status", status)
        if status == "success":
            terms = _canonical_terms(self.term_values)
            if not isinstance(self.native_like, bool):
                raise PoseRankingCalibrationError(
                    "successful rows require a boolean native_like label"
                )
            if self.error_code:
                raise PoseRankingCalibrationError(
                    "successful rows cannot contain error_code"
                )
            object.__setattr__(self, "term_values", terms)
        else:
            if self.term_values or self.native_like is not None:
                raise PoseRankingCalibrationError(
                    "failure rows cannot contain terms or a native_like label"
                )
            error_code = _token(self.error_code, name="failure error_code")
            object.__setattr__(self, "term_values", MappingProxyType({}))
            object.__setattr__(self, "native_like", None)
            object.__setattr__(self, "error_code", error_code)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "suite_id": self.suite_id,
            "case_id": self.case_id,
            "pose_id": self.pose_id,
            "target_id": self.target_id,
            "target_family": self.target_family,
            "split_role": self.split_role,
            "scoring_protocol_sha256": self.scoring_protocol_sha256,
            "preparation_profile_sha256": self.preparation_profile_sha256,
            "receptor_sha256": self.receptor_sha256,
            "ligand_sha256": self.ligand_sha256,
            "scaffold_sha256": self.scaffold_sha256,
            "pose_sha256": self.pose_sha256,
            "status": self.status,
            "term_values": dict(self.term_values),
            "native_like": self.native_like,
            "error_code": self.error_code,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def identity_projection(self) -> dict[str, object]:
        return {
            "suite_id": self.suite_id,
            "case_id": self.case_id,
            "pose_id": self.pose_id,
            "target_id": self.target_id,
            "target_family": self.target_family,
            "split_role": self.split_role,
            "scoring_protocol_sha256": self.scoring_protocol_sha256,
            "preparation_profile_sha256": self.preparation_profile_sha256,
            "receptor_sha256": self.receptor_sha256,
            "ligand_sha256": self.ligand_sha256,
            "scaffold_sha256": self.scaffold_sha256,
            "pose_sha256": self.pose_sha256,
        }


@dataclass(frozen=True)
class PoseRankingCalibrationPartition:
    dataset_id: str
    dataset_version: str
    split_role: str
    rows: tuple[PoseRankingCalibrationRow, ...]
    schema_id: str = POSE_RANKING_CALIBRATION_PARTITION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSE_RANKING_CALIBRATION_PARTITION_SCHEMA_ID:
            raise PoseRankingCalibrationError("unsupported calibration partition schema")
        object.__setattr__(self, "dataset_id", _token(self.dataset_id, name="dataset_id"))
        object.__setattr__(
            self,
            "dataset_version",
            _token(self.dataset_version, name="dataset_version"),
        )
        split = _token(self.split_role, name="split_role").lower()
        if split not in _SPLIT_ROLES:
            raise PoseRankingCalibrationError("unsupported partition split_role")
        object.__setattr__(self, "split_role", split)
        rows = tuple(self.rows)
        if not rows or len(rows) > MAX_CALIBRATION_ROWS:
            raise PoseRankingCalibrationError(
                f"partition row count must be in [1,{MAX_CALIBRATION_ROWS}]"
            )
        if not all(isinstance(row, PoseRankingCalibrationRow) for row in rows):
            raise PoseRankingCalibrationError(
                "partition rows must be PoseRankingCalibrationRow"
            )
        if any(row.split_role != split for row in rows):
            raise PoseRankingCalibrationError(
                "every row split_role must match the partition"
            )
        row_keys = [(row.case_id, row.pose_id) for row in rows]
        if len(row_keys) != len(set(row_keys)):
            raise PoseRankingCalibrationError(
                "case_id/pose_id pairs must be unique within a partition"
            )
        successful = [row for row in rows if row.status == "success"]
        if not successful:
            raise PoseRankingCalibrationError(
                "partition must retain at least one successful pose row"
            )
        schemas = {tuple(row.term_values) for row in successful}
        if len(schemas) != 1:
            raise PoseRankingCalibrationError(
                "all successful rows must share one exact term schema"
            )
        case_identity: dict[str, tuple[str, str, str, str, str]] = {}
        for row in rows:
            identity = (
                row.suite_id,
                row.target_id,
                row.target_family,
                row.receptor_sha256,
                row.ligand_sha256,
            )
            previous = case_identity.setdefault(row.case_id, identity)
            if previous != identity:
                raise PoseRankingCalibrationError(
                    "case rows disagree on suite, target, family, receptor, or ligand identity"
                )
        if len({row.scoring_protocol_sha256 for row in rows}) != 1:
            raise PoseRankingCalibrationError(
                "partition rows must share one scoring protocol identity"
            )
        if len({row.preparation_profile_sha256 for row in rows}) != 1:
            raise PoseRankingCalibrationError(
                "partition rows must share one preparation profile identity"
            )
        object.__setattr__(self, "rows", rows)

    @property
    def term_ids(self) -> tuple[str, ...]:
        row = next(item for item in self.rows if item.status == "success")
        return tuple(row.term_values)

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(sorted({row.case_id for row in self.rows}))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "split_role": self.split_role,
            "term_ids": list(self.term_ids),
            "rows": [row.to_dict() for row in self.rows],
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @property
    def identity_fingerprint_sha256(self) -> str:
        return _canonical_sha256(
            {
                "schema_id": self.schema_id,
                "dataset_id": self.dataset_id,
                "dataset_version": self.dataset_version,
                "split_role": self.split_role,
                "rows": [row.identity_projection() for row in self.rows],
            }
        )


@dataclass(frozen=True)
class PoseRankingLeakagePolicy:
    require_target_disjoint: bool = True
    require_family_disjoint: bool = False
    require_receptor_disjoint: bool = True
    require_ligand_disjoint: bool = True
    require_scaffold_disjoint: bool = True

    def __post_init__(self) -> None:
        for name in (
            "require_target_disjoint",
            "require_family_disjoint",
            "require_receptor_disjoint",
            "require_ligand_disjoint",
            "require_scaffold_disjoint",
        ):
            if not isinstance(getattr(self, name), bool):
                raise PoseRankingCalibrationError(f"{name} must be boolean")

    def to_dict(self) -> dict[str, bool]:
        return {
            "require_target_disjoint": self.require_target_disjoint,
            "require_family_disjoint": self.require_family_disjoint,
            "require_receptor_disjoint": self.require_receptor_disjoint,
            "require_ligand_disjoint": self.require_ligand_disjoint,
            "require_scaffold_disjoint": self.require_scaffold_disjoint,
        }


@dataclass(frozen=True)
class PoseRankingLeakageAudit:
    fit_partition_sha256: str
    evaluation_partition_sha256: str
    fit_identity_sha256: str
    evaluation_identity_sha256: str
    policy: PoseRankingLeakagePolicy
    overlaps: Mapping[str, tuple[str, ...]]
    blockers: tuple[str, ...]
    schema_id: str = POSE_RANKING_LEAKAGE_AUDIT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSE_RANKING_LEAKAGE_AUDIT_SCHEMA_ID:
            raise PoseRankingCalibrationError("unsupported leakage audit schema")
        for name in (
            "fit_partition_sha256",
            "evaluation_partition_sha256",
            "fit_identity_sha256",
            "evaluation_identity_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if not isinstance(self.policy, PoseRankingLeakagePolicy):
            raise PoseRankingCalibrationError("audit policy type is invalid")
        overlaps = {
            _token(key, name="overlap kind"): tuple(sorted(set(values)))
            for key, values in self.overlaps.items()
        }
        blockers = tuple(_token(value, name="audit blocker") for value in self.blockers)
        if len(blockers) != len(set(blockers)):
            raise PoseRankingCalibrationError("audit blockers must be unique")
        object.__setattr__(self, "overlaps", MappingProxyType(dict(sorted(overlaps.items()))))
        object.__setattr__(self, "blockers", blockers)

    @property
    def passed(self) -> bool:
        return not self.blockers

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "fit_partition_sha256": self.fit_partition_sha256,
            "evaluation_partition_sha256": self.evaluation_partition_sha256,
            "fit_identity_sha256": self.fit_identity_sha256,
            "evaluation_identity_sha256": self.evaluation_identity_sha256,
            "policy": self.policy.to_dict(),
            "overlaps": {key: list(values) for key, values in self.overlaps.items()},
            "blockers": list(self.blockers),
            "passed": self.passed,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _values(rows: Sequence[PoseRankingCalibrationRow], field_name: str) -> set[str]:
    return {str(getattr(row, field_name)) for row in rows}


def audit_pose_ranking_leakage(
    fit: PoseRankingCalibrationPartition,
    evaluation: PoseRankingCalibrationPartition,
    *,
    policy: PoseRankingLeakagePolicy | None = None,
) -> PoseRankingLeakageAudit:
    """Bind two partitions and retain every exact identity overlap."""

    if fit.split_role != "fit":
        raise PoseRankingCalibrationError("fit partition must use split_role=fit")
    if evaluation.split_role == "fit":
        raise PoseRankingCalibrationError("evaluation partition cannot use split_role=fit")
    active = policy or PoseRankingLeakagePolicy()
    field_by_kind = {
        "case_id": "case_id",
        "pose_sha256": "pose_sha256",
        "target_id": "target_id",
        "target_family": "target_family",
        "receptor_sha256": "receptor_sha256",
        "ligand_sha256": "ligand_sha256",
        "scaffold_sha256": "scaffold_sha256",
        "scoring_protocol_sha256": "scoring_protocol_sha256",
        "preparation_profile_sha256": "preparation_profile_sha256",
    }
    overlaps = {
        kind: tuple(
            sorted(
                _values(fit.rows, field_name)
                & _values(evaluation.rows, field_name)
            )
        )
        for kind, field_name in field_by_kind.items()
    }
    required = {
        "case_id": True,
        "pose_sha256": True,
        "target_id": active.require_target_disjoint,
        "target_family": active.require_family_disjoint,
        "receptor_sha256": active.require_receptor_disjoint,
        "ligand_sha256": active.require_ligand_disjoint,
        "scaffold_sha256": active.require_scaffold_disjoint,
        "scoring_protocol_sha256": False,
        "preparation_profile_sha256": False,
    }
    blockers = tuple(
        f"{kind}_overlap"
        for kind in field_by_kind
        if required[kind] and overlaps[kind]
    )
    compatibility_blockers = []
    if not overlaps["scoring_protocol_sha256"]:
        compatibility_blockers.append("scoring_protocol_mismatch")
    if not overlaps["preparation_profile_sha256"]:
        compatibility_blockers.append("preparation_profile_mismatch")
    return PoseRankingLeakageAudit(
        fit_partition_sha256=fit.fingerprint_sha256,
        evaluation_partition_sha256=evaluation.fingerprint_sha256,
        fit_identity_sha256=fit.identity_fingerprint_sha256,
        evaluation_identity_sha256=evaluation.identity_fingerprint_sha256,
        policy=active,
        overlaps=overlaps,
        blockers=(*blockers, *compatibility_blockers),
    )


@dataclass(frozen=True)
class PoseRankingCalibrationConfig:
    term_ids: tuple[str, ...]
    learning_rate: float = 0.05
    l2_penalty: float = 1.0e-3
    iterations: int = 500
    trace_interval: int = 25
    max_training_pairs: int = 100_000

    def __post_init__(self) -> None:
        term_ids = tuple(_token(value, name="term ID") for value in self.term_ids)
        if (
            not term_ids
            or len(term_ids) > MAX_CALIBRATION_TERMS
            or len(term_ids) != len(set(term_ids))
        ):
            raise PoseRankingCalibrationError(
                "term_ids must be 1..64 unique non-empty values"
            )
        object.__setattr__(self, "term_ids", term_ids)
        learning_rate = _finite_float(self.learning_rate, name="learning_rate")
        if learning_rate <= 0.0:
            raise PoseRankingCalibrationError("learning_rate must be positive")
        l2 = _finite_float(self.l2_penalty, name="l2_penalty")
        if l2 < 0.0:
            raise PoseRankingCalibrationError("l2_penalty must be non-negative")
        object.__setattr__(self, "learning_rate", learning_rate)
        object.__setattr__(self, "l2_penalty", l2)
        object.__setattr__(
            self,
            "iterations",
            _exact_int(self.iterations, name="iterations", minimum=1, maximum=100_000),
        )
        trace_interval = _exact_int(
            self.trace_interval,
            name="trace_interval",
            minimum=1,
        )
        if trace_interval > self.iterations:
            raise PoseRankingCalibrationError(
                "trace_interval cannot exceed iterations"
            )
        object.__setattr__(self, "trace_interval", trace_interval)
        object.__setattr__(
            self,
            "max_training_pairs",
            _exact_int(
                self.max_training_pairs,
                name="max_training_pairs",
                minimum=1,
                maximum=MAX_TRAINING_PAIRS,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "term_ids": list(self.term_ids),
            "learning_rate": self.learning_rate,
            "l2_penalty": self.l2_penalty,
            "iterations": self.iterations,
            "trace_interval": self.trace_interval,
            "max_training_pairs": self.max_training_pairs,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class PoseRankingCalibrationModel:
    term_ids: tuple[str, ...]
    feature_means: tuple[float, ...]
    feature_scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    training_pair_count: int
    training_case_count: int
    loss_trace: tuple[tuple[int, float], ...]
    fit_partition_sha256: str
    evaluation_identity_sha256: str
    leakage_audit_sha256: str
    config_sha256: str
    schema_id: str = POSE_RANKING_CALIBRATION_MODEL_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSE_RANKING_CALIBRATION_MODEL_SCHEMA_ID:
            raise PoseRankingCalibrationError("unsupported calibration model schema")
        width = len(self.term_ids)
        if width < 1 or any(
            len(values) != width
            for values in (self.feature_means, self.feature_scales, self.coefficients)
        ):
            raise PoseRankingCalibrationError("calibration model vector widths differ")
        if len(set(self.term_ids)) != width:
            raise PoseRankingCalibrationError("calibration model term IDs are not unique")
        means = tuple(
            _finite_float(value, name="feature mean") for value in self.feature_means
        )
        scales = tuple(
            _finite_float(value, name="feature scale") for value in self.feature_scales
        )
        coefficients = tuple(
            _finite_float(value, name="coefficient") for value in self.coefficients
        )
        if any(value <= 0.0 for value in scales):
            raise PoseRankingCalibrationError("feature scales must be positive")
        object.__setattr__(self, "feature_means", means)
        object.__setattr__(self, "feature_scales", scales)
        object.__setattr__(self, "coefficients", coefficients)
        object.__setattr__(
            self,
            "training_pair_count",
            _exact_int(self.training_pair_count, name="training_pair_count", minimum=1),
        )
        object.__setattr__(
            self,
            "training_case_count",
            _exact_int(self.training_case_count, name="training_case_count", minimum=1),
        )
        trace = tuple(
            (
                _exact_int(iteration, name="loss iteration", minimum=0),
                _finite_float(loss, name="training loss"),
            )
            for iteration, loss in self.loss_trace
        )
        if not trace or any(
            second[0] <= first[0] for first, second in zip(trace, trace[1:])
        ):
            raise PoseRankingCalibrationError(
                "loss_trace must have strictly increasing iterations"
            )
        object.__setattr__(self, "loss_trace", trace)
        for name in (
            "fit_partition_sha256",
            "evaluation_identity_sha256",
            "leakage_audit_sha256",
            "config_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))

    def score_terms(self, term_values: Mapping[str, float]) -> float:
        if set(term_values) != set(self.term_ids):
            raise PoseRankingCalibrationError(
                "score terms do not match the calibration model schema"
            )
        values = [
            _finite_float(term_values[term_id], name=f"term {term_id}")
            for term_id in self.term_ids
        ]
        score = math.fsum(
            coefficient * ((value - mean) / scale)
            for value, mean, scale, coefficient in zip(
                values,
                self.feature_means,
                self.feature_scales,
                self.coefficients,
            )
        )
        return _finite_float(score, name="calibrated ranking score")

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "term_ids": list(self.term_ids),
            "feature_means": list(self.feature_means),
            "feature_scales": list(self.feature_scales),
            "coefficients": list(self.coefficients),
            "training_pair_count": self.training_pair_count,
            "training_case_count": self.training_case_count,
            "loss_trace": [
                {"iteration": iteration, "loss": loss}
                for iteration, loss in self.loss_trace
            ],
            "fit_partition_sha256": self.fit_partition_sha256,
            "evaluation_identity_sha256": self.evaluation_identity_sha256,
            "leakage_audit_sha256": self.leakage_audit_sha256,
            "config_sha256": self.config_sha256,
            "score_direction": "minimize",
            "fit_complete": True,
            "holdout_validated": False,
            "scientifically_validated": False,
            "claim_safe": False,
            "blockers": [
                "holdout_evaluation_missing",
                "public_benchmark_result_missing",
                "independent_external_rerun_missing",
            ],
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _training_matrix(
    partition: PoseRankingCalibrationPartition,
    config: PoseRankingCalibrationConfig,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, int]:
    if any(row.status != "success" for row in partition.rows):
        raise PoseRankingCalibrationError(
            "fit partition contains retained failure rows and cannot be fitted"
        )
    if set(partition.term_ids) != set(config.term_ids):
        raise PoseRankingCalibrationError(
            "fit partition term schema does not match calibration config"
        )
    ordered = sorted(partition.rows, key=lambda row: (row.case_id, row.pose_id))
    values = torch.tensor(
        [
            [float(row.term_values[term_id]) for term_id in config.term_ids]
            for row in ordered
        ],
        dtype=torch.float64,
    )
    means = values.mean(dim=0)
    scales = values.std(dim=0, unbiased=False)
    scales = torch.where(scales > 1.0e-12, scales, torch.ones_like(scales))
    standardized = (values - means) / scales
    index = {(row.case_id, row.pose_id): position for position, row in enumerate(ordered)}
    case_rows: dict[str, list[PoseRankingCalibrationRow]] = {}
    for row in ordered:
        case_rows.setdefault(row.case_id, []).append(row)
    differences: list[torch.Tensor] = []
    for case_id in sorted(case_rows):
        positives = [row for row in case_rows[case_id] if row.native_like]
        negatives = [row for row in case_rows[case_id] if not row.native_like]
        if not positives or not negatives:
            raise PoseRankingCalibrationError(
                f"fit case {case_id} must contain native-like and non-native poses"
            )
        for positive in positives:
            for negative in negatives:
                differences.append(
                    standardized[index[(case_id, positive.pose_id)]]
                    - standardized[index[(case_id, negative.pose_id)]]
                )
                if len(differences) > config.max_training_pairs:
                    raise PoseRankingCalibrationError(
                        "training pair count exceeds max_training_pairs"
                    )
    return torch.stack(differences), means, scales, len(case_rows)


def fit_pose_ranking_calibration(
    fit: PoseRankingCalibrationPartition,
    leakage_audit: PoseRankingLeakageAudit,
    config: PoseRankingCalibrationConfig,
) -> PoseRankingCalibrationModel:
    """Fit deterministic pairwise logistic weights using only fit rows."""

    if fit.split_role != "fit":
        raise PoseRankingCalibrationError("calibration fitting requires split_role=fit")
    if not leakage_audit.passed:
        raise PoseRankingCalibrationError(
            "calibration fitting requires a passing leakage audit"
        )
    if leakage_audit.fit_partition_sha256 != fit.fingerprint_sha256:
        raise PoseRankingCalibrationError(
            "leakage audit does not bind the supplied fit partition"
        )
    differences, means, scales, case_count = _training_matrix(fit, config)
    coefficients = torch.zeros(len(config.term_ids), dtype=torch.float64)
    trace: list[tuple[int, float]] = []
    pair_count = int(differences.shape[0])
    for iteration in range(config.iterations + 1):
        logits = differences @ coefficients
        loss = functional.softplus(logits).mean() + (
            0.5 * config.l2_penalty * coefficients.square().sum()
        )
        if (
            iteration == 0
            or iteration == config.iterations
            or iteration % config.trace_interval == 0
        ):
            trace.append((iteration, float(loss.item())))
        if iteration == config.iterations:
            break
        gradient = (
            differences.T @ torch.sigmoid(logits)
        ) / float(pair_count) + config.l2_penalty * coefficients
        coefficients = coefficients - config.learning_rate * gradient
    return PoseRankingCalibrationModel(
        term_ids=config.term_ids,
        feature_means=tuple(float(value) for value in means.tolist()),
        feature_scales=tuple(float(value) for value in scales.tolist()),
        coefficients=tuple(float(value) for value in coefficients.tolist()),
        training_pair_count=pair_count,
        training_case_count=case_count,
        loss_trace=tuple(trace),
        fit_partition_sha256=fit.fingerprint_sha256,
        evaluation_identity_sha256=leakage_audit.evaluation_identity_sha256,
        leakage_audit_sha256=leakage_audit.fingerprint_sha256,
        config_sha256=config.fingerprint_sha256,
    )


class TrainingFitPoseRankingScorer:
    """Apply one fit-only linear model without claiming holdout validation."""

    scorer_version = "1.0.0"
    validated_for_docking_ranking = False

    def __init__(self, base_scorer: object, model: PoseRankingCalibrationModel) -> None:
        if not callable(getattr(base_scorer, "score", None)):
            raise PoseRankingCalibrationError("base_scorer must provide score(proposal)")
        if not isinstance(model, PoseRankingCalibrationModel):
            raise PoseRankingCalibrationError(
                "model must be PoseRankingCalibrationModel"
            )
        self.base_scorer = base_scorer
        self.model = model
        self.scorer_id = (
            "training-fit-pose-ranking:" + _token(
                getattr(base_scorer, "scorer_id", ""),
                name="base scorer_id",
            )
        )
        base_descriptor = scorer_descriptor(base_scorer)
        self.score_descriptor = DockingScoreDescriptor(
            score_id="training_fit_pose_ranking_score",
            direction=ScoreDirection.MINIMIZE,
            unit=None,
            semantics=(
                "fit_partition_only_standardized_linear_combination_of_explicit_"
                "base_score_terms"
            ),
            calibrated=False,
            applicability_domain_id=base_descriptor.applicability_domain_id,
        )
        self.config_fingerprint_sha256 = _canonical_sha256(
            {
                "base_scorer_fingerprint_sha256": component_contract_fingerprint(
                    base_scorer,
                    kind="scorer",
                ),
                "calibration_model_sha256": model.fingerprint_sha256,
            }
        )

    def score(self, proposal: object) -> DockingScoreBreakdown:
        breakdown = self.base_scorer.score(proposal)
        if not isinstance(breakdown, DockingScoreBreakdown) or not breakdown.complete:
            raise PoseRankingCalibrationError(
                "base scorer must return a complete DockingScoreBreakdown"
            )
        terms = {term.term_id: term for term in breakdown.terms}
        if set(terms) != set(self.model.term_ids):
            raise PoseRankingCalibrationError(
                "base score terms do not match the calibration model"
            )
        transformed: list[DockingScoreTerm] = []
        for term_id, mean, scale, coefficient in zip(
            self.model.term_ids,
            self.model.feature_means,
            self.model.feature_scales,
            self.model.coefficients,
        ):
            base = terms[term_id]
            transformed.append(
                DockingScoreTerm(
                    term_id=term_id,
                    raw_value=(base.raw_value - mean) / scale,
                    weight=coefficient,
                    unit=None,
                    semantics=(
                        "training_fit_standardized_base_term:" + base.semantics
                    ),
                    parameter_source_sha256=base.parameter_source_sha256,
                )
            )
        blockers = tuple(
            dict.fromkeys(
                (
                    *breakdown.blockers,
                    "training_fit_only_not_holdout_validated",
                    "public_benchmark_result_missing",
                    "independent_external_rerun_missing",
                )
            )
        )
        return DockingScoreBreakdown(terms=tuple(transformed), blockers=blockers)


@dataclass(frozen=True)
class PoseRankingEvaluationConfig:
    confidence_level: float = 0.95
    bootstrap_samples: int = 2_000
    seed: int = 7301

    def __post_init__(self) -> None:
        level = _finite_float(self.confidence_level, name="confidence_level")
        if not 0.0 < level < 1.0:
            raise PoseRankingCalibrationError("confidence_level must be in (0,1)")
        object.__setattr__(self, "confidence_level", level)
        object.__setattr__(
            self,
            "bootstrap_samples",
            _exact_int(
                self.bootstrap_samples,
                name="bootstrap_samples",
                minimum=1,
                maximum=MAX_BOOTSTRAP_SAMPLES,
            ),
        )
        object.__setattr__(self, "seed", _exact_int(self.seed, name="seed"))

    def to_dict(self) -> dict[str, object]:
        return {
            "confidence_level": self.confidence_level,
            "bootstrap_samples": self.bootstrap_samples,
            "seed": self.seed,
        }


def _bootstrap_interval(
    values: Sequence[float],
    *,
    config: PoseRankingEvaluationConfig,
    scope: str,
) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    seed = int.from_bytes(
        hashlib.sha256(f"{config.seed}:{scope}".encode("utf-8")).digest()[:8],
        "big",
    )
    generator = random.Random(seed)
    count = len(values)
    sampled = sorted(
        math.fsum(values[generator.randrange(count)] for _ in range(count)) / count
        for _ in range(config.bootstrap_samples)
    )
    alpha = (1.0 - config.confidence_level) / 2.0
    low_index = min(len(sampled) - 1, int(math.floor(alpha * len(sampled))))
    high_index = min(
        len(sampled) - 1,
        int(math.ceil((1.0 - alpha) * len(sampled))) - 1,
    )
    return float(sampled[low_index]), float(sampled[high_index])


@dataclass(frozen=True)
class PoseRankingCaseEvaluation:
    case_id: str
    target_id: str
    target_family: str
    total_pose_count: int
    successful_pose_count: int
    failed_pose_count: int
    top1_native_like: bool
    top5_native_like: bool
    ranked_pose_ids: tuple[str, ...]
    failed_pose_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "target_id": self.target_id,
            "target_family": self.target_family,
            "total_pose_count": self.total_pose_count,
            "successful_pose_count": self.successful_pose_count,
            "failed_pose_count": self.failed_pose_count,
            "top1_native_like": self.top1_native_like,
            "top5_native_like": self.top5_native_like,
            "ranked_pose_ids": list(self.ranked_pose_ids),
            "failed_pose_ids": list(self.failed_pose_ids),
        }


@dataclass(frozen=True)
class PoseRankingMetricEstimate:
    metric_id: str
    value: float
    confidence_interval_low: float
    confidence_interval_high: float
    confidence_level: float
    numerator: int
    all_case_denominator: int

    def to_dict(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "value": self.value,
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
            "confidence_level": self.confidence_level,
            "numerator": self.numerator,
            "all_case_denominator": self.all_case_denominator,
        }


@dataclass(frozen=True)
class PoseRankingFamilyEvaluation:
    target_family: str
    case_count: int
    metrics: tuple[PoseRankingMetricEstimate, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "target_family": self.target_family,
            "case_count": self.case_count,
            "metrics": [metric.to_dict() for metric in self.metrics],
        }


def _metrics(
    cases: Sequence[PoseRankingCaseEvaluation],
    *,
    config: PoseRankingEvaluationConfig,
    scope: str,
) -> tuple[PoseRankingMetricEstimate, ...]:
    definitions = {
        "top1_native_like_rate": [float(case.top1_native_like) for case in cases],
        "top5_native_like_rate": [float(case.top5_native_like) for case in cases],
        "scored_case_coverage": [
            float(case.successful_pose_count > 0) for case in cases
        ],
    }
    denominator = len(cases)
    metrics: list[PoseRankingMetricEstimate] = []
    for metric_id, values in definitions.items():
        numerator = int(sum(values))
        value = float(numerator) / float(denominator) if denominator else 0.0
        low, high = _bootstrap_interval(
            values,
            config=config,
            scope=f"{scope}:{metric_id}",
        )
        metrics.append(
            PoseRankingMetricEstimate(
                metric_id=metric_id,
                value=value,
                confidence_interval_low=low,
                confidence_interval_high=high,
                confidence_level=config.confidence_level,
                numerator=numerator,
                all_case_denominator=denominator,
            )
        )
    return tuple(metrics)


@dataclass(frozen=True)
class PoseRankingEvaluationReport:
    model_sha256: str
    evaluation_partition_sha256: str
    leakage_audit_sha256: str
    config: PoseRankingEvaluationConfig
    cases: tuple[PoseRankingCaseEvaluation, ...]
    overall_metrics: tuple[PoseRankingMetricEstimate, ...]
    family_metrics: tuple[PoseRankingFamilyEvaluation, ...]
    schema_id: str = POSE_RANKING_EVALUATION_SCHEMA_ID

    @property
    def all_case_denominator(self) -> int:
        return len(self.cases)

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "model_sha256": self.model_sha256,
            "evaluation_partition_sha256": self.evaluation_partition_sha256,
            "leakage_audit_sha256": self.leakage_audit_sha256,
            "config": self.config.to_dict(),
            "all_case_denominator": self.all_case_denominator,
            "cases": [case.to_dict() for case in self.cases],
            "overall_metrics": [metric.to_dict() for metric in self.overall_metrics],
            "family_metrics": [family.to_dict() for family in self.family_metrics],
            "claim_safe": False,
            "blockers": [
                "public_dataset_result_not_established",
                "independent_external_rerun_missing",
                "scientific_review_missing",
            ],
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def evaluate_pose_ranking_calibration(
    model: PoseRankingCalibrationModel,
    evaluation: PoseRankingCalibrationPartition,
    leakage_audit: PoseRankingLeakageAudit,
    *,
    config: PoseRankingEvaluationConfig | None = None,
) -> PoseRankingEvaluationReport:
    """Evaluate one held-out partition with failures retained in every denominator."""

    if evaluation.split_role == "fit":
        raise PoseRankingCalibrationError("evaluation cannot consume a fit partition")
    if not leakage_audit.passed:
        raise PoseRankingCalibrationError("evaluation requires a passing leakage audit")
    if leakage_audit.evaluation_partition_sha256 != evaluation.fingerprint_sha256:
        raise PoseRankingCalibrationError(
            "leakage audit does not bind the evaluation partition"
        )
    if model.leakage_audit_sha256 != leakage_audit.fingerprint_sha256:
        raise PoseRankingCalibrationError("model does not bind the leakage audit")
    if model.evaluation_identity_sha256 != evaluation.identity_fingerprint_sha256:
        raise PoseRankingCalibrationError(
            "model holdout identity commitment does not match evaluation"
        )
    active = config or PoseRankingEvaluationConfig()
    grouped: dict[str, list[PoseRankingCalibrationRow]] = {}
    for row in evaluation.rows:
        grouped.setdefault(row.case_id, []).append(row)
    case_results: list[PoseRankingCaseEvaluation] = []
    for case_id in sorted(grouped):
        rows = sorted(grouped[case_id], key=lambda row: row.pose_id)
        successful = [row for row in rows if row.status == "success"]
        failed = [row for row in rows if row.status == "failure"]
        ranked = sorted(
            successful,
            key=lambda row: (model.score_terms(row.term_values), row.pose_id),
        )
        case_results.append(
            PoseRankingCaseEvaluation(
                case_id=case_id,
                target_id=rows[0].target_id,
                target_family=rows[0].target_family,
                total_pose_count=len(rows),
                successful_pose_count=len(successful),
                failed_pose_count=len(failed),
                top1_native_like=bool(ranked and ranked[0].native_like),
                top5_native_like=any(
                    bool(row.native_like) for row in ranked[:5]
                ),
                ranked_pose_ids=tuple(row.pose_id for row in ranked),
                failed_pose_ids=tuple(row.pose_id for row in failed),
            )
        )
    families: dict[str, list[PoseRankingCaseEvaluation]] = {}
    for case in case_results:
        families.setdefault(case.target_family, []).append(case)
    family_results = tuple(
        PoseRankingFamilyEvaluation(
            target_family=family,
            case_count=len(families[family]),
            metrics=_metrics(
                families[family],
                config=active,
                scope=f"family:{family}",
            ),
        )
        for family in sorted(families)
    )
    return PoseRankingEvaluationReport(
        model_sha256=model.fingerprint_sha256,
        evaluation_partition_sha256=evaluation.fingerprint_sha256,
        leakage_audit_sha256=leakage_audit.fingerprint_sha256,
        config=active,
        cases=tuple(case_results),
        overall_metrics=_metrics(case_results, config=active, scope="overall"),
        family_metrics=family_results,
    )


__all__ = [
    "MAX_BOOTSTRAP_SAMPLES",
    "MAX_CALIBRATION_ROWS",
    "MAX_CALIBRATION_TERMS",
    "MAX_TRAINING_PAIRS",
    "POSE_RANKING_CALIBRATION_MODEL_SCHEMA_ID",
    "POSE_RANKING_CALIBRATION_PARTITION_SCHEMA_ID",
    "POSE_RANKING_CALIBRATION_ROW_SCHEMA_ID",
    "POSE_RANKING_EVALUATION_SCHEMA_ID",
    "POSE_RANKING_LEAKAGE_AUDIT_SCHEMA_ID",
    "PoseRankingCalibrationConfig",
    "PoseRankingCalibrationError",
    "PoseRankingCalibrationModel",
    "PoseRankingCalibrationPartition",
    "PoseRankingCalibrationRow",
    "PoseRankingCaseEvaluation",
    "PoseRankingEvaluationConfig",
    "PoseRankingEvaluationReport",
    "PoseRankingFamilyEvaluation",
    "PoseRankingLeakageAudit",
    "PoseRankingLeakagePolicy",
    "PoseRankingMetricEstimate",
    "TrainingFitPoseRankingScorer",
    "audit_pose_ranking_leakage",
    "evaluate_pose_ranking_calibration",
    "fit_pose_ranking_calibration",
]
