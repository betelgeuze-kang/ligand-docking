"""Machine-readable GitHub review evidence required before Engine v2 release."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


REVIEW_EVIDENCE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_review_evidence_receipt/1.0.0"
)
REVIEW_EVIDENCE_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_review_evidence_policy/1.0.0"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,256}$")

SECURITY_CHANGE_DOMAINS = frozenset(
    {
        "cryptography",
        "authorization",
        "posix_persistence",
        "execution_bootstrap",
        "runtime_trust",
    }
)
NUMERICAL_CHANGE_DOMAINS = frozenset(
    {
        "numerical_methods",
        "force_field",
        "minimization",
        "metrics",
        "docking",
        "molecular_dynamics",
    }
)
REVIEW_ROLES = frozenset({"human", "codeowner", "security", "numerical_methods"})


class ReviewEvidenceError(ValueError):
    """Release review evidence is absent, contradictory, or insufficient."""


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
        raise ReviewEvidenceError(
            "review evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _safe_id(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SAFE_ID_RE.fullmatch(value) is None:
        raise ReviewEvidenceError(f"{name} is invalid")
    return value


def _sha256_value(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ReviewEvidenceError(f"{name} must be a lowercase SHA-256")
    return value


def _utc(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReviewEvidenceError(f"{name} must use second-resolution UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReviewEvidenceError(
            f"{name} must use second-resolution UTC"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ReviewEvidenceError(f"{name} is not canonical UTC")
    return value


def required_review_roles(change_domains: Sequence[str]) -> tuple[str, ...]:
    domains = frozenset(_safe_id(value, name="change domain") for value in change_domains)
    if not domains:
        raise ReviewEvidenceError("at least one change domain is required")
    roles = {"human", "codeowner"}
    if domains.intersection(SECURITY_CHANGE_DOMAINS):
        roles.add("security")
    if domains.intersection(NUMERICAL_CHANGE_DOMAINS):
        roles.add("numerical_methods")
    return tuple(sorted(roles))


@dataclass(frozen=True, slots=True)
class ReviewSubmissionEvidence:
    submission_id: str
    reviewer_identity_sha256: str
    reviewer_role: str
    state: str
    submitted_at_utc: str
    dismissed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "submission_id",
            _safe_id(self.submission_id, name="review submission id"),
        )
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _sha256_value(
                self.reviewer_identity_sha256,
                name="reviewer identity",
            ),
        )
        role = _safe_id(self.reviewer_role, name="reviewer role")
        if role not in REVIEW_ROLES:
            raise ReviewEvidenceError("reviewer role is unsupported")
        object.__setattr__(self, "reviewer_role", role)
        state = _safe_id(self.state, name="review state").lower()
        if state != "approved":
            raise ReviewEvidenceError("qualifying review state must be approved")
        object.__setattr__(self, "state", state)
        object.__setattr__(
            self,
            "submitted_at_utc",
            _utc(self.submitted_at_utc, name="review submitted_at_utc"),
        )
        if type(self.dismissed) is not bool:
            raise ReviewEvidenceError("review dismissed flag must be boolean")
        if self.dismissed:
            raise ReviewEvidenceError("dismissed review cannot qualify")

    def to_dict(self) -> dict[str, object]:
        return {
            "submission_id": self.submission_id,
            "reviewer_identity_sha256": self.reviewer_identity_sha256,
            "reviewer_role": self.reviewer_role,
            "state": self.state,
            "submitted_at_utc": self.submitted_at_utc,
            "dismissed": self.dismissed,
        }

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
    ) -> "ReviewSubmissionEvidence":
        required = {
            "submission_id",
            "reviewer_identity_sha256",
            "reviewer_role",
            "state",
            "submitted_at_utc",
            "dismissed",
        }
        if not isinstance(payload, Mapping) or set(payload) != required:
            raise ReviewEvidenceError("review submission fields are invalid")
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ReviewEvidenceReceipt:
    repository_full_name: str
    pr_number: int
    head_sha: str
    ruleset_id: str
    implementation_author_identity_sha256: str
    change_domains: tuple[str, ...]
    reviews: tuple[ReviewSubmissionEvidence, ...]
    unresolved_review_thread_count: int
    required_check_names: tuple[str, ...]
    successful_check_names: tuple[str, ...]
    administrator_bypass_allowed: bool
    recorded_at_utc: str
    schema_id: str = REVIEW_EVIDENCE_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REVIEW_EVIDENCE_RECEIPT_SCHEMA_ID:
            raise ReviewEvidenceError("unsupported review evidence schema")
        repository = _safe_id(
            self.repository_full_name,
            name="repository_full_name",
        )
        if repository.count("/") != 1:
            raise ReviewEvidenceError(
                "repository_full_name must use owner/name form"
            )
        object.__setattr__(self, "repository_full_name", repository)
        if type(self.pr_number) is not int or self.pr_number < 1:
            raise ReviewEvidenceError("pr_number must be positive")
        if not isinstance(self.head_sha, str) or _GIT_COMMIT_RE.fullmatch(
            self.head_sha
        ) is None:
            raise ReviewEvidenceError(
                "head_sha must be a lowercase 40-character Git SHA"
            )
        object.__setattr__(
            self,
            "ruleset_id",
            _safe_id(self.ruleset_id, name="ruleset_id"),
        )
        author = _sha256_value(
            self.implementation_author_identity_sha256,
            name="implementation author identity",
        )
        object.__setattr__(
            self,
            "implementation_author_identity_sha256",
            author,
        )
        domains = tuple(
            sorted(
                set(
                    _safe_id(value, name="change domain")
                    for value in self.change_domains
                )
            )
        )
        required_roles = required_review_roles(domains)
        object.__setattr__(self, "change_domains", domains)
        reviews = tuple(self.reviews)
        if not reviews:
            raise ReviewEvidenceError("qualifying reviews are required")
        if any(not isinstance(row, ReviewSubmissionEvidence) for row in reviews):
            raise ReviewEvidenceError("review rows must be ReviewSubmissionEvidence")
        submission_ids = [row.submission_id for row in reviews]
        if len(submission_ids) != len(set(submission_ids)):
            raise ReviewEvidenceError("review submission ids must be unique")
        if any(row.reviewer_identity_sha256 == author for row in reviews):
            raise ReviewEvidenceError(
                "implementation author cannot supply a qualifying review"
            )
        observed_roles = {row.reviewer_role for row in reviews}
        missing_roles = sorted(set(required_roles) - observed_roles)
        if missing_roles:
            raise ReviewEvidenceError(
                f"required review roles are missing: {missing_roles}"
            )
        object.__setattr__(self, "reviews", reviews)
        if (
            type(self.unresolved_review_thread_count) is not int
            or self.unresolved_review_thread_count != 0
        ):
            raise ReviewEvidenceError(
                "all review conversations must be resolved"
            )
        required_checks = tuple(
            sorted(
                set(
                    _safe_id(value, name="required check")
                    for value in self.required_check_names
                )
            )
        )
        successful_checks = tuple(
            sorted(
                set(
                    _safe_id(value, name="successful check")
                    for value in self.successful_check_names
                )
            )
        )
        if not required_checks:
            raise ReviewEvidenceError("required CI checks cannot be empty")
        missing_checks = sorted(set(required_checks) - set(successful_checks))
        if missing_checks:
            raise ReviewEvidenceError(
                f"required CI checks are not successful: {missing_checks}"
            )
        object.__setattr__(self, "required_check_names", required_checks)
        object.__setattr__(self, "successful_check_names", successful_checks)
        if type(self.administrator_bypass_allowed) is not bool:
            raise ReviewEvidenceError(
                "administrator bypass flag must be boolean"
            )
        if self.administrator_bypass_allowed:
            raise ReviewEvidenceError(
                "administrator bypass must be disabled for release evidence"
            )
        object.__setattr__(
            self,
            "recorded_at_utc",
            _utc(self.recorded_at_utc, name="recorded_at_utc"),
        )

    @property
    def required_roles(self) -> tuple[str, ...]:
        return required_review_roles(self.change_domains)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "repository_full_name": self.repository_full_name,
            "pr_number": self.pr_number,
            "head_sha": self.head_sha,
            "ruleset_id": self.ruleset_id,
            "implementation_author_identity_sha256": (
                self.implementation_author_identity_sha256
            ),
            "change_domains": list(self.change_domains),
            "required_review_roles": list(self.required_roles),
            "reviews": [row.to_dict() for row in self.reviews],
            "unresolved_review_thread_count": (
                self.unresolved_review_thread_count
            ),
            "required_check_names": list(self.required_check_names),
            "successful_check_names": list(self.successful_check_names),
            "administrator_bypass_allowed": self.administrator_bypass_allowed,
            "recorded_at_utc": self.recorded_at_utc,
            "release_review_evidence_ready": True,
            "scientific_validation_established": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
    ) -> "ReviewEvidenceReceipt":
        required = {
            "schema_id",
            "repository_full_name",
            "pr_number",
            "head_sha",
            "ruleset_id",
            "implementation_author_identity_sha256",
            "change_domains",
            "reviews",
            "unresolved_review_thread_count",
            "required_check_names",
            "successful_check_names",
            "administrator_bypass_allowed",
            "recorded_at_utc",
        }
        if not isinstance(payload, Mapping) or set(payload) != required:
            raise ReviewEvidenceError("review evidence receipt fields are invalid")
        reviews = payload["reviews"]
        if not isinstance(reviews, list):
            raise ReviewEvidenceError("reviews must be an array")
        return cls(
            repository_full_name=payload["repository_full_name"],
            pr_number=payload["pr_number"],
            head_sha=payload["head_sha"],
            ruleset_id=payload["ruleset_id"],
            implementation_author_identity_sha256=(
                payload["implementation_author_identity_sha256"]
            ),
            change_domains=tuple(payload["change_domains"]),
            reviews=tuple(
                ReviewSubmissionEvidence.from_mapping(row) for row in reviews
            ),
            unresolved_review_thread_count=(
                payload["unresolved_review_thread_count"]
            ),
            required_check_names=tuple(payload["required_check_names"]),
            successful_check_names=tuple(payload["successful_check_names"]),
            administrator_bypass_allowed=(
                payload["administrator_bypass_allowed"]
            ),
            recorded_at_utc=payload["recorded_at_utc"],
            schema_id=payload["schema_id"],
        )


def review_evidence_policy_document() -> dict[str, object]:
    return {
        "schema_id": REVIEW_EVIDENCE_POLICY_SCHEMA_ID,
        "receipt_schema_id": REVIEW_EVIDENCE_RECEIPT_SCHEMA_ID,
        "base_required_roles": ["human", "codeowner"],
        "security_change_domains": sorted(SECURITY_CHANGE_DOMAINS),
        "numerical_change_domains": sorted(NUMERICAL_CHANGE_DOMAINS),
        "security_role_required_for_security_changes": True,
        "numerical_methods_role_required_for_numerical_changes": True,
        "implementation_author_review_forbidden": True,
        "stale_or_dismissed_review_forbidden": True,
        "all_review_conversations_must_be_resolved": True,
        "all_required_checks_must_be_successful": True,
        "protected_ruleset_identity_required": True,
        "administrator_bypass_allowed": False,
        "repository_bundles_qualifying_review_receipt": False,
        "external_state_mutated": False,
    }


def require_review_evidence_receipt(payload: object) -> ReviewEvidenceReceipt:
    if not isinstance(payload, Mapping):
        raise ReviewEvidenceError("review evidence receipt must be a mapping")
    return ReviewEvidenceReceipt.from_mapping(payload)


def current_review_evidence_decision() -> dict[str, object]:
    return {
        "policy": review_evidence_policy_document(),
        "qualifying_review_receipt_present": False,
        "protected_ruleset_evidence_present": False,
        "independent_human_approval_present": False,
        "release_review_evidence_ready": False,
        "claim_safe": False,
        "blockers": [
            "qualifying_review_receipt_not_bundled",
            "protected_ruleset_evidence_not_bundled",
            "independent_human_approval_not_bundled",
        ],
    }


__all__ = [
    "NUMERICAL_CHANGE_DOMAINS",
    "REVIEW_EVIDENCE_POLICY_SCHEMA_ID",
    "REVIEW_EVIDENCE_RECEIPT_SCHEMA_ID",
    "REVIEW_ROLES",
    "SECURITY_CHANGE_DOMAINS",
    "ReviewEvidenceError",
    "ReviewEvidenceReceipt",
    "ReviewSubmissionEvidence",
    "current_review_evidence_decision",
    "require_review_evidence_receipt",
    "required_review_roles",
    "review_evidence_policy_document",
]
