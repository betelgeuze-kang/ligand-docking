"""Third-generation release evidence contracts.

Version 3 closes the remaining ambiguity in release-review evidence: every
review submission and every required check is bound to the exact pull-request
head, role-qualified reviewers are distinct unless an explicit policy permits a
specific merge, completion times precede attestation generation, attestations
expire, and unknown capability execution receipts are rejected.

The verifier establishes operational evidence only. It never grants scientific
validation, benchmark validity, product qualification, customer execution, or
claim safety.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Mapping, Sequence

from .evidence_contracts import (
    EXECUTION_EVIDENCE_VERIFICATION_SCHEMA_ID,
    EvidenceContractError,
    TrustedReviewer,
    evidence_bound_capability_snapshot,
)
from .truthfulness import capability_truthfulness_snapshot


RELEASE_REVIEW_ATTESTATION_V3_SCHEMA_ID = (
    "betelgeuze.engine_v2_release_review_attestation/3.0.0"
)
RELEASE_REVIEW_VERIFICATION_V3_SCHEMA_ID = (
    "betelgeuze.engine_v2_release_review_verification/3.0.0"
)
EVIDENCE_BOUND_TRUTHFULNESS_V2_SCHEMA_ID = (
    "betelgeuze.engine_v2_evidence_bound_truthfulness_snapshot/2.0.0"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_RE = re.compile(r"^[A-Za-z0-9._:/+@-]{1,256}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
_REVIEW_ROLES = frozenset(
    {"codeowner", "security", "numerical_methods", "scientific"}
)
_EVENT_NAMES = frozenset(
    {"pull_request", "pull_request_target", "workflow_dispatch", "merge_group"}
)


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
        raise EvidenceContractError("evidence v3 is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _safe(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SAFE_RE.fullmatch(value) is None:
        raise EvidenceContractError(f"{name} must be a safe identifier")
    return value


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise EvidenceContractError(f"{name} must be a lowercase SHA-256")
    return value


def _commit(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise EvidenceContractError(
            f"{name} must be a lowercase 40-character Git SHA"
        )
    return value


def _positive_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 1:
        raise EvidenceContractError(f"{name} must be a positive integer")
    return value


def _utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise EvidenceContractError(f"{name} must be second-resolution UTC")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise EvidenceContractError(f"{name} must be valid UTC") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise EvidenceContractError(f"{name} must be canonical UTC")
    return parsed


def _decode_signature(value: object) -> bytes:
    if not isinstance(value, str):
        raise EvidenceContractError("signature_base64 must be text")
    try:
        signature = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise EvidenceContractError("signature_base64 is invalid") from exc
    if len(signature) != 64:
        raise EvidenceContractError("Ed25519 signature must contain 64 bytes")
    return signature


def _verify_signature(
    *, public_key: bytes, signature_base64: object, message: bytes
) -> None:
    if not isinstance(public_key, bytes) or len(public_key) != 32:
        raise EvidenceContractError("trusted Ed25519 key must contain 32 bytes")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(public_key).verify(
            _decode_signature(signature_base64), message
        )
    except InvalidSignature as exc:
        raise EvidenceContractError("release evidence signature is invalid") from exc


def _role_pair(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second)))  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ReleaseReviewExpectationV3:
    repository_full_name: str
    pull_request_number: int
    pull_request_head_sha: str
    pull_request_author_identity_sha256: str
    ruleset_sha256: str
    codeowners_sha256: str
    required_check_names: tuple[str, ...]
    required_check_workflow_source_sha256s: Mapping[str, str]
    required_roles: tuple[str, ...]
    trusted_reviewers: Mapping[str, TrustedReviewer]
    trusted_attestor_keys: Mapping[str, bytes]
    maximum_attestation_age_seconds: int = 3_600
    allowed_role_merge_pairs: tuple[tuple[str, str], ...] = ()

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
            _commit(self.pull_request_head_sha, name="pull_request_head_sha"),
        )
        object.__setattr__(
            self,
            "pull_request_author_identity_sha256",
            _digest(
                self.pull_request_author_identity_sha256,
                name="pull request author identity",
            ),
        )
        object.__setattr__(
            self, "ruleset_sha256", _digest(self.ruleset_sha256, name="ruleset")
        )
        object.__setattr__(
            self,
            "codeowners_sha256",
            _digest(self.codeowners_sha256, name="CODEOWNERS"),
        )
        checks = tuple(sorted(set(self.required_check_names)))
        if not checks or len(checks) != len(self.required_check_names):
            raise EvidenceContractError(
                "required check names must be non-empty and unique"
            )
        if any(not isinstance(name, str) or not name for name in checks):
            raise EvidenceContractError("required check names are invalid")
        object.__setattr__(self, "required_check_names", checks)
        workflow_sources = {
            str(name): _digest(digest, name=f"{name} workflow source")
            for name, digest in self.required_check_workflow_source_sha256s.items()
        }
        if set(workflow_sources) != set(checks):
            raise EvidenceContractError(
                "required workflow source identities must match required checks"
            )
        object.__setattr__(
            self,
            "required_check_workflow_source_sha256s",
            workflow_sources,
        )
        roles = tuple(sorted(set(self.required_roles)))
        if not roles or any(role not in _REVIEW_ROLES for role in roles):
            raise EvidenceContractError("required reviewer roles are invalid")
        if "codeowner" not in roles:
            raise EvidenceContractError(
                "required reviewer roles must include codeowner"
            )
        object.__setattr__(self, "required_roles", roles)
        reviewers = dict(self.trusted_reviewers)
        if not reviewers or any(
            login != reviewer.login for login, reviewer in reviewers.items()
        ):
            raise EvidenceContractError("trusted reviewer directory is invalid")
        object.__setattr__(self, "trusted_reviewers", reviewers)
        keys = dict(self.trusted_attestor_keys)
        if not keys or any(
            not isinstance(key, bytes) or len(key) != 32 for key in keys.values()
        ):
            raise EvidenceContractError("trusted attestor keys are invalid")
        object.__setattr__(self, "trusted_attestor_keys", keys)
        age = _positive_int(
            self.maximum_attestation_age_seconds,
            name="maximum_attestation_age_seconds",
        )
        if age > 86_400:
            raise EvidenceContractError(
                "maximum attestation age must not exceed one day"
            )
        object.__setattr__(self, "maximum_attestation_age_seconds", age)
        merge_pairs = tuple(sorted(set(_role_pair(*row) for row in self.allowed_role_merge_pairs)))
        if any(
            len(row) != 2
            or row[0] == row[1]
            or row[0] not in roles
            or row[1] not in roles
            for row in merge_pairs
        ):
            raise EvidenceContractError("allowed role merge policy is invalid")
        object.__setattr__(self, "allowed_role_merge_pairs", merge_pairs)


def canonical_release_review_attestation_v3_bytes(
    payload: Mapping[str, object],
) -> bytes:
    projection = dict(payload)
    projection.pop("signature_base64", None)
    return _canonical_bytes(projection)


def verify_release_review_attestation_v3(
    payload: object,
    *,
    expected: ReleaseReviewExpectationV3,
    verified_at_utc: str,
) -> dict[str, object]:
    fields = {
        "schema_id",
        "repository_full_name",
        "pull_request_number",
        "pull_request_head_sha",
        "pull_request_author_identity_sha256",
        "ruleset_id",
        "ruleset_sha256",
        "ruleset_snapshot_at_utc",
        "codeowners_sha256",
        "no_admin_bypass",
        "stale_approval_dismissal_enabled",
        "code_owner_review_required",
        "unresolved_review_thread_count",
        "head_up_to_date",
        "review_submissions",
        "required_checks",
        "evidence_generated_at_utc",
        "attestor_key_id",
        "signature_base64",
    }
    if not isinstance(payload, Mapping) or set(payload) != fields:
        raise EvidenceContractError("release review v3 fields are invalid")
    if payload["schema_id"] != RELEASE_REVIEW_ATTESTATION_V3_SCHEMA_ID:
        raise EvidenceContractError("unsupported release review v3 schema")
    exact = (
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
    )
    for observed, wanted, name in exact:
        if observed != wanted:
            raise EvidenceContractError(f"release review {name} is cross-wired")
    _safe(payload["ruleset_id"], name="ruleset_id")
    if (
        payload["no_admin_bypass"] is not True
        or payload["stale_approval_dismissal_enabled"] is not True
        or payload["code_owner_review_required"] is not True
        or payload["unresolved_review_thread_count"] != 0
        or payload["head_up_to_date"] is not True
    ):
        raise EvidenceContractError("release protection policy is incomplete")

    generated = _utc(
        payload["evidence_generated_at_utc"], name="evidence_generated_at_utc"
    )
    verified = _utc(verified_at_utc, name="verified_at_utc")
    ruleset_snapshot = _utc(
        payload["ruleset_snapshot_at_utc"], name="ruleset_snapshot_at_utc"
    )
    if generated > verified:
        raise EvidenceContractError("release evidence is from the future")
    if verified - generated > timedelta(
        seconds=expected.maximum_attestation_age_seconds
    ):
        raise EvidenceContractError("release evidence is stale")

    submissions = payload["review_submissions"]
    if not isinstance(submissions, list) or not submissions:
        raise EvidenceContractError("review submissions are required")
    canonical_submissions: list[dict[str, object]] = []
    role_to_identity: dict[str, str] = {}
    submission_ids: list[int] = []
    latest_review = ruleset_snapshot
    for row in submissions:
        row_fields = {
            "submission_id",
            "reviewer_login",
            "reviewer_user_id",
            "reviewer_identity_sha256",
            "role",
            "state",
            "reviewed_head_sha",
            "submitted_at_utc",
            "dismissed",
        }
        if not isinstance(row, Mapping) or set(row) != row_fields:
            raise EvidenceContractError("review submission v3 fields are invalid")
        submission_id = _positive_int(row["submission_id"], name="submission_id")
        login = _safe(row["reviewer_login"], name="reviewer_login")
        trusted = expected.trusted_reviewers.get(login)
        if trusted is None:
            raise EvidenceContractError("reviewer is absent from trusted directory")
        if row["reviewer_user_id"] != trusted.user_id:
            raise EvidenceContractError("reviewer user ID is cross-wired")
        identity = _digest(
            row["reviewer_identity_sha256"], name="reviewer identity"
        )
        if identity != trusted.identity_sha256:
            raise EvidenceContractError("reviewer identity is cross-wired")
        if identity == expected.pull_request_author_identity_sha256:
            raise EvidenceContractError("pull request author cannot approve")
        role = row["role"]
        if role not in expected.required_roles or role not in trusted.roles:
            raise EvidenceContractError("reviewer role is not trusted or required")
        if row["reviewed_head_sha"] != expected.pull_request_head_sha:
            raise EvidenceContractError("review submission head SHA is cross-wired")
        if row["state"] != "APPROVED" or row["dismissed"] is not False:
            raise EvidenceContractError("review submission is not a current approval")
        submitted = _utc(row["submitted_at_utc"], name="review submitted_at_utc")
        if submitted < ruleset_snapshot or submitted > generated:
            raise EvidenceContractError("review timestamp order is invalid")
        if role in role_to_identity:
            raise EvidenceContractError("review role has multiple approval rows")
        role_to_identity[str(role)] = identity
        submission_ids.append(submission_id)
        latest_review = max(latest_review, submitted)
        canonical_submissions.append(
            {
                "submission_id": submission_id,
                "reviewer_login": login,
                "reviewer_user_id": trusted.user_id,
                "reviewer_identity_sha256": identity,
                "role": role,
                "state": "APPROVED",
                "reviewed_head_sha": expected.pull_request_head_sha,
                "submitted_at_utc": submitted.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "dismissed": False,
            }
        )
    if tuple(sorted(role_to_identity)) != expected.required_roles:
        raise EvidenceContractError("required reviewer roles are incomplete")
    if submission_ids != sorted(set(submission_ids)):
        raise EvidenceContractError("review submission IDs must be uniquely sorted")
    for index, first in enumerate(expected.required_roles):
        for second in expected.required_roles[index + 1 :]:
            if (
                role_to_identity[first] == role_to_identity[second]
                and _role_pair(first, second) not in expected.allowed_role_merge_pairs
            ):
                raise EvidenceContractError(
                    "independent reviewer roles require distinct identities"
                )

    checks = payload["required_checks"]
    if not isinstance(checks, list) or not checks:
        raise EvidenceContractError("required checks are missing")
    canonical_checks: list[dict[str, object]] = []
    names: list[str] = []
    latest_check = ruleset_snapshot
    for row in checks:
        row_fields = {
            "name",
            "check_run_id",
            "check_suite_id",
            "workflow_run_id",
            "workflow_run_attempt",
            "workflow_source_sha256",
            "check_head_sha",
            "event_name",
            "conclusion",
            "completed_at_utc",
        }
        if not isinstance(row, Mapping) or set(row) != row_fields:
            raise EvidenceContractError("required check v3 fields are invalid")
        name = row["name"]
        if not isinstance(name, str) or not name:
            raise EvidenceContractError("required check name is invalid")
        if row["check_head_sha"] != expected.pull_request_head_sha:
            raise EvidenceContractError("required check head SHA is cross-wired")
        if row["event_name"] not in _EVENT_NAMES:
            raise EvidenceContractError("required check event is unsupported")
        if row["conclusion"] != "success":
            raise EvidenceContractError("every required check must succeed")
        completed = _utc(row["completed_at_utc"], name="check completed_at_utc")
        if completed < ruleset_snapshot or completed > generated:
            raise EvidenceContractError("check timestamp order is invalid")
        latest_check = max(latest_check, completed)
        names.append(name)
        workflow_source = _digest(
            row["workflow_source_sha256"], name="workflow source"
        )
        if (
            workflow_source
            != expected.required_check_workflow_source_sha256s.get(str(name))
        ):
            raise EvidenceContractError(
                "required check workflow source is cross-wired"
            )
        canonical_checks.append(
            {
                "name": name,
                "check_run_id": _positive_int(
                    row["check_run_id"], name="check_run_id"
                ),
                "check_suite_id": _positive_int(
                    row["check_suite_id"], name="check_suite_id"
                ),
                "workflow_run_id": _positive_int(
                    row["workflow_run_id"], name="workflow_run_id"
                ),
                "workflow_run_attempt": _positive_int(
                    row["workflow_run_attempt"], name="workflow_run_attempt"
                ),
                "workflow_source_sha256": workflow_source,
                "check_head_sha": expected.pull_request_head_sha,
                "event_name": row["event_name"],
                "conclusion": "success",
                "completed_at_utc": completed.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    if tuple(names) != expected.required_check_names or len(names) != len(set(names)):
        raise EvidenceContractError("required check set is cross-wired")
    if generated < max(latest_review, latest_check):
        raise EvidenceContractError("attestation predates review or check completion")

    key_id = _safe(payload["attestor_key_id"], name="attestor_key_id")
    public_key = expected.trusted_attestor_keys.get(key_id)
    if public_key is None:
        raise EvidenceContractError("attestor key is not trusted")
    unsigned = dict(payload)
    unsigned.pop("signature_base64")
    expected_unsigned = {
        "schema_id": RELEASE_REVIEW_ATTESTATION_V3_SCHEMA_ID,
        "repository_full_name": expected.repository_full_name,
        "pull_request_number": expected.pull_request_number,
        "pull_request_head_sha": expected.pull_request_head_sha,
        "pull_request_author_identity_sha256": (
            expected.pull_request_author_identity_sha256
        ),
        "ruleset_id": payload["ruleset_id"],
        "ruleset_sha256": expected.ruleset_sha256,
        "ruleset_snapshot_at_utc": ruleset_snapshot.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "codeowners_sha256": expected.codeowners_sha256,
        "no_admin_bypass": True,
        "stale_approval_dismissal_enabled": True,
        "code_owner_review_required": True,
        "unresolved_review_thread_count": 0,
        "head_up_to_date": True,
        "review_submissions": canonical_submissions,
        "required_checks": canonical_checks,
        "evidence_generated_at_utc": generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attestor_key_id": key_id,
    }
    if unsigned != expected_unsigned:
        raise EvidenceContractError("release review v3 attestation is not canonical")
    _verify_signature(
        public_key=public_key,
        signature_base64=payload["signature_base64"],
        message=_canonical_bytes(unsigned),
    )
    return {
        "schema_id": RELEASE_REVIEW_VERIFICATION_V3_SCHEMA_ID,
        "attestation_sha256": _sha256(dict(payload)),
        "verified_head_sha": expected.pull_request_head_sha,
        "distinct_reviewer_identity_count": len(set(role_to_identity.values())),
        "required_role_count": len(expected.required_roles),
        "required_check_count": len(expected.required_check_names),
        "expected_context_verified": True,
        "signature_verified": True,
        "timestamp_order_verified": True,
        "freshness_verified": True,
        "scientific_validation_granted": False,
        "benchmark_validation_granted": False,
        "product_qualification_granted": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def evidence_bound_capability_snapshot_v3(
    execution_verifications: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    base = capability_truthfulness_snapshot()
    known = set(base["capabilities"])
    for row in execution_verifications:
        if not isinstance(row, Mapping) or row.get("schema_id") != (
            EXECUTION_EVIDENCE_VERIFICATION_SCHEMA_ID
        ):
            raise EvidenceContractError("execution verification is invalid")
        capability_id = row.get("capability_id")
        if capability_id not in known:
            raise EvidenceContractError(
                "execution evidence references an unknown capability"
            )
    previous = evidence_bound_capability_snapshot(execution_verifications)
    projection: dict[str, object] = {
        **previous,
        "schema_id": EVIDENCE_BOUND_TRUTHFULNESS_V2_SCHEMA_ID,
        "unknown_capability_receipts_rejected": True,
    }
    projection.pop("snapshot_sha256", None)
    projection["snapshot_sha256"] = _sha256(projection)
    return projection


__all__ = [
    "EVIDENCE_BOUND_TRUTHFULNESS_V2_SCHEMA_ID",
    "RELEASE_REVIEW_ATTESTATION_V3_SCHEMA_ID",
    "RELEASE_REVIEW_VERIFICATION_V3_SCHEMA_ID",
    "ReleaseReviewExpectationV3",
    "canonical_release_review_attestation_v3_bytes",
    "evidence_bound_capability_snapshot_v3",
    "verify_release_review_attestation_v3",
]
