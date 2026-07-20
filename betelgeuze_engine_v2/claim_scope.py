"""Scope-qualified metric records for scientific and parity claim surfaces."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any


CLAIM_METRIC_RECORD_SCHEMA_ID = (
    "betelgeuze.engine_v2_claim_metric_record/1.0.0"
)
CLAIM_METRIC_SCOPE_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_claim_metric_scope_policy/1.0.0"
)
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

CLAIM_METRIC_REQUIRED_FIELDS = (
    "schema_id",
    "scope_id",
    "task_id",
    "dataset_id",
    "dataset_version",
    "split_id",
    "target_family",
    "scorer_id",
    "scorer_version",
    "engine_commit",
    "metric_id",
    "metric_direction",
    "unit",
    "value",
    "confidence_interval_low",
    "confidence_interval_high",
    "denominator_count",
    "failure_count",
    "as_of_utc",
    "claim_boundary",
    "source_artifact_sha256",
)


class ClaimScopeError(ValueError):
    """A scientific metric omits its evaluation or claim scope."""


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
        raise ClaimScopeError("claim metric record is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: object, *, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise ClaimScopeError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ClaimScopeError(f"{name} must contain 1 to {maximum} characters")
    if any(ord(character) < 32 for character in normalized):
        raise ClaimScopeError(f"{name} contains control characters")
    return normalized


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool):
        raise ClaimScopeError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ClaimScopeError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ClaimScopeError(f"{name} must be finite")
    return result


def _count(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ClaimScopeError(f"{name} must be a non-negative integer")
    return value


def _utc(value: object, *, name: str) -> str:
    text = _text(value, name=name, maximum=20)
    if not text.endswith("Z"):
        raise ClaimScopeError(f"{name} must use second-resolution UTC")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ClaimScopeError(
            f"{name} must use second-resolution UTC"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise ClaimScopeError(f"{name} is not canonical UTC")
    return text


@dataclass(frozen=True, slots=True)
class ClaimMetricRecord:
    scope_id: str
    task_id: str
    dataset_id: str
    dataset_version: str
    split_id: str
    target_family: str
    scorer_id: str
    scorer_version: str
    engine_commit: str
    metric_id: str
    metric_direction: str
    unit: str | None
    value: float
    confidence_interval_low: float
    confidence_interval_high: float
    denominator_count: int
    failure_count: int
    as_of_utc: str
    claim_boundary: str
    source_artifact_sha256: str
    schema_id: str = CLAIM_METRIC_RECORD_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != CLAIM_METRIC_RECORD_SCHEMA_ID:
            raise ClaimScopeError("unsupported claim metric record schema")
        for name in (
            "scope_id",
            "task_id",
            "dataset_id",
            "dataset_version",
            "split_id",
            "target_family",
            "scorer_id",
            "scorer_version",
            "metric_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name=name),
            )
        direction = _text(
            self.metric_direction,
            name="metric_direction",
            maximum=16,
        ).lower()
        if direction not in {"minimize", "maximize"}:
            raise ClaimScopeError(
                "metric_direction must be minimize or maximize"
            )
        object.__setattr__(self, "metric_direction", direction)
        if self.unit is not None:
            object.__setattr__(self, "unit", _text(self.unit, name="unit"))
        if not isinstance(self.engine_commit, str) or not _GIT_COMMIT_RE.fullmatch(
            self.engine_commit
        ):
            raise ClaimScopeError(
                "engine_commit must be a lowercase 40-character Git SHA"
            )
        if (
            not isinstance(self.source_artifact_sha256, str)
            or not _SHA256_RE.fullmatch(self.source_artifact_sha256)
        ):
            raise ClaimScopeError(
                "source_artifact_sha256 must be a lowercase SHA-256"
            )
        value = _finite(self.value, name="value")
        ci_low = _finite(
            self.confidence_interval_low,
            name="confidence_interval_low",
        )
        ci_high = _finite(
            self.confidence_interval_high,
            name="confidence_interval_high",
        )
        if ci_low > value or value > ci_high:
            raise ClaimScopeError(
                "confidence interval must contain the metric value"
            )
        denominator = _count(
            self.denominator_count,
            name="denominator_count",
        )
        failures = _count(self.failure_count, name="failure_count")
        if denominator < 1:
            raise ClaimScopeError("denominator_count must be positive")
        if failures > denominator:
            raise ClaimScopeError(
                "failure_count cannot exceed denominator_count"
            )
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "confidence_interval_low", ci_low)
        object.__setattr__(self, "confidence_interval_high", ci_high)
        object.__setattr__(self, "denominator_count", denominator)
        object.__setattr__(self, "failure_count", failures)
        object.__setattr__(
            self,
            "as_of_utc",
            _utc(self.as_of_utc, name="as_of_utc"),
        )
        object.__setattr__(
            self,
            "claim_boundary",
            _text(
                self.claim_boundary,
                name="claim_boundary",
                maximum=1_024,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "scope_id": self.scope_id,
            "task_id": self.task_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "split_id": self.split_id,
            "target_family": self.target_family,
            "scorer_id": self.scorer_id,
            "scorer_version": self.scorer_version,
            "engine_commit": self.engine_commit,
            "metric_id": self.metric_id,
            "metric_direction": self.metric_direction,
            "unit": self.unit,
            "value": self.value,
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
            "denominator_count": self.denominator_count,
            "failure_count": self.failure_count,
            "as_of_utc": self.as_of_utc,
            "claim_boundary": self.claim_boundary,
            "source_artifact_sha256": self.source_artifact_sha256,
            "claim_safe": False,
            "scientifically_validated": False,
            "product_qualified": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ClaimMetricRecord":
        if not isinstance(payload, Mapping):
            raise ClaimScopeError("claim metric record must be a mapping")
        if set(payload) != set(CLAIM_METRIC_REQUIRED_FIELDS):
            missing = sorted(set(CLAIM_METRIC_REQUIRED_FIELDS) - set(payload))
            extra = sorted(set(payload) - set(CLAIM_METRIC_REQUIRED_FIELDS))
            raise ClaimScopeError(
                f"claim metric fields are invalid; missing={missing}, extra={extra}"
            )
        return cls(
            scope_id=payload["scope_id"],
            task_id=payload["task_id"],
            dataset_id=payload["dataset_id"],
            dataset_version=payload["dataset_version"],
            split_id=payload["split_id"],
            target_family=payload["target_family"],
            scorer_id=payload["scorer_id"],
            scorer_version=payload["scorer_version"],
            engine_commit=payload["engine_commit"],
            metric_id=payload["metric_id"],
            metric_direction=payload["metric_direction"],
            unit=payload["unit"],
            value=payload["value"],
            confidence_interval_low=payload["confidence_interval_low"],
            confidence_interval_high=payload["confidence_interval_high"],
            denominator_count=payload["denominator_count"],
            failure_count=payload["failure_count"],
            as_of_utc=payload["as_of_utc"],
            claim_boundary=payload["claim_boundary"],
            source_artifact_sha256=payload["source_artifact_sha256"],
            schema_id=payload["schema_id"],
        )


def claim_metric_scope_policy_document() -> dict[str, Any]:
    return {
        "schema_id": CLAIM_METRIC_SCOPE_POLICY_SCHEMA_ID,
        "record_schema_id": CLAIM_METRIC_RECORD_SCHEMA_ID,
        "required_fields": list(CLAIM_METRIC_REQUIRED_FIELDS),
        "context_free_metric_language_allowed": False,
        "failure_denominator_required": True,
        "confidence_interval_required": True,
        "frozen_engine_commit_required": True,
        "source_artifact_identity_required": True,
        "claim_boundary_required": True,
        "repository_bundles_current_promoted_metric_record": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
    }


def require_claim_metric_record(payload: object) -> ClaimMetricRecord:
    if not isinstance(payload, Mapping):
        raise ClaimScopeError("claim metric record must be a mapping")
    return ClaimMetricRecord.from_mapping(payload)


def current_claim_scope_decision() -> dict[str, Any]:
    return {
        "policy": claim_metric_scope_policy_document(),
        "qualified_metric_record_present": False,
        "independent_metric_review_present": False,
        "public_holdout_evidence_present": False,
        "claim_promotion_allowed": False,
        "claim_safe": False,
        "blockers": [
            "scope_qualified_metric_record_not_bundled",
            "independent_metric_review_not_bundled",
            "public_holdout_evidence_not_bundled",
        ],
    }


__all__ = [
    "CLAIM_METRIC_RECORD_SCHEMA_ID",
    "CLAIM_METRIC_REQUIRED_FIELDS",
    "CLAIM_METRIC_SCOPE_POLICY_SCHEMA_ID",
    "ClaimMetricRecord",
    "ClaimScopeError",
    "claim_metric_scope_policy_document",
    "current_claim_scope_decision",
    "require_claim_metric_record",
]
