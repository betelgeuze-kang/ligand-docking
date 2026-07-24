"""Fail-closed capability, metric, and review-evidence truthfulness contracts.

This module does not replace the frozen capability ledger.  It derives a
current lifecycle view that separates implementation, tested components,
canonical process wiring, production authorization, durable result evidence,
independent result review, scientific validation, benchmark validation,
product qualification, and customer enablement.

It also defines exact row contracts for scoped scientific metrics and external
GitHub review/ruleset evidence.  Passing an operational review contract never
promotes a scientific, benchmark, product, or customer claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Mapping

from .capabilities import (
    CAPABILITY_SCHEMA_VERSION,
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
    ENGINE_ID,
    IMPLEMENTATION_STAGE,
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID,
    capability_snapshot,
)


TRUTHFULNESS_SCHEMA_VERSION = 1
TRUTHFULNESS_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_truthfulness_policy/1.0.0"
)
TRUTHFULNESS_SNAPSHOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_capability_truthfulness_snapshot/1.0.0"
)
SCOPED_METRIC_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_scoped_metric_evidence/1.0.0"
)
RELEASE_REVIEW_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_release_review_evidence/1.0.0"
)
RELEASE_REVIEW_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_release_review_verification/1.0.0"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/+-]{1,256}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)

_CANONICAL_ENTRYPOINT_APPLICABLE = (
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID,
)
_CANONICAL_ENTRYPOINT_WIRED = (
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
)
_RESULT_RECEIPT_REQUIRED = (
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
)
_INDEPENDENT_RESULT_REVIEW_REQUIRED = (
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID,
)
_SUPERSEDED_BLOCKERS: dict[str, tuple[str, ...]] = {
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID: (
        "validation_runner_not_implemented",
        "result_receipt_writer_not_implemented",
    ),
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID: (
        "validation_runner_not_implemented",
        "result_receipt_writer_not_implemented",
    ),
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID: (
        "symmetry_mapping_materializer_not_implemented",
        "reference_ligand_match_materializer_not_implemented",
    ),
}

_REVIEW_ROLES = frozenset(
    {
        "general",
        "codeowner",
        "security",
        "numerical_methods",
        "scientific",
    }
)
_CHANGE_CATEGORIES = frozenset(
    {
        "general",
        "security",
        "numerical_methods",
        "scientific",
        "packaging",
        "claim_policy",
    }
)


class TruthfulnessContractError(ValueError):
    """A lifecycle or evidence payload contradicts the fail-closed policy."""


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
        raise TruthfulnessContractError(
            "truthfulness payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise TruthfulnessContractError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_commit(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise TruthfulnessContractError(
            f"{name} must be a lowercase 40-character Git SHA"
        )
    return value


def _require_safe_id(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SAFE_ID_RE.fullmatch(value) is None:
        raise TruthfulnessContractError(
            f"{name} must be a non-empty safe identifier"
        )
    return value


def _require_text(value: object, *, name: str, maximum: int = 2_000) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or "\x00" in value
    ):
        raise TruthfulnessContractError(
            f"{name} must be bounded non-empty text"
        )
    return value.strip()


def _require_utc(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise TruthfulnessContractError(
            f"{name} must be second-resolution UTC"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise TruthfulnessContractError(
            f"{name} must be valid second-resolution UTC"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise TruthfulnessContractError(
            f"{name} is not canonical UTC"
        )
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TruthfulnessContractError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise TruthfulnessContractError(f"{name} must be finite")
    return result


def truthfulness_policy_document() -> dict[str, object]:
    """Return the small static policy used to derive the full lifecycle view."""

    return {
        "schema_id": TRUTHFULNESS_POLICY_SCHEMA_ID,
        "schema_version": TRUTHFULNESS_SCHEMA_VERSION,
        "base_capability_schema_version": CAPABILITY_SCHEMA_VERSION,
        "canonical_entrypoint_applicable_capability_ids": list(
            _CANONICAL_ENTRYPOINT_APPLICABLE
        ),
        "canonical_entrypoint_wired_capability_ids": list(
            _CANONICAL_ENTRYPOINT_WIRED
        ),
        "production_result_receipt_required_capability_ids": list(
            _RESULT_RECEIPT_REQUIRED
        ),
        "independent_result_review_required_capability_ids": list(
            _INDEPENDENT_RESULT_REVIEW_REQUIRED
        ),
        "superseded_blockers": {
            capability_id: list(blockers)
            for capability_id, blockers in sorted(_SUPERSEDED_BLOCKERS.items())
        },
        "principles": {
            "component_implementation_is_not_production_authorization": True,
            "canonical_entrypoint_wiring_is_not_result_evidence": True,
            "result_receipt_is_not_independent_result_review": True,
            "operational_review_is_not_scientific_validation": True,
            "public_protocol_materialization_is_not_benchmark_execution": True,
            "all_claim_promotion_requires_external_evidence": True,
        },
    }


def require_truthfulness_policy_document(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise TruthfulnessContractError(
            "truthfulness policy document must be a mapping"
        )
    expected = truthfulness_policy_document()
    if dict(payload) != expected:
        raise TruthfulnessContractError(
            "truthfulness policy document drifted from executable policy"
        )
    return payload


def _lifecycle_row(
    capability_id: str,
    base_row: Mapping[str, object],
) -> dict[str, object]:
    base_blockers = tuple(str(value) for value in base_row.get("blockers", ()))
    superseded = _SUPERSEDED_BLOCKERS.get(capability_id, ())
    current_blockers = tuple(
        blocker for blocker in base_blockers if blocker not in set(superseded)
    )
    applicable = capability_id in _CANONICAL_ENTRYPOINT_APPLICABLE
    wired = capability_id in _CANONICAL_ENTRYPOINT_WIRED
    receipt_required = capability_id in _RESULT_RECEIPT_REQUIRED
    result_review_required = capability_id in _INDEPENDENT_RESULT_REVIEW_REQUIRED
    implemented = base_row.get("implemented") is True
    reference_contract_ready = base_row.get("reference_contract_ready") is True

    row = {
        "current_state": str(base_row.get("current_state") or ""),
        "implemented": implemented,
        "component_tested": bool(implemented and reference_contract_ready),
        "canonical_entrypoint_applicable": applicable,
        "canonical_entrypoint_wired": wired,
        "internal_reference_execution_enabled": (
            base_row.get("internal_reference_execution_enabled") is True
        ),
        "production_execution_authorized": False,
        "production_result_receipt_required": receipt_required,
        "production_result_receipt_present": False,
        "independent_result_review_required": result_review_required,
        "independent_result_reviewed": False,
        "calibrated": base_row.get("calibrated") is True,
        "scientifically_validated": (
            base_row.get("scientifically_validated") is True
        ),
        "public_evidence_ready": (
            base_row.get("public_evidence_ready") is True
        ),
        "benchmark_validated": base_row.get("benchmark_validated") is True,
        "product_qualified": base_row.get("product_qualified") is True,
        "customer_execution_enabled": (
            base_row.get("customer_execution_enabled") is True
        ),
        "claim_safe": base_row.get("claim_safe") is True,
        "current_blockers": list(current_blockers),
        "superseded_blockers": list(superseded),
        "base_blocker_source": str(base_row.get("blocker_source") or ""),
    }
    _require_lifecycle_row(capability_id, row)
    return row


def _require_lifecycle_row(
    capability_id: str,
    row: Mapping[str, object],
) -> None:
    if row["canonical_entrypoint_wired"] and not row[
        "canonical_entrypoint_applicable"
    ]:
        raise TruthfulnessContractError(
            f"{capability_id} wires a non-applicable canonical entrypoint"
        )
    if row["production_result_receipt_present"] and not row[
        "production_execution_authorized"
    ]:
        raise TruthfulnessContractError(
            f"{capability_id} has a result receipt without authorized execution"
        )
    if row["independent_result_reviewed"] and not row[
        "production_result_receipt_present"
    ]:
        raise TruthfulnessContractError(
            f"{capability_id} claims result review without a production receipt"
        )
    if row["customer_execution_enabled"] and not row["product_qualified"]:
        raise TruthfulnessContractError(
            f"{capability_id} enables customers before product qualification"
        )
    if row["claim_safe"] and not all(
        row[name]
        for name in (
            "scientifically_validated",
            "benchmark_validated",
            "product_qualified",
            "customer_execution_enabled",
        )
    ):
        raise TruthfulnessContractError(
            f"{capability_id} is claim-safe without all promotion evidence"
        )
    if not row["implemented"] and row["component_tested"]:
        raise TruthfulnessContractError(
            f"{capability_id} tests a component that is not implemented"
        )


def capability_truthfulness_snapshot() -> dict[str, object]:
    """Derive the current lifecycle state without mutating frozen base records."""

    base = capability_snapshot()
    if base.get("schema_version") != CAPABILITY_SCHEMA_VERSION:
        raise TruthfulnessContractError(
            "base capability schema version drifted"
        )
    base_capabilities = base.get("capabilities")
    if not isinstance(base_capabilities, Mapping) or not base_capabilities:
        raise TruthfulnessContractError(
            "base capability snapshot has no capabilities"
        )
    rows = {
        str(capability_id): _lifecycle_row(str(capability_id), base_row)
        for capability_id, base_row in sorted(base_capabilities.items())
        if isinstance(base_row, Mapping)
    }
    if len(rows) != len(base_capabilities):
        raise TruthfulnessContractError(
            "base capability rows are not mappings"
        )
    return {
        "schema_id": TRUTHFULNESS_SNAPSHOT_SCHEMA_ID,
        "schema_version": TRUTHFULNESS_SCHEMA_VERSION,
        "base_capability_schema_version": CAPABILITY_SCHEMA_VERSION,
        "engine_id": ENGINE_ID,
        "implementation_stage": IMPLEMENTATION_STAGE,
        "policy_sha256": _sha256(truthfulness_policy_document()),
        "claim_policy": {
            "production_execution_authorized": False,
            "production_result_receipts_present": False,
            "independent_result_review_complete": False,
            "scientific_validity_green": False,
            "benchmark_validity_green": False,
            "product_qualification_green": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        },
        "capabilities": rows,
    }


def require_capability_truthfulness_snapshot(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise TruthfulnessContractError(
            "capability truthfulness snapshot must be a mapping"
        )
    expected = capability_truthfulness_snapshot()
    if dict(payload) != expected:
        raise TruthfulnessContractError(
            "capability truthfulness snapshot drifted from executable state"
        )
    return payload


@dataclass(frozen=True, slots=True)
class ScopedMetricEvidence:
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
    value: float
    confidence_interval_low: float
    confidence_interval_high: float
    confidence_level: float
    failure_denominator: int
    as_of_utc: str
    claim_boundary: str
    schema_id: str = SCOPED_METRIC_EVIDENCE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != SCOPED_METRIC_EVIDENCE_SCHEMA_ID:
            raise TruthfulnessContractError(
                "unsupported scoped metric evidence schema"
            )
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
                _require_safe_id(getattr(self, name), name=name),
            )
        object.__setattr__(
            self,
            "engine_commit",
            _require_commit(self.engine_commit, name="engine_commit"),
        )
        value = _finite(self.value, name="metric value")
        low = _finite(
            self.confidence_interval_low,
            name="confidence interval low",
        )
        high = _finite(
            self.confidence_interval_high,
            name="confidence interval high",
        )
        level = _finite(self.confidence_level, name="confidence level")
        if low > value or value > high:
            raise TruthfulnessContractError(
                "metric value must lie inside its confidence interval"
            )
        if not 0.0 < level < 1.0:
            raise TruthfulnessContractError(
                "confidence level must be in (0,1)"
            )
        denominator = self.failure_denominator
        if type(denominator) is not int or denominator < 1:
            raise TruthfulnessContractError(
                "failure_denominator must be a positive integer"
            )
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "confidence_interval_low", low)
        object.__setattr__(self, "confidence_interval_high", high)
        object.__setattr__(self, "confidence_level", level)
        object.__setattr__(
            self,
            "as_of_utc",
            _require_utc(self.as_of_utc, name="as_of_utc"),
        )
        object.__setattr__(
            self,
            "claim_boundary",
            _require_text(self.claim_boundary, name="claim_boundary"),
        )

    def to_dict(self) -> dict[str, object]:
        payload = {
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
            "value": self.value,
            "confidence_interval": {
                "low": self.confidence_interval_low,
                "high": self.confidence_interval_high,
                "level": self.confidence_level,
            },
            "failure_denominator": self.failure_denominator,
            "as_of_utc": self.as_of_utc,
            "claim_boundary": self.claim_boundary,
        }
        payload["evidence_sha256"] = _sha256(payload)
        return payload


def require_scoped_metric_evidence_row(payload: object) -> ScopedMetricEvidence:
    if not isinstance(payload, Mapping):
        raise TruthfulnessContractError(
            "scoped metric evidence must be a mapping"
        )
    expected_fields = {
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
        "value",
        "confidence_interval",
        "failure_denominator",
        "as_of_utc",
        "claim_boundary",
        "evidence_sha256",
    }
    if set(payload) != expected_fields:
        raise TruthfulnessContractError(
            "scoped metric evidence fields are incomplete or unexpected"
        )
    interval = payload.get("confidence_interval")
    if not isinstance(interval, Mapping) or set(interval) != {
        "low",
        "high",
        "level",
    }:
        raise TruthfulnessContractError(
            "confidence_interval must contain low, high, and level"
        )
    projection = dict(payload)
    evidence_sha256 = projection.pop("evidence_sha256")
    if evidence_sha256 != _sha256(projection):
        raise TruthfulnessContractError(
            "scoped metric evidence SHA-256 is invalid"
        )
    row = ScopedMetricEvidence(
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
        value=payload["value"],
        confidence_interval_low=interval["low"],
        confidence_interval_high=interval["high"],
        confidence_level=interval["level"],
        failure_denominator=payload["failure_denominator"],
        as_of_utc=payload["as_of_utc"],
        claim_boundary=payload["claim_boundary"],
        schema_id=payload["schema_id"],
    )
    if row.to_dict() != dict(payload):
        raise TruthfulnessContractError(
            "scoped metric evidence is not canonical"
        )
    return row


def _require_review_submission(
    payload: object,
    *,
    author_identity_sha256: str,
) -> dict[str, object]:
    if not isinstance(payload, Mapping) or set(payload) != {
        "submission_id",
        "reviewer_identity_sha256",
        "role",
        "state",
        "submitted_at_utc",
        "dismissed",
    }:
        raise TruthfulnessContractError(
            "review submission fields are incomplete or unexpected"
        )
    submission_id = _require_safe_id(
        payload["submission_id"],
        name="review submission id",
    )
    reviewer = _require_sha256(
        payload["reviewer_identity_sha256"],
        name="reviewer identity",
    )
    if reviewer == author_identity_sha256:
        raise TruthfulnessContractError(
            "pull-request author cannot satisfy independent review"
        )
    role = payload["role"]
    if role not in _REVIEW_ROLES:
        raise TruthfulnessContractError("review role is unsupported")
    if payload["state"] != "APPROVED" or payload["dismissed"] is not False:
        raise TruthfulnessContractError(
            "review submission must be a current approval"
        )
    return {
        "submission_id": submission_id,
        "reviewer_identity_sha256": reviewer,
        "role": role,
        "state": "APPROVED",
        "submitted_at_utc": _require_utc(
            payload["submitted_at_utc"],
            name="review submitted_at_utc",
        ),
        "dismissed": False,
    }


def _require_check(payload: object) -> dict[str, object]:
    if not isinstance(payload, Mapping) or set(payload) != {
        "name",
        "conclusion",
        "completed_at_utc",
    }:
        raise TruthfulnessContractError(
            "required check fields are incomplete or unexpected"
        )
    if payload["conclusion"] != "success":
        raise TruthfulnessContractError(
            "every required check must conclude success"
        )
    return {
        "name": _require_text(payload["name"], name="required check name"),
        "conclusion": "success",
        "completed_at_utc": _require_utc(
            payload["completed_at_utc"],
            name="required check completed_at_utc",
        ),
    }


def verify_release_review_evidence(payload: object) -> dict[str, object]:
    """Verify external operational review evidence without granting science claims."""

    if not isinstance(payload, Mapping) or set(payload) != {
        "schema_id",
        "repository_full_name",
        "pull_request_number",
        "pull_request_head_sha",
        "pull_request_author_identity_sha256",
        "ruleset_id",
        "ruleset_sha256",
        "no_admin_bypass",
        "stale_approval_dismissal_enabled",
        "code_owner_review_required",
        "unresolved_review_thread_count",
        "head_up_to_date",
        "change_categories",
        "review_submissions",
        "required_checks",
        "evidence_generated_at_utc",
    }:
        raise TruthfulnessContractError(
            "release review evidence fields are incomplete or unexpected"
        )
    if payload["schema_id"] != RELEASE_REVIEW_EVIDENCE_SCHEMA_ID:
        raise TruthfulnessContractError(
            "unsupported release review evidence schema"
        )
    repository = payload["repository_full_name"]
    if not isinstance(repository, str) or _REPOSITORY_RE.fullmatch(repository) is None:
        raise TruthfulnessContractError(
            "repository_full_name must be owner/name"
        )
    number = payload["pull_request_number"]
    if type(number) is not int or number < 1:
        raise TruthfulnessContractError(
            "pull_request_number must be positive"
        )
    head_sha = _require_commit(
        payload["pull_request_head_sha"],
        name="pull-request head",
    )
    author = _require_sha256(
        payload["pull_request_author_identity_sha256"],
        name="pull-request author identity",
    )
    ruleset_id = _require_safe_id(payload["ruleset_id"], name="ruleset_id")
    ruleset_sha256 = _require_sha256(
        payload["ruleset_sha256"],
        name="ruleset",
    )
    if payload["no_admin_bypass"] is not True:
        raise TruthfulnessContractError(
            "release evidence requires no administrator bypass"
        )
    if payload["stale_approval_dismissal_enabled"] is not True:
        raise TruthfulnessContractError(
            "release evidence requires stale approval dismissal"
        )
    if payload["code_owner_review_required"] is not True:
        raise TruthfulnessContractError(
            "release evidence requires CODEOWNER review"
        )
    if payload["unresolved_review_thread_count"] != 0:
        raise TruthfulnessContractError(
            "release evidence requires zero unresolved review threads"
        )
    if payload["head_up_to_date"] is not True:
        raise TruthfulnessContractError(
            "release evidence requires an up-to-date pull-request head"
        )
    categories_source = payload["change_categories"]
    if (
        not isinstance(categories_source, list)
        or not categories_source
        or any(value not in _CHANGE_CATEGORIES for value in categories_source)
    ):
        raise TruthfulnessContractError(
            "change_categories must be a non-empty supported array"
        )
    categories = tuple(sorted(set(categories_source)))
    if len(categories) != len(categories_source):
        raise TruthfulnessContractError(
            "change_categories must be sorted and unique"
        )

    review_source = payload["review_submissions"]
    if not isinstance(review_source, list) or not review_source:
        raise TruthfulnessContractError(
            "release evidence requires review submissions"
        )
    reviews = tuple(
        _require_review_submission(row, author_identity_sha256=author)
        for row in review_source
    )
    submission_ids = [str(row["submission_id"]) for row in reviews]
    if submission_ids != sorted(submission_ids) or len(submission_ids) != len(
        set(submission_ids)
    ):
        raise TruthfulnessContractError(
            "review submissions must be uniquely sorted by submission_id"
        )
    roles = {str(row["role"]) for row in reviews}
    if "codeowner" not in roles:
        raise TruthfulnessContractError(
            "release evidence lacks CODEOWNER approval"
        )
    for category, required_role in (
        ("security", "security"),
        ("numerical_methods", "numerical_methods"),
        ("scientific", "scientific"),
    ):
        if category in categories and required_role not in roles:
            raise TruthfulnessContractError(
                f"{category} changes lack the required reviewer approval"
            )

    check_source = payload["required_checks"]
    if not isinstance(check_source, list) or not check_source:
        raise TruthfulnessContractError(
            "release evidence requires successful checks"
        )
    checks = tuple(_require_check(row) for row in check_source)
    check_names = [str(row["name"]) for row in checks]
    if check_names != sorted(check_names) or len(check_names) != len(
        set(check_names)
    ):
        raise TruthfulnessContractError(
            "required checks must be uniquely sorted by name"
        )
    generated_at = _require_utc(
        payload["evidence_generated_at_utc"],
        name="evidence_generated_at_utc",
    )
    canonical_evidence = {
        "schema_id": RELEASE_REVIEW_EVIDENCE_SCHEMA_ID,
        "repository_full_name": repository,
        "pull_request_number": number,
        "pull_request_head_sha": head_sha,
        "pull_request_author_identity_sha256": author,
        "ruleset_id": ruleset_id,
        "ruleset_sha256": ruleset_sha256,
        "no_admin_bypass": True,
        "stale_approval_dismissal_enabled": True,
        "code_owner_review_required": True,
        "unresolved_review_thread_count": 0,
        "head_up_to_date": True,
        "change_categories": list(categories),
        "review_submissions": list(reviews),
        "required_checks": list(checks),
        "evidence_generated_at_utc": generated_at,
    }
    if canonical_evidence != dict(payload):
        raise TruthfulnessContractError(
            "release review evidence is not canonical"
        )
    return {
        "schema_id": RELEASE_REVIEW_VERIFICATION_SCHEMA_ID,
        "evidence_sha256": _sha256(canonical_evidence),
        "operational_review_evidence_verified": True,
        "ruleset_evidence_verified": True,
        "independent_human_approval_verified": True,
        "required_checks_verified": True,
        "scientific_validation_granted": False,
        "benchmark_validation_granted": False,
        "product_qualification_granted": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


__all__ = [
    "RELEASE_REVIEW_EVIDENCE_SCHEMA_ID",
    "RELEASE_REVIEW_VERIFICATION_SCHEMA_ID",
    "SCOPED_METRIC_EVIDENCE_SCHEMA_ID",
    "TRUTHFULNESS_POLICY_SCHEMA_ID",
    "TRUTHFULNESS_SCHEMA_VERSION",
    "TRUTHFULNESS_SNAPSHOT_SCHEMA_ID",
    "ScopedMetricEvidence",
    "TruthfulnessContractError",
    "capability_truthfulness_snapshot",
    "require_capability_truthfulness_snapshot",
    "require_scoped_metric_evidence_row",
    "require_truthfulness_policy_document",
    "truthfulness_policy_document",
    "verify_release_review_evidence",
]
