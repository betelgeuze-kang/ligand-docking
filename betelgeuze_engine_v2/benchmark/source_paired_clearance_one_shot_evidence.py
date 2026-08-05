"""Bind one-shot result summaries to exact external evidence artifact bytes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

from .source_paired_clearance_one_shot_ab import (
    EXPECTED_POLICY_SHA256,
    OneShotABAuthorityError,
    _is_sha256,
    sha256_payload,
    verify_self_hash,
)


EXTERNAL_EVIDENCE_ENVELOPE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_evidence_envelope/1.0.0"
)
MAX_EXTERNAL_EVIDENCE_BYTES = 256 * 1024 * 1024
_ARM_ROLES = frozenset({"baseline_arm", "experimental_arm"})
_ALLOWED_ROLES = _ARM_ROLES | {"cross_arm"}
_ENVELOPE_KEYS = {
    "evidence_role",
    "execution_environment_sha256",
    "payload",
    "policy_sha256",
    "receipt_sha256",
    "run_start_receipt_sha256",
    "schema_id",
    "source_commit_git_sha1",
}
_ARM_PAYLOAD_KEYS = {
    "arm_summary_projection",
    "candidate_receipt_sha256s",
    "case_receipt_sha256s",
}
_CROSS_PAYLOAD_KEYS = {
    "case_cross_arm_receipt_sha256s",
    "changed_slot_receipt_sha256s",
    "cross_arm_projection",
}


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, name: str) -> None:
    if set(value) != expected:
        raise OneShotABAuthorityError(f"{name} key set is invalid")


def _sha256_rows(
    value: object,
    *,
    expected_count: int,
    name: str,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise OneShotABAuthorityError(
            f"{name} must contain exactly {expected_count} SHA-256 rows"
        )
    rows = tuple(value)
    if any(not _is_sha256(item) for item in rows):
        raise OneShotABAuthorityError(f"{name} contains an invalid SHA-256")
    if len(set(rows)) != len(rows):
        raise OneShotABAuthorityError(f"{name} must contain unique receipt identities")
    return rows


def _read_pinned_regular_file(path: Path, *, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise OneShotABAuthorityError(f"{name} cannot be opened safely: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OneShotABAuthorityError(f"{name} must be a regular file")
        if before.st_size <= 0 or before.st_size > MAX_EXTERNAL_EVIDENCE_BYTES:
            raise OneShotABAuthorityError(f"{name} size is outside the bounded envelope")
        chunks: list[bytes] = []
        observed_size = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, MAX_EXTERNAL_EVIDENCE_BYTES + 1))
            if not chunk:
                break
            observed_size += len(chunk)
            if observed_size > MAX_EXTERNAL_EVIDENCE_BYTES:
                raise OneShotABAuthorityError(f"{name} exceeds the bounded envelope")
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    )
    if identity_before != identity_after or observed_size != before.st_size:
        raise OneShotABAuthorityError(f"{name} changed while it was being read")
    return b"".join(chunks)


def _decode_envelope(raw: bytes, *, name: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OneShotABAuthorityError(f"{name} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise OneShotABAuthorityError(f"{name} must be a JSON object")
    return value


def _summary_projection(summary: Mapping[str, Any], *, role: str) -> dict[str, Any]:
    projection = dict(summary)
    if role in _ARM_ROLES:
        projection.pop("arm_evidence_file_sha256", None)
        projection.pop("arm_evidence_self_sha256", None)
    else:
        projection.pop("cross_arm_evidence_sha256", None)
    return projection


def build_external_evidence_envelope(
    *,
    role: str,
    run_start: Mapping[str, Any],
    summary: Mapping[str, Any],
    case_receipt_sha256s: Sequence[str],
    candidate_or_changed_receipt_sha256s: Sequence[str],
) -> dict[str, Any]:
    """Build a self-hashed envelope around a full external evidence manifest."""

    if role not in _ALLOWED_ROLES:
        raise OneShotABAuthorityError("external evidence role is invalid")
    if role in _ARM_ROLES:
        if len(case_receipt_sha256s) != 8:
            raise OneShotABAuthorityError("arm evidence requires eight case receipts")
        if len(candidate_or_changed_receipt_sha256s) != 512:
            raise OneShotABAuthorityError("arm evidence requires 512 candidate receipts")
        payload: dict[str, Any] = {
            "arm_summary_projection": _summary_projection(summary, role=role),
            "case_receipt_sha256s": list(case_receipt_sha256s),
            "candidate_receipt_sha256s": list(
                candidate_or_changed_receipt_sha256s
            ),
        }
    else:
        changed_slot_count = summary.get("changed_slot_count")
        if type(changed_slot_count) is not int or changed_slot_count < 0:
            raise OneShotABAuthorityError("cross-arm changed-slot count is invalid")
        if len(case_receipt_sha256s) != 8:
            raise OneShotABAuthorityError("cross-arm evidence requires eight case receipts")
        if len(candidate_or_changed_receipt_sha256s) != changed_slot_count:
            raise OneShotABAuthorityError(
                "cross-arm changed-slot receipt denominator is invalid"
            )
        payload = {
            "cross_arm_projection": _summary_projection(summary, role=role),
            "case_cross_arm_receipt_sha256s": list(case_receipt_sha256s),
            "changed_slot_receipt_sha256s": list(
                candidate_or_changed_receipt_sha256s
            ),
        }
    envelope: dict[str, Any] = {
        "schema_id": EXTERNAL_EVIDENCE_ENVELOPE_SCHEMA_ID,
        "evidence_role": role,
        "policy_sha256": EXPECTED_POLICY_SHA256,
        "run_start_receipt_sha256": run_start.get("receipt_sha256"),
        "source_commit_git_sha1": run_start.get("source_commit_git_sha1"),
        "execution_environment_sha256": run_start.get(
            "execution_environment_sha256"
        ),
        "payload": payload,
    }
    envelope["receipt_sha256"] = sha256_payload(envelope)
    return envelope


def verify_external_evidence_file(
    path: Path,
    *,
    role: str,
    run_start: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, str]:
    """Verify one exact evidence file and its summary/run-start bindings."""

    if role not in _ALLOWED_ROLES:
        raise OneShotABAuthorityError("external evidence role is invalid")
    raw = _read_pinned_regular_file(path, name=f"{role} evidence")
    file_sha256 = hashlib.sha256(raw).hexdigest()
    envelope = _decode_envelope(raw, name=f"{role} evidence")
    _exact_keys(envelope, _ENVELOPE_KEYS, name=f"{role} evidence envelope")
    verify_self_hash(
        envelope,
        hash_field="receipt_sha256",
        name=f"{role} evidence envelope",
    )
    if envelope.get("schema_id") != EXTERNAL_EVIDENCE_ENVELOPE_SCHEMA_ID:
        raise OneShotABAuthorityError(f"{role} evidence schema is invalid")
    if envelope.get("evidence_role") != role:
        raise OneShotABAuthorityError(f"{role} evidence role is cross-wired")
    if envelope.get("policy_sha256") != EXPECTED_POLICY_SHA256:
        raise OneShotABAuthorityError(f"{role} evidence policy is cross-wired")
    for field in (
        "run_start_receipt_sha256",
        "source_commit_git_sha1",
        "execution_environment_sha256",
    ):
        if envelope.get(field) != run_start.get(field):
            raise OneShotABAuthorityError(f"{role} evidence {field} is cross-wired")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise OneShotABAuthorityError(f"{role} evidence payload must be an object")

    expected_projection = _summary_projection(summary, role=role)
    if role in _ARM_ROLES:
        _exact_keys(payload, _ARM_PAYLOAD_KEYS, name=f"{role} evidence payload")
        if payload.get("arm_summary_projection") != expected_projection:
            raise OneShotABAuthorityError(f"{role} evidence summary is cross-wired")
        _sha256_rows(
            payload.get("case_receipt_sha256s"),
            expected_count=8,
            name=f"{role} case receipts",
        )
        _sha256_rows(
            payload.get("candidate_receipt_sha256s"),
            expected_count=512,
            name=f"{role} candidate receipts",
        )
        if summary.get("arm_evidence_file_sha256") != file_sha256:
            raise OneShotABAuthorityError(f"{role} evidence file SHA-256 is cross-wired")
        if summary.get("arm_evidence_self_sha256") != envelope.get("receipt_sha256"):
            raise OneShotABAuthorityError(f"{role} evidence self-hash is cross-wired")
    else:
        _exact_keys(payload, _CROSS_PAYLOAD_KEYS, name="cross-arm evidence payload")
        if payload.get("cross_arm_projection") != expected_projection:
            raise OneShotABAuthorityError("cross-arm evidence summary is cross-wired")
        _sha256_rows(
            payload.get("case_cross_arm_receipt_sha256s"),
            expected_count=8,
            name="cross-arm case receipts",
        )
        changed_slot_count = summary.get("changed_slot_count")
        if type(changed_slot_count) is not int:
            raise OneShotABAuthorityError("cross-arm changed-slot count is invalid")
        _sha256_rows(
            payload.get("changed_slot_receipt_sha256s"),
            expected_count=changed_slot_count,
            name="cross-arm changed-slot receipts",
        )
        if summary.get("cross_arm_evidence_sha256") != file_sha256:
            raise OneShotABAuthorityError(
                "cross-arm evidence file SHA-256 is cross-wired"
            )

    return {
        "file_sha256": file_sha256,
        "receipt_sha256": str(envelope["receipt_sha256"]),
    }


__all__ = [
    "EXTERNAL_EVIDENCE_ENVELOPE_SCHEMA_ID",
    "MAX_EXTERNAL_EVIDENCE_BYTES",
    "build_external_evidence_envelope",
    "verify_external_evidence_file",
]
