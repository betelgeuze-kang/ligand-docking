"""Signed, expected-context evidence contracts for Engine v2.

These contracts deliberately separate three questions:

* whether a metric is fully scoped and failure-inclusive;
* whether GitHub review evidence is bound to an externally supplied repository,
  pull-request head, ruleset, CODEOWNERS snapshot, reviewer directory, and
  required check set; and
* whether a capability has signed test and canonical-entrypoint execution
  evidence for one exact engine commit.

A verified receipt never grants scientific validation, benchmark validity,
product qualification, customer execution, or claim safety.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from .truthfulness import capability_truthfulness_snapshot


SCOPED_METRIC_EVIDENCE_V2_SCHEMA_ID = (
    "betelgeuze.engine_v2_scoped_metric_evidence/2.0.0"
)
RELEASE_REVIEW_ATTESTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_release_review_attestation/2.0.0"
)
RELEASE_REVIEW_VERIFICATION_V2_SCHEMA_ID = (
    "betelgeuze.engine_v2_release_review_verification/2.0.0"
)
EXECUTION_EVIDENCE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_execution_evidence_receipt/1.0.0"
)
EXECUTION_EVIDENCE_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_execution_evidence_verification/1.0.0"
)
EVIDENCE_BOUND_TRUTHFULNESS_SCHEMA_ID = (
    "betelgeuze.engine_v2_evidence_bound_truthfulness_snapshot/1.0.0"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/+@-]{1,256}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
_REVIEW_ROLES = frozenset(
    {"general", "codeowner", "security", "numerical_methods", "scientific"}
)
_CHANGE_CATEGORIES = frozenset(
    {"general", "security", "numerical_methods", "scientific", "packaging", "claim_policy"}
)


class EvidenceContractError(ValueError):
    """An evidence row is incomplete, cross-wired, unsigned, or contradictory."""


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
        raise EvidenceContractError("evidence payload is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise EvidenceContractError(f"{name} must be a lowercase SHA-256")
    return value


def _require_commit(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise EvidenceContractError(
            f"{name} must be a lowercase 40-character Git SHA"
        )
    return value


def _require_safe_id(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SAFE_ID_RE.fullmatch(value) is None:
        raise EvidenceContractError(f"{name} must be a safe identifier")
    return value


def _require_text(value: object, *, name: str, maximum: int = 2_000) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or "\x00" in value
    ):
        raise EvidenceContractError(f"{name} must be bounded non-empty text")
    return value.strip()


def _require_utc(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise EvidenceContractError(f"{name} must be second-resolution UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise EvidenceContractError(f"{name} must be valid UTC") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise EvidenceContractError(f"{name} is not canonical UTC")
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceContractError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise EvidenceContractError(f"{name} must be finite")
    return result


def _non_negative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise EvidenceContractError(f"{name} must be a non-negative integer")
    return value


def _positive_int(value: object, *, name: str) -> int:
    result = _non_negative_int(value, name=name)
    if result < 1:
        raise EvidenceContractError(f"{name} must be positive")
    return result


def _decode_signature(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise EvidenceContractError("signature_base64 must be non-empty text")
    try:
        signature = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise EvidenceContractError("signature_base64 is invalid") from exc
    if len(signature) != 64:
        raise EvidenceContractError("Ed25519 signature must contain 64 bytes")
    return signature


def _verify_ed25519(
    *,
    public_key_bytes: bytes,
    signature_base64: object,
    message: bytes,
) -> None:
    if not isinstance(public_key_bytes, bytes) or len(public_key_bytes) != 32:
        raise EvidenceContractError("trusted Ed25519 public key must contain 32 bytes")
    signature = _decode_signature(signature_base64)
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature, message)
    except InvalidSignature as exc:
        raise EvidenceContractError("evidence signature verification failed") from exc


@dataclass(frozen=True, slots=True)
class ScopedMetricEvidenceV2:
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
    confidence_level: float
    denominator_count: int
    success_count: int
    failure_count: int
    as_of_utc: str
    claim_boundary: str
    source_artifact_sha256: str
    evaluator_source_sha256: str
    metric_implementation_sha256: str
    protocol_sha256: str
    environment_fingerprint_sha256: str
    execution_receipt_sha256: str
    schema_id: str = SCOPED_METRIC_EVIDENCE_V2_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != SCOPED_METRIC_EVIDENCE_V2_SCHEMA_ID:
            raise EvidenceContractError("unsupported scoped metric evidence schema")
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
                self, name, _require_safe_id(getattr(self, name), name=name)
            )
        object.__setattr__(
            self, "engine_commit", _require_commit(self.engine_commit, name="engine_commit")
        )
        direction = str(self.metric_direction or "").lower()
        if direction not in {"minimize", "maximize"}:
            raise EvidenceContractError(
                "metric_direction must be minimize or maximize"
            )
        object.__setattr__(self, "metric_direction", direction)
        if self.unit is not None:
            object.__setattr__(self, "unit", _require_safe_id(self.unit, name="unit"))
        value = _finite(self.value, name="metric value")
        low = _finite(self.confidence_interval_low, name="confidence interval low")
        high = _finite(self.confidence_interval_high, name="confidence interval high")
        level = _finite(self.confidence_level, name="confidence level")
        if low > value or value > high:
            raise EvidenceContractError(
                "metric value must lie inside its confidence interval"
            )
        if not 0.0 < level < 1.0:
            raise EvidenceContractError("confidence level must be in (0,1)")
        denominator = _positive_int(self.denominator_count, name="denominator_count")
        successes = _non_negative_int(self.success_count, name="success_count")
        failures = _non_negative_int(self.failure_count, name="failure_count")
        if successes + failures != denominator:
            raise EvidenceContractError(
                "success_count plus failure_count must equal denominator_count"
            )
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "confidence_interval_low", low)
        object.__setattr__(self, "confidence_interval_high", high)
        object.__setattr__(self, "confidence_level", level)
        object.__setattr__(self, "denominator_count", denominator)
        object.__setattr__(self, "success_count", successes)
        object.__setattr__(self, "failure_count", failures)
        object.__setattr__(self, "as_of_utc", _require_utc(self.as_of_utc, name="as_of_utc"))
        object.__setattr__(
            self,
            "claim_boundary",
            _require_text(self.claim_boundary, name="claim_boundary"),
        )
        for name in (
            "source_artifact_sha256",
            "evaluator_source_sha256",
            "metric_implementation_sha256",
            "protocol_sha256",
            "environment_fingerprint_sha256",
            "execution_receipt_sha256",
        ):
            object.__setattr__(
                self, name, _require_sha256(getattr(self, name), name=name)
            )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
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
            "confidence_interval": {
                "low": self.confidence_interval_low,
                "high": self.confidence_interval_high,
                "level": self.confidence_level,
            },
            "counts": {
                "denominator": self.denominator_count,
                "success": self.success_count,
                "failure": self.failure_count,
            },
            "as_of_utc": self.as_of_utc,
            "claim_boundary": self.claim_boundary,
            "source_artifact_sha256": self.source_artifact_sha256,
            "evaluator_source_sha256": self.evaluator_source_sha256,
            "metric_implementation_sha256": self.metric_implementation_sha256,
            "protocol_sha256": self.protocol_sha256,
            "environment_fingerprint_sha256": self.environment_fingerprint_sha256,
            "execution_receipt_sha256": self.execution_receipt_sha256,
            "scientifically_validated": False,
            "claim_safe": False,
        }
        payload["evidence_sha256"] = _sha256(payload)
        return payload


def require_scoped_metric_evidence_v2(payload: object) -> ScopedMetricEvidenceV2:
    if not isinstance(payload, Mapping):
        raise EvidenceContractError("scoped metric evidence must be a mapping")
    expected = {
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
        "confidence_interval",
        "counts",
        "as_of_utc",
        "claim_boundary",
        "source_artifact_sha256",
        "evaluator_source_sha256",
        "metric_implementation_sha256",
        "protocol_sha256",
        "environment_fingerprint_sha256",
        "execution_receipt_sha256",
        "scientifically_validated",
        "claim_safe",
        "evidence_sha256",
    }
    if set(payload) != expected:
        raise EvidenceContractError(
            "scoped metric evidence fields are incomplete or unexpected"
        )
    if payload["scientifically_validated"] is not False or payload["claim_safe"] is not False:
        raise EvidenceContractError("metric evidence cannot promote claims")
    interval = payload["confidence_interval"]
    counts = payload["counts"]
    if not isinstance(interval, Mapping) or set(interval) != {"low", "high", "level"}:
        raise EvidenceContractError("confidence_interval fields are invalid")
    if not isinstance(counts, Mapping) or set(counts) != {"denominator", "success", "failure"}:
        raise EvidenceContractError("counts fields are invalid")
    projection = dict(payload)
    evidence_sha256 = projection.pop("evidence_sha256")
    if evidence_sha256 != _sha256(projection):
        raise EvidenceContractError("scoped metric evidence SHA-256 is invalid")
    row = ScopedMetricEvidenceV2(
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
        confidence_interval_low=interval["low"],
        confidence_interval_high=interval["high"],
        confidence_level=interval["level"],
        denominator_count=counts["denominator"],
        success_count=counts["success"],
        failure_count=counts["failure"],
        as_of_utc=payload["as_of_utc"],
        claim_boundary=payload["claim_boundary"],
        source_artifact_sha256=payload["source_artifact_sha256"],
        evaluator_source_sha256=payload["evaluator_source_sha256"],
        metric_implementation_sha256=payload["metric_implementation_sha256"],
        protocol_sha256=payload["protocol_sha256"],
        environment_fingerprint_sha256=payload["environment_fingerprint_sha256"],
        execution_receipt_sha256=payload["execution_receipt_sha256"],
        schema_id=payload["schema_id"],
    )
    if row.to_dict() != dict(payload):
        raise EvidenceContractError("scoped metric evidence is not canonical")
    return row


@dataclass(frozen=True, slots=True)
class TrustedReviewer:
    login: str
    user_id: int
    identity_sha256: str
    roles: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "login", _require_safe_id(self.login, name="reviewer login"))
        object.__setattr__(self, "user_id", _positive_int(self.user_id, name="reviewer user_id"))
        object.__setattr__(
            self,
            "identity_sha256",
            _require_sha256(self.identity_sha256, name="reviewer identity"),
        )
        roles = tuple(sorted(set(self.roles)))
        if not roles or any(role not in _REVIEW_ROLES for role in roles):
            raise EvidenceContractError("trusted reviewer roles are invalid")
        object.__setattr__(self, "roles", roles)


@dataclass(frozen=True, slots=True)
class ReviewEvidenceExpectation:
    repository_full_name: str
    pull_request_number: int
    pull_request_head_sha: str
    pull_request_author_identity_sha256: str
    ruleset_sha256: str
    codeowners_sha256: str
    required_check_names: tuple[str, ...]
    required_change_categories: tuple[str, ...]
    trusted_reviewers: Mapping[str, TrustedReviewer]
    trusted_attestor_keys: Mapping[str, bytes]

    def __post_init__(self) -> None:
        if _REPOSITORY_RE.fullmatch(str(self.repository_full_name or "")) is None:
            raise EvidenceContractError("repository_full_name must be owner/name")
        object.__setattr__(
            self,
            "pull_request_number",
            _positive_int(self.pull_request_number, name="pull_request_number"),
        )
        object.__setattr__(
            self,
            "pull_request_head_sha",
            _require_commit(self.pull_request_head_sha, name="pull-request head"),
        )
        object.__setattr__(
            self,
            "pull_request_author_identity_sha256",
            _require_sha256(
                self.pull_request_author_identity_sha256,
                name="pull-request author identity",
            ),
        )
        object.__setattr__(self, "ruleset_sha256", _require_sha256(self.ruleset_sha256, name="ruleset"))
        object.__setattr__(self, "codeowners_sha256", _require_sha256(self.codeowners_sha256, name="CODEOWNERS"))
        checks = tuple(sorted(set(_require_text(value, name="required check name") for value in self.required_check_names)))
        if not checks or len(checks) != len(self.required_check_names):
            raise EvidenceContractError("required check names must be non-empty and unique")
        object.__setattr__(self, "required_check_names", checks)
        categories = tuple(sorted(set(self.required_change_categories)))
        if not categories or any(category not in _CHANGE_CATEGORIES for category in categories):
            raise EvidenceContractError("required change categories are invalid")
        object.__setattr__(self, "required_change_categories", categories)
        reviewers = dict(self.trusted_reviewers)
        if not reviewers or any(login != reviewer.login for login, reviewer in reviewers.items()):
            raise EvidenceContractError("trusted reviewer directory is invalid")
        object.__setattr__(self, "trusted_reviewers", reviewers)
        keys = dict(self.trusted_attestor_keys)
        if not keys or any(not isinstance(key, bytes) or len(key) != 32 for key in keys.values()):
            raise EvidenceContractError("trusted attestor keys are invalid")
        object.__setattr__(self, "trusted_attestor_keys", keys)


def _review_unsigned_projection(payload: Mapping[str, object]) -> dict[str, object]:
    projection = dict(payload)
    projection.pop("signature_base64", None)
    return projection


def canonical_release_review_attestation_bytes(payload: Mapping[str, object]) -> bytes:
    return _canonical_bytes(_review_unsigned_projection(payload))


def verify_release_review_attestation(
    payload: object,
    *,
    expected: ReviewEvidenceExpectation,
) -> dict[str, object]:
    required_fields = {
        "schema_id",
        "repository_full_name",
        "pull_request_number",
        "pull_request_head_sha",
        "pull_request_author_identity_sha256",
        "ruleset_id",
        "ruleset_sha256",
        "codeowners_sha256",
        "no_admin_bypass",
        "stale_approval_dismissal_enabled",
        "code_owner_review_required",
        "unresolved_review_thread_count",
        "head_up_to_date",
        "change_categories",
        "review_submissions",
        "required_checks",
        "evidence_generated_at_utc",
        "attestor_key_id",
        "signature_base64",
    }
    if not isinstance(payload, Mapping) or set(payload) != required_fields:
        raise EvidenceContractError("release review attestation fields are invalid")
    if payload["schema_id"] != RELEASE_REVIEW_ATTESTATION_SCHEMA_ID:
        raise EvidenceContractError("unsupported release review attestation schema")
    for observed, wanted, name in (
        (payload["repository_full_name"], expected.repository_full_name, "repository"),
        (payload["pull_request_number"], expected.pull_request_number, "pull request"),
        (payload["pull_request_head_sha"], expected.pull_request_head_sha, "head SHA"),
        (
            payload["pull_request_author_identity_sha256"],
            expected.pull_request_author_identity_sha256,
            "author identity",
        ),
        (payload["ruleset_sha256"], expected.ruleset_sha256, "ruleset"),
        (payload["codeowners_sha256"], expected.codeowners_sha256, "CODEOWNERS"),
    ):
        if observed != wanted:
            raise EvidenceContractError(f"release review attestation {name} is cross-wired")
    _require_safe_id(payload["ruleset_id"], name="ruleset_id")
    if payload["no_admin_bypass"] is not True:
        raise EvidenceContractError("no administrator bypass is required")
    if payload["stale_approval_dismissal_enabled"] is not True:
        raise EvidenceContractError("stale approval dismissal is required")
    if payload["code_owner_review_required"] is not True:
        raise EvidenceContractError("CODEOWNER review is required")
    if payload["unresolved_review_thread_count"] != 0:
        raise EvidenceContractError("all review threads must be resolved")
    if payload["head_up_to_date"] is not True:
        raise EvidenceContractError("pull-request head must be up to date")
    categories = payload["change_categories"]
    if not isinstance(categories, list) or tuple(categories) != expected.required_change_categories:
        raise EvidenceContractError("change categories do not match expected context")

    reviews_source = payload["review_submissions"]
    if not isinstance(reviews_source, list) or not reviews_source:
        raise EvidenceContractError("review submissions are required")
    roles: set[str] = set()
    submission_ids: list[int] = []
    canonical_reviews: list[dict[str, object]] = []
    for review in reviews_source:
        if not isinstance(review, Mapping) or set(review) != {
            "submission_id",
            "reviewer_login",
            "reviewer_user_id",
            "reviewer_identity_sha256",
            "role",
            "state",
            "submitted_at_utc",
            "dismissed",
        }:
            raise EvidenceContractError("review submission fields are invalid")
        submission_id = _positive_int(review["submission_id"], name="submission_id")
        login = _require_safe_id(review["reviewer_login"], name="reviewer login")
        trusted = expected.trusted_reviewers.get(login)
        if trusted is None:
            raise EvidenceContractError("reviewer is absent from trusted directory")
        if review["reviewer_user_id"] != trusted.user_id:
            raise EvidenceContractError("reviewer user ID is cross-wired")
        if review["reviewer_identity_sha256"] != trusted.identity_sha256:
            raise EvidenceContractError("reviewer identity is cross-wired")
        if trusted.identity_sha256 == expected.pull_request_author_identity_sha256:
            raise EvidenceContractError("pull-request author cannot approve the change")
        role = review["role"]
        if role not in trusted.roles:
            raise EvidenceContractError("reviewer is not trusted for the declared role")
        if review["state"] != "APPROVED" or review["dismissed"] is not False:
            raise EvidenceContractError("review submission must be a current approval")
        roles.add(str(role))
        submission_ids.append(submission_id)
        canonical_reviews.append(
            {
                "submission_id": submission_id,
                "reviewer_login": login,
                "reviewer_user_id": trusted.user_id,
                "reviewer_identity_sha256": trusted.identity_sha256,
                "role": role,
                "state": "APPROVED",
                "submitted_at_utc": _require_utc(
                    review["submitted_at_utc"], name="review submitted_at_utc"
                ),
                "dismissed": False,
            }
        )
    if submission_ids != sorted(submission_ids) or len(submission_ids) != len(set(submission_ids)):
        raise EvidenceContractError("review submissions must be uniquely sorted")
    required_roles = {"codeowner"}
    required_roles.update(
        category
        for category in expected.required_change_categories
        if category in {"security", "numerical_methods", "scientific"}
    )
    if not required_roles.issubset(roles):
        raise EvidenceContractError("required reviewer roles are missing")

    checks_source = payload["required_checks"]
    if not isinstance(checks_source, list) or not checks_source:
        raise EvidenceContractError("required checks are missing")
    canonical_checks: list[dict[str, object]] = []
    check_names: list[str] = []
    for check in checks_source:
        if not isinstance(check, Mapping) or set(check) != {
            "name",
            "check_run_id",
            "workflow_source_sha256",
            "conclusion",
            "completed_at_utc",
        }:
            raise EvidenceContractError("required check fields are invalid")
        name = _require_text(check["name"], name="required check name")
        if check["conclusion"] != "success":
            raise EvidenceContractError("every required check must succeed")
        check_names.append(name)
        canonical_checks.append(
            {
                "name": name,
                "check_run_id": _positive_int(check["check_run_id"], name="check_run_id"),
                "workflow_source_sha256": _require_sha256(
                    check["workflow_source_sha256"], name="workflow source"
                ),
                "conclusion": "success",
                "completed_at_utc": _require_utc(
                    check["completed_at_utc"], name="check completed_at_utc"
                ),
            }
        )
    if tuple(check_names) != expected.required_check_names:
        raise EvidenceContractError("required check set does not match expected context")
    if len(check_names) != len(set(check_names)):
        raise EvidenceContractError("required checks must be unique")

    generated_at = _require_utc(
        payload["evidence_generated_at_utc"], name="evidence_generated_at_utc"
    )
    key_id = _require_safe_id(payload["attestor_key_id"], name="attestor key ID")
    public_key = expected.trusted_attestor_keys.get(key_id)
    if public_key is None:
        raise EvidenceContractError("attestor key is not trusted")
    unsigned = _review_unsigned_projection(payload)
    expected_unsigned = {
        "schema_id": RELEASE_REVIEW_ATTESTATION_SCHEMA_ID,
        "repository_full_name": expected.repository_full_name,
        "pull_request_number": expected.pull_request_number,
        "pull_request_head_sha": expected.pull_request_head_sha,
        "pull_request_author_identity_sha256": expected.pull_request_author_identity_sha256,
        "ruleset_id": payload["ruleset_id"],
        "ruleset_sha256": expected.ruleset_sha256,
        "codeowners_sha256": expected.codeowners_sha256,
        "no_admin_bypass": True,
        "stale_approval_dismissal_enabled": True,
        "code_owner_review_required": True,
        "unresolved_review_thread_count": 0,
        "head_up_to_date": True,
        "change_categories": list(expected.required_change_categories),
        "review_submissions": canonical_reviews,
        "required_checks": canonical_checks,
        "evidence_generated_at_utc": generated_at,
        "attestor_key_id": key_id,
    }
    if unsigned != expected_unsigned:
        raise EvidenceContractError("release review attestation is not canonical")
    _verify_ed25519(
        public_key_bytes=public_key,
        signature_base64=payload["signature_base64"],
        message=_canonical_bytes(unsigned),
    )
    return {
        "schema_id": RELEASE_REVIEW_VERIFICATION_V2_SCHEMA_ID,
        "attestation_sha256": _sha256(dict(payload)),
        "expected_context_verified": True,
        "signature_verified": True,
        "reviewer_directory_verified": True,
        "required_checks_verified": True,
        "operational_review_evidence_verified": True,
        "scientific_validation_granted": False,
        "benchmark_validation_granted": False,
        "product_qualification_granted": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


@dataclass(frozen=True, slots=True)
class ExecutionEvidenceExpectation:
    capability_id: str
    engine_commit: str
    source_manifest_sha256: str
    test_manifest_sha256: str
    canonical_argv: tuple[str, ...]
    entrypoint_source_sha256: str
    environment_fingerprint_sha256: str
    trusted_attestor_keys: Mapping[str, bytes]

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", _require_safe_id(self.capability_id, name="capability_id"))
        object.__setattr__(self, "engine_commit", _require_commit(self.engine_commit, name="engine_commit"))
        for name in (
            "source_manifest_sha256",
            "test_manifest_sha256",
            "entrypoint_source_sha256",
            "environment_fingerprint_sha256",
        ):
            object.__setattr__(self, name, _require_sha256(getattr(self, name), name=name))
        argv = tuple(_require_text(value, name="canonical argv item") for value in self.canonical_argv)
        if not argv:
            raise EvidenceContractError("canonical_argv must be non-empty")
        object.__setattr__(self, "canonical_argv", argv)
        keys = dict(self.trusted_attestor_keys)
        if not keys or any(not isinstance(key, bytes) or len(key) != 32 for key in keys.values()):
            raise EvidenceContractError("trusted attestor keys are invalid")
        object.__setattr__(self, "trusted_attestor_keys", keys)


def _execution_unsigned_projection(payload: Mapping[str, object]) -> dict[str, object]:
    projection = dict(payload)
    projection.pop("signature_base64", None)
    return projection


def canonical_execution_evidence_bytes(payload: Mapping[str, object]) -> bytes:
    return _canonical_bytes(_execution_unsigned_projection(payload))


def verify_execution_evidence_receipt(
    payload: object,
    *,
    expected: ExecutionEvidenceExpectation,
) -> dict[str, object]:
    fields = {
        "schema_id",
        "capability_id",
        "engine_commit",
        "source_manifest_sha256",
        "test_manifest_sha256",
        "test_count",
        "failure_count",
        "canonical_argv",
        "entrypoint_source_sha256",
        "entrypoint_exit_code",
        "environment_fingerprint_sha256",
        "completed_at_utc",
        "attestor_key_id",
        "signature_base64",
    }
    if not isinstance(payload, Mapping) or set(payload) != fields:
        raise EvidenceContractError("execution evidence receipt fields are invalid")
    if payload["schema_id"] != EXECUTION_EVIDENCE_RECEIPT_SCHEMA_ID:
        raise EvidenceContractError("unsupported execution evidence schema")
    for observed, wanted, name in (
        (payload["capability_id"], expected.capability_id, "capability"),
        (payload["engine_commit"], expected.engine_commit, "engine commit"),
        (payload["source_manifest_sha256"], expected.source_manifest_sha256, "source manifest"),
        (payload["test_manifest_sha256"], expected.test_manifest_sha256, "test manifest"),
        (payload["entrypoint_source_sha256"], expected.entrypoint_source_sha256, "entrypoint source"),
        (
            payload["environment_fingerprint_sha256"],
            expected.environment_fingerprint_sha256,
            "environment fingerprint",
        ),
    ):
        if observed != wanted:
            raise EvidenceContractError(f"execution evidence {name} is cross-wired")
    test_count = _positive_int(payload["test_count"], name="test_count")
    failure_count = _non_negative_int(payload["failure_count"], name="failure_count")
    if failure_count != 0:
        raise EvidenceContractError("execution evidence contains test failures")
    argv = payload["canonical_argv"]
    if not isinstance(argv, list) or tuple(argv) != expected.canonical_argv:
        raise EvidenceContractError("canonical argv does not match expected context")
    if payload["entrypoint_exit_code"] != 0:
        raise EvidenceContractError("canonical entrypoint did not exit successfully")
    completed_at = _require_utc(payload["completed_at_utc"], name="completed_at_utc")
    key_id = _require_safe_id(payload["attestor_key_id"], name="attestor key ID")
    public_key = expected.trusted_attestor_keys.get(key_id)
    if public_key is None:
        raise EvidenceContractError("execution attestor key is not trusted")
    unsigned = _execution_unsigned_projection(payload)
    expected_unsigned = {
        "schema_id": EXECUTION_EVIDENCE_RECEIPT_SCHEMA_ID,
        "capability_id": expected.capability_id,
        "engine_commit": expected.engine_commit,
        "source_manifest_sha256": expected.source_manifest_sha256,
        "test_manifest_sha256": expected.test_manifest_sha256,
        "test_count": test_count,
        "failure_count": 0,
        "canonical_argv": list(expected.canonical_argv),
        "entrypoint_source_sha256": expected.entrypoint_source_sha256,
        "entrypoint_exit_code": 0,
        "environment_fingerprint_sha256": expected.environment_fingerprint_sha256,
        "completed_at_utc": completed_at,
        "attestor_key_id": key_id,
    }
    if unsigned != expected_unsigned:
        raise EvidenceContractError("execution evidence receipt is not canonical")
    _verify_ed25519(
        public_key_bytes=public_key,
        signature_base64=payload["signature_base64"],
        message=_canonical_bytes(unsigned),
    )
    return {
        "schema_id": EXECUTION_EVIDENCE_VERIFICATION_SCHEMA_ID,
        "capability_id": expected.capability_id,
        "engine_commit": expected.engine_commit,
        "evidence_sha256": _sha256(dict(payload)),
        "test_count": test_count,
        "failure_count": 0,
        "component_tested": True,
        "canonical_entrypoint_wired": True,
        "signature_verified": True,
        "production_execution_authorized": False,
        "production_result_receipt_present": False,
        "independent_result_reviewed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def evidence_bound_capability_snapshot(
    execution_verifications: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Derive tested/wired state only from verified execution receipts."""

    base = capability_truthfulness_snapshot()
    verified: dict[str, Mapping[str, object]] = {}
    for verification in execution_verifications:
        if not isinstance(verification, Mapping) or verification.get("schema_id") != EXECUTION_EVIDENCE_VERIFICATION_SCHEMA_ID:
            raise EvidenceContractError("execution verification is invalid")
        capability_id = _require_safe_id(
            verification.get("capability_id"), name="verified capability_id"
        )
        if capability_id in verified:
            raise EvidenceContractError("duplicate capability execution evidence")
        if verification.get("signature_verified") is not True:
            raise EvidenceContractError("execution verification is not signed")
        verified[capability_id] = verification
    rows: dict[str, object] = {}
    for capability_id, source_row in base["capabilities"].items():
        receipt = verified.get(capability_id)
        rows[capability_id] = {
            **dict(source_row),
            "source_declared_component_tested": source_row["component_tested"],
            "source_declared_canonical_entrypoint_wired": source_row[
                "canonical_entrypoint_wired"
            ],
            "component_tested": bool(receipt and receipt["component_tested"] is True),
            "canonical_entrypoint_wired": bool(
                receipt and receipt["canonical_entrypoint_wired"] is True
            ),
            "execution_evidence_sha256": (
                "" if receipt is None else str(receipt["evidence_sha256"])
            ),
        }
    payload: dict[str, object] = {
        "schema_id": EVIDENCE_BOUND_TRUTHFULNESS_SCHEMA_ID,
        "base_snapshot_sha256": _sha256(base),
        "verified_execution_evidence_count": len(verified),
        "verified_execution_evidence_sha256s": sorted(
            str(row["evidence_sha256"]) for row in verified.values()
        ),
        "capabilities": rows,
        "production_execution_authorized": False,
        "production_result_receipt_present": False,
        "independent_result_reviewed": False,
        "scientific_validity_green": False,
        "benchmark_validity_green": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }
    payload["snapshot_sha256"] = _sha256(payload)
    return payload


__all__ = [
    "EVIDENCE_BOUND_TRUTHFULNESS_SCHEMA_ID",
    "EXECUTION_EVIDENCE_RECEIPT_SCHEMA_ID",
    "EXECUTION_EVIDENCE_VERIFICATION_SCHEMA_ID",
    "RELEASE_REVIEW_ATTESTATION_SCHEMA_ID",
    "RELEASE_REVIEW_VERIFICATION_V2_SCHEMA_ID",
    "SCOPED_METRIC_EVIDENCE_V2_SCHEMA_ID",
    "EvidenceContractError",
    "ExecutionEvidenceExpectation",
    "ReviewEvidenceExpectation",
    "ScopedMetricEvidenceV2",
    "TrustedReviewer",
    "canonical_execution_evidence_bytes",
    "canonical_release_review_attestation_bytes",
    "evidence_bound_capability_snapshot",
    "require_scoped_metric_evidence_v2",
    "verify_execution_evidence_receipt",
    "verify_release_review_attestation",
]
