"""Independent review evidence contract (P0-2).

P0-1 requires an independent security review and an independent numerical
review before the reconstruction work can be called integrated. "Independent"
has to mean something checkable, otherwise a self-approved PR satisfies it.

This module encodes the minimum that makes a review claim falsifiable:

- at least one reviewer whose identity differs from the author (author-distinct);
- a named security reviewer and a named numerical/scientific reviewer, and
  neither role may be filled by the author;
- protected-branch enforcement with admin bypass disabled;
- a review evidence artifact tied to the exact reviewed commit.

Everything fails closed. An unfilled reviewer handle, a placeholder, or a review
recorded against a different commit is reported as a violation rather than
treated as a weaker-but-acceptable review, because a review claim that cannot
be checked is worse than no claim at all.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

REVIEW_EVIDENCE_SCHEMA_VERSION = "independent_review_evidence_v1"

#: Review roles that must each be filled by a non-author reviewer.
ROLE_SECURITY = "security"
ROLE_NUMERICAL = "numerical_scientific"
ROLE_GENERAL = "general"

REQUIRED_REVIEW_ROLES = (ROLE_SECURITY, ROLE_NUMERICAL)
REVIEW_ROLES = (ROLE_GENERAL, ROLE_SECURITY, ROLE_NUMERICAL)

#: Review verdicts. Only ``approved`` counts as satisfying a required role.
VERDICT_APPROVED = "approved"
VERDICT_CHANGES_REQUESTED = "changes_requested"
VERDICT_COMMENTED = "commented"
REVIEW_VERDICTS = (VERDICT_APPROVED, VERDICT_CHANGES_REQUESTED, VERDICT_COMMENTED)

#: Placeholder shapes an operator template ships with. These must never count as
#: a real reviewer identity.
_PLACEHOLDER_PATTERN = re.compile(
    r"^(|-|n/?a|tbd|todo|fill|fillme|operator_fill.*|<.*>|\{\{.*\}\}|reviewer_handle.*|example.*)$",
    re.IGNORECASE,
)

STATUS_READY = "independent_review_evidence_ready"
STATUS_BLOCKED = "blocked_independent_review_evidence"

CLAIM_BOUNDARY = (
    "Independent review evidence contract only. It validates operator-recorded reviewer identities, roles, "
    "verdicts, reviewed-commit binding, and protected-branch posture. It does not contact GitHub, read or "
    "change branch protection, request reviews, approve anything, merge, or mutate external state."
)


def _is_placeholder(value: Any) -> bool:
    return bool(_PLACEHOLDER_PATTERN.match(str(value or "").strip()))


def _normalize_identity(value: Any) -> str:
    """Case-insensitive identity, so `Alice` and `alice` are the same person."""

    return str(value or "").strip().lower()


@dataclass(frozen=True)
class ReviewRecord:
    """One recorded review."""

    reviewer_id: str
    role: str
    verdict: str
    reviewed_commit_sha: str
    reviewed_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def approved(self) -> bool:
        return self.verdict == VERDICT_APPROVED


@dataclass(frozen=True)
class BranchProtectionPosture:
    """Operator-recorded branch protection state for the protected branch."""

    branch: str
    protected: bool
    required_approving_review_count: int
    dismiss_stale_reviews: bool
    require_code_owner_reviews: bool
    admin_bypass_allowed: bool
    force_push_allowed: bool

    def violations(self) -> list[str]:
        reasons: list[str] = []
        if not str(self.branch or "").strip():
            reasons.append("protected_branch_name_missing")
        if not self.protected:
            reasons.append("protected_branch_not_enabled")
        if int(self.required_approving_review_count) < 1:
            reasons.append("required_approving_review_count_below_one")
        if not self.require_code_owner_reviews:
            reasons.append("code_owner_review_not_required")
        if self.admin_bypass_allowed:
            # An admin bypass makes every other protection advisory.
            reasons.append("admin_bypass_allowed")
        if self.force_push_allowed:
            reasons.append("force_push_allowed_on_protected_branch")
        if not self.dismiss_stale_reviews:
            reasons.append("stale_reviews_not_dismissed_on_new_commits")
        return reasons

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["violations"] = self.violations()
        return payload


@dataclass(frozen=True)
class CodeownersPosture:
    """Operator-recorded CODEOWNERS separation state."""

    codeowners_path: str
    present: bool
    owner_ids: tuple[str, ...] = ()
    security_owner_ids: tuple[str, ...] = ()
    numerical_owner_ids: tuple[str, ...] = ()

    def violations(self, *, author_id: str) -> list[str]:
        reasons: list[str] = []
        if not self.present:
            reasons.append("codeowners_file_missing")
            return reasons
        author = _normalize_identity(author_id)
        for label, owners in (
            ("codeowners", self.owner_ids),
            ("security_codeowners", self.security_owner_ids),
            ("numerical_codeowners", self.numerical_owner_ids),
        ):
            real = [owner for owner in owners if not _is_placeholder(owner)]
            if not real:
                reasons.append(f"{label}_unassigned")
                continue
            if all(_normalize_identity(owner) == author for owner in real):
                # A CODEOWNERS entry that names only the author cannot separate
                # ownership from authorship.
                reasons.append(f"{label}_only_author")
        return reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "codeowners_path": self.codeowners_path,
            "present": bool(self.present),
            "owner_ids": list(self.owner_ids),
            "security_owner_ids": list(self.security_owner_ids),
            "numerical_owner_ids": list(self.numerical_owner_ids),
        }


@dataclass(frozen=True)
class ReviewEvidence:
    """The full review evidence bundle for one reviewed commit."""

    subject: str
    author_id: str
    reviewed_commit_sha: str
    reviews: tuple[ReviewRecord, ...] = ()
    branch_protection: BranchProtectionPosture | None = None
    codeowners: CodeownersPosture | None = None

    @property
    def approved_reviews(self) -> tuple[ReviewRecord, ...]:
        return tuple(review for review in self.reviews if review.approved)

    def author_distinct_reviewers(self) -> tuple[str, ...]:
        author = _normalize_identity(self.author_id)
        seen: list[str] = []
        for review in self.approved_reviews:
            identity = _normalize_identity(review.reviewer_id)
            if not identity or _is_placeholder(review.reviewer_id):
                continue
            if identity == author:
                continue
            if identity not in seen:
                seen.append(identity)
        return tuple(seen)

    def role_reviewers(self, role: str) -> tuple[str, ...]:
        author = _normalize_identity(self.author_id)
        return tuple(
            _normalize_identity(review.reviewer_id)
            for review in self.approved_reviews
            if review.role == role
            and not _is_placeholder(review.reviewer_id)
            and _normalize_identity(review.reviewer_id) != author
        )

    def violations(self) -> list[str]:
        reasons: list[str] = []
        if not str(self.author_id or "").strip() or _is_placeholder(self.author_id):
            reasons.append("author_id_missing")
        commit = str(self.reviewed_commit_sha or "").strip()
        if not commit or _is_placeholder(commit):
            reasons.append("reviewed_commit_sha_missing")

        for review in self.reviews:
            if review.verdict not in REVIEW_VERDICTS:
                reasons.append(f"unsupported_review_verdict:{review.verdict or '<empty>'}")
            if review.role not in REVIEW_ROLES:
                reasons.append(f"unsupported_review_role:{review.role or '<empty>'}")
            if _is_placeholder(review.reviewer_id):
                reasons.append("reviewer_id_placeholder")
            if commit and str(review.reviewed_commit_sha or "").strip() != commit:
                # A review of a different commit is not a review of this change.
                reasons.append(
                    f"review_commit_mismatch:{review.reviewer_id or '<unknown>'}"
                )
            if _normalize_identity(review.reviewer_id) == _normalize_identity(self.author_id):
                reasons.append(f"self_review_not_independent:{review.role}")

        if not self.author_distinct_reviewers():
            reasons.append("no_author_distinct_approving_reviewer")
        for role in REQUIRED_REVIEW_ROLES:
            if not self.role_reviewers(role):
                reasons.append(f"required_review_role_unsatisfied:{role}")

        if self.branch_protection is None:
            reasons.append("branch_protection_posture_missing")
        else:
            reasons.extend(self.branch_protection.violations())
        if self.codeowners is None:
            reasons.append("codeowners_posture_missing")
        else:
            reasons.extend(self.codeowners.violations(author_id=self.author_id))

        return list(dict.fromkeys(reasons))

    @property
    def ready(self) -> bool:
        return not self.violations()

    @property
    def status(self) -> str:
        return STATUS_READY if self.ready else STATUS_BLOCKED

    @property
    def evidence_hash(self) -> str:
        payload = {
            "subject": self.subject,
            "author_id": _normalize_identity(self.author_id),
            "reviewed_commit_sha": str(self.reviewed_commit_sha),
            "reviews": [review.to_dict() for review in self.reviews],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        violations = self.violations()
        return {
            "schema_version": REVIEW_EVIDENCE_SCHEMA_VERSION,
            "status": STATUS_READY if not violations else STATUS_BLOCKED,
            "ready": not violations,
            "subject": str(self.subject),
            "author_id": str(self.author_id),
            "reviewed_commit_sha": str(self.reviewed_commit_sha),
            "evidence_hash": self.evidence_hash,
            "review_count": len(self.reviews),
            "approved_review_count": len(self.approved_reviews),
            "author_distinct_reviewer_count": len(self.author_distinct_reviewers()),
            "author_distinct_reviewer_ids": list(self.author_distinct_reviewers()),
            "required_review_roles": list(REQUIRED_REVIEW_ROLES),
            "role_reviewers": {
                role: list(self.role_reviewers(role)) for role in REVIEW_ROLES
            },
            "reviews": [review.to_dict() for review in self.reviews],
            "branch_protection": (
                self.branch_protection.to_dict() if self.branch_protection else {}
            ),
            "codeowners": self.codeowners.to_dict() if self.codeowners else {},
            "admin_bypass_allowed": bool(
                self.branch_protection.admin_bypass_allowed if self.branch_protection else True
            ),
            "violation_count": len(violations),
            "violations": violations,
            "github_contacted": False,
            "branch_protection_mutated": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }


def build_review_evidence(
    *,
    subject: str,
    author_id: str,
    reviewed_commit_sha: str,
    reviews: Sequence[Mapping[str, Any]] | None = None,
    branch_protection: Mapping[str, Any] | None = None,
    codeowners: Mapping[str, Any] | None = None,
) -> ReviewEvidence:
    """Build review evidence from plain mappings, without fixing up problems."""

    review_rows = tuple(
        ReviewRecord(
            reviewer_id=str(row.get("reviewer_id") or ""),
            role=str(row.get("role") or ""),
            verdict=str(row.get("verdict") or ""),
            reviewed_commit_sha=str(row.get("reviewed_commit_sha") or ""),
            reviewed_at_utc=str(row.get("reviewed_at_utc") or ""),
        )
        for row in reviews or ()
    )
    protection = (
        BranchProtectionPosture(
            branch=str(branch_protection.get("branch") or ""),
            protected=bool(branch_protection.get("protected") is True),
            required_approving_review_count=int(
                branch_protection.get("required_approving_review_count") or 0
            ),
            dismiss_stale_reviews=bool(branch_protection.get("dismiss_stale_reviews") is True),
            require_code_owner_reviews=bool(
                branch_protection.get("require_code_owner_reviews") is True
            ),
            admin_bypass_allowed=bool(branch_protection.get("admin_bypass_allowed") is not False),
            force_push_allowed=bool(branch_protection.get("force_push_allowed") is True),
        )
        if branch_protection is not None
        else None
    )
    owners = (
        CodeownersPosture(
            codeowners_path=str(codeowners.get("codeowners_path") or ""),
            present=bool(codeowners.get("present") is True),
            owner_ids=tuple(str(v) for v in codeowners.get("owner_ids") or ()),
            security_owner_ids=tuple(str(v) for v in codeowners.get("security_owner_ids") or ()),
            numerical_owner_ids=tuple(
                str(v) for v in codeowners.get("numerical_owner_ids") or ()
            ),
        )
        if codeowners is not None
        else None
    )
    return ReviewEvidence(
        subject=str(subject),
        author_id=str(author_id),
        reviewed_commit_sha=str(reviewed_commit_sha),
        reviews=review_rows,
        branch_protection=protection,
        codeowners=owners,
    )


__all__ = [
    "CLAIM_BOUNDARY",
    "REQUIRED_REVIEW_ROLES",
    "REVIEW_EVIDENCE_SCHEMA_VERSION",
    "REVIEW_ROLES",
    "REVIEW_VERDICTS",
    "ROLE_GENERAL",
    "ROLE_NUMERICAL",
    "ROLE_SECURITY",
    "STATUS_BLOCKED",
    "STATUS_READY",
    "VERDICT_APPROVED",
    "VERDICT_CHANGES_REQUESTED",
    "VERDICT_COMMENTED",
    "BranchProtectionPosture",
    "CodeownersPosture",
    "ReviewEvidence",
    "ReviewRecord",
    "build_review_evidence",
]
