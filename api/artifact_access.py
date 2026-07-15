"""Confined, signed, content-addressed access to completed API artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, BinaryIO, Iterator

from fastapi import HTTPException

from api.result_manifest import infer_result_artifact_metadata, verify_result_manifest
from api.validated_runner_execution_evidence import (
    EXECUTION_EVIDENCE_PROVENANCE_KEY,
    validate_validated_runner_execution_evidence,
)
from api.validated_runner_runtime_qualification import (
    MAX_RECEIPT_VALIDITY,
    RECEIPT_SCHEMA_VERSION,
)
from betelgeuze_ai_md.contracts import EvidenceBundle
from betelgeuze_ai_md.contracts.errors import ContractValidationError


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_QUALIFICATION_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_RUNTIME_QUALIFICATION_KEYS = (
    "validated_runner_namespace_runtime_qualified",
    "validated_runner_namespace_runtime_receipt_schema_version",
    "validated_runner_namespace_runtime_receipt_sha256",
    "validated_runner_namespace_runtime_receipt_issued_at_utc",
    "validated_runner_namespace_runtime_receipt_expires_at_utc",
)
_ALLOWED_MEDIA_TYPES = {
    "application/json",
    "chemical/x-pdb",
    "chemical/x-mdl-sdfile",
    "chemical/x-mdl-molfile",
    "application/zip",
    "application/octet-stream",
}


@dataclass
class VerifiedResultArtifacts:
    root: Path
    manifest_path: Path
    result_path: Path
    evidence_bundle_path: Path
    manifest: dict[str, Any]
    result_sha256: str
    evidence_bundle_sha256: str
    media_type: str
    artifact_type: str
    result_snapshot: BinaryIO | None = None

    def close(self) -> None:
        if self.result_snapshot is not None:
            self.result_snapshot.close()
            self.result_snapshot = None

    def iter_result(self, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        snapshot = self.result_snapshot
        if snapshot is None:
            raise RuntimeError("verified result snapshot is unavailable")
        try:
            snapshot.seek(0)
            while True:
                chunk = snapshot.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            self.close()


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=403, detail=detail)


class _ConfinedArtifactRoot:
    """Hold one root directory descriptor while opening confined artifacts."""

    def __init__(self, root: str | Path, *, label: str = "artifact") -> None:
        self.root_path = Path(os.path.abspath(str(Path(root).expanduser())))
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            self._fd = os.open(self.root_path, flags)
            if not stat.S_ISDIR(os.fstat(self._fd).st_mode):
                raise OSError("root is not a directory")
        except OSError as exc:
            if hasattr(self, "_fd"):
                os.close(self._fd)
            raise _forbidden(f"{label} root is unavailable") from exc

    def __enter__(self) -> "_ConfinedArtifactRoot":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def normalize(self, path_like: str | Path, *, label: str) -> tuple[Path, tuple[str, ...]]:
        candidate = Path(path_like).expanduser()
        if not candidate.is_absolute():
            candidate = self.root_path / candidate
        normalized = Path(os.path.abspath(str(candidate)))
        try:
            relative = normalized.relative_to(self.root_path)
        except ValueError as exc:
            raise _forbidden(f"{label} path escapes the job result root") from exc
        parts = tuple(relative.parts)
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise _forbidden(f"{label} path traversal is forbidden")
        return normalized, parts

    def open(self, path_like: str | Path, *, label: str) -> tuple[Path, BinaryIO]:
        logical_path, parts = self.normalize(path_like, label=label)
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        file_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        current_fd = os.dup(self._fd)
        file_fd = -1
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, directory_flags, dir_fd=current_fd)
                if not stat.S_ISDIR(os.fstat(next_fd).st_mode):
                    os.close(next_fd)
                    raise OSError("intermediate component is not a directory")
                os.close(current_fd)
                current_fd = next_fd
            file_fd = os.open(parts[-1], file_flags, dir_fd=current_fd)
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise OSError("artifact is not a regular file")
            if metadata.st_nlink != 1:
                raise OSError("hard-linked artifacts are forbidden")
            handle = os.fdopen(file_fd, "rb")
            file_fd = -1
            return logical_path, handle
        except OSError as exc:
            raise _forbidden(f"{label} file could not be opened safely") from exc
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            os.close(current_fd)


def open_confined_regular_file(
    root: str | Path,
    path_like: str | Path,
    *,
    label: str,
) -> tuple[Path, BinaryIO]:
    """Open a regular file through a no-symlink directory-descriptor walk."""

    with _ConfinedArtifactRoot(root, label=label) as confined:
        return confined.open(path_like, label=label)


def read_confined_json_object(
    root: str | Path,
    path_like: str | Path,
    *,
    label: str,
    maximum_bytes: int = 16 * 1024 * 1024,
    missing_ok: bool = False,
) -> dict[str, Any] | None:
    """Read bounded JSON through one confined, no-follow regular-file descriptor."""

    try:
        with _ConfinedArtifactRoot(root, label=label) as confined:
            _, handle = confined.open(path_like, label=label)
            with handle:
                payload_bytes = handle.read(maximum_bytes + 1)
    except HTTPException as exc:
        if missing_ok and isinstance(exc.__cause__, FileNotFoundError):
            return None
        raise
    except OSError as exc:
        raise _forbidden(f"{label} file could not be read safely") from exc

    if len(payload_bytes) > maximum_bytes:
        raise _forbidden(f"{label} exceeds the permitted size")
    try:
        payload = json.loads(payload_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _forbidden(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise _forbidden(f"{label} root must be a JSON object")
    return payload


def _hash_handle(
    handle: BinaryIO,
    *,
    snapshot: bool = False,
) -> tuple[str, BinaryIO | None]:
    digest = hashlib.sha256()
    captured: BinaryIO | None = None
    if snapshot:
        captured = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    try:
        handle.seek(0)
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            if captured is not None:
                captured.write(chunk)
        if captured is not None:
            captured.seek(0)
        return digest.hexdigest(), captured
    except Exception:
        if captured is not None:
            captured.close()
        raise


def _matching_required_value(
    status_value: object,
    record_value: object,
    *,
    label: str,
) -> str:
    status_text = str(status_value or "").strip()
    record_text = str(record_value or "").strip()
    if not status_text or not record_text:
        raise _forbidden(f"completed job is missing durable {label} provenance")
    if status_text != record_text:
        raise _forbidden(f"{label} provenance paths disagree")
    return status_text


def _matching_sha256(status_value: object, record_value: object, *, label: str) -> str:
    status_digest = str(status_value or "").strip().lower()
    record_digest = str(record_value or "").strip().lower()
    if (
        _SHA256_RE.fullmatch(status_digest) is None
        or _SHA256_RE.fullmatch(record_digest) is None
    ):
        raise _forbidden(f"completed job is missing a durable {label} fingerprint")
    if not hmac.compare_digest(status_digest, record_digest):
        raise _forbidden(f"{label} fingerprints disagree")
    return record_digest


def _load_json_object(handle: BinaryIO, *, label: str) -> dict[str, Any]:
    try:
        handle.seek(0)
        payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _forbidden(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise _forbidden(f"{label} root must be a JSON object")
    return payload


def _evidence_bundle_fingerprint(handle: BinaryIO) -> tuple[str, EvidenceBundle]:
    payload = _load_json_object(handle, label="evidence bundle")
    try:
        bundle = EvidenceBundle(**payload)
        return bundle.fingerprint(), bundle
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise _forbidden("evidence bundle contract verification failed") from exc


def _published_attempt_prefix(record: dict[str, Any]) -> tuple[str, str] | None:
    published_status_path = str(record.get("published_status_path", "") or "").strip()
    if not published_status_path:
        return None
    worker_id = str(record.get("published_worker_id", "") or "")
    attempt_count = int(record.get("published_attempt_count", 0) or 0)
    token_sha256 = str(
        record.get("published_attempt_token_sha256", "") or ""
    ).lower()
    if not worker_id or attempt_count < 1 or _SHA256_RE.fullmatch(token_sha256) is None:
        raise _forbidden("completed job is missing published attempt provenance")
    worker_sha256 = hashlib.sha256(worker_id.encode("utf-8")).hexdigest()
    return (
        ".attempts",
        f"attempt-{attempt_count:06d}-{worker_sha256}-{token_sha256}",
    )


def _require_attempt_prefix(
    confined: _ConfinedArtifactRoot,
    path_like: str | Path,
    *,
    expected_prefix: tuple[str, str] | None,
    label: str,
) -> None:
    if expected_prefix is None:
        return
    _, parts = confined.normalize(path_like, label=label)
    if parts[:2] != expected_prefix:
        raise _forbidden(f"{label} is not bound to the published attempt")


def _exact_json_value_matches(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _exact_json_value_matches(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _exact_json_value_matches(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _require_published_worker_provenance(
    *,
    status_data: dict[str, Any],
    manifest: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Verify the selected attempt and optional signed runtime qualification."""

    status_provenance = status_data.get("worker_provenance")
    manifest_provenance = manifest.get("worker_provenance")
    if not isinstance(status_provenance, dict):
        raise _forbidden("published status worker attempt provenance mismatch")
    if not isinstance(manifest_provenance, dict):
        raise _forbidden("result manifest worker attempt provenance mismatch")
    if not _exact_json_value_matches(status_provenance, manifest_provenance):
        raise _forbidden("published status and result manifest provenance disagree")

    base_keys = set(expected)
    observed_keys = set(status_provenance)
    runtime_key = "validated_runner_runtime_qualification"
    optional_keys = {runtime_key, EXECUTION_EVIDENCE_PROVENANCE_KEY}
    if not base_keys.issubset(observed_keys) or not observed_keys.issubset(
        base_keys | optional_keys
    ):
        raise _forbidden("published worker attempt provenance fields are invalid")
    for key, expected_value in expected.items():
        observed_value = status_provenance.get(key)
        if type(observed_value) is not type(expected_value) or observed_value != expected_value:
            raise _forbidden("published status worker attempt provenance mismatch")

    runtime_qualification = status_provenance.get(runtime_key)
    if runtime_qualification is None:
        if any(key in status_data for key in _RUNTIME_QUALIFICATION_KEYS):
            raise _forbidden(
                "validated runner runtime qualification is not signed"
            )
    else:
        if not isinstance(runtime_qualification, dict) or set(
            runtime_qualification
        ) != set(_RUNTIME_QUALIFICATION_KEYS):
            raise _forbidden("validated runner runtime qualification provenance is invalid")
        if (
            type(
                runtime_qualification[
                    "validated_runner_namespace_runtime_qualified"
                ]
            )
            is not bool
            or runtime_qualification[
                "validated_runner_namespace_runtime_qualified"
            ]
            is not True
        ):
            raise _forbidden("validated runner runtime qualification provenance is invalid")
        schema_version = runtime_qualification[
            "validated_runner_namespace_runtime_receipt_schema_version"
        ]
        receipt_sha256 = runtime_qualification[
            "validated_runner_namespace_runtime_receipt_sha256"
        ]
        issued_at_utc = runtime_qualification[
            "validated_runner_namespace_runtime_receipt_issued_at_utc"
        ]
        expires_at_utc = runtime_qualification[
            "validated_runner_namespace_runtime_receipt_expires_at_utc"
        ]
        if type(schema_version) is not str or schema_version != RECEIPT_SCHEMA_VERSION:
            raise _forbidden("validated runner runtime qualification provenance is invalid")
        if (
            type(receipt_sha256) is not str
            or _SHA256_RE.fullmatch(receipt_sha256) is None
        ):
            raise _forbidden("validated runner runtime qualification provenance is invalid")
        if type(issued_at_utc) is not str or type(expires_at_utc) is not str:
            raise _forbidden("validated runner runtime qualification provenance is invalid")
        try:
            issued_at = dt.datetime.strptime(
                issued_at_utc,
                _RUNTIME_QUALIFICATION_TIMESTAMP_FORMAT,
            ).replace(tzinfo=dt.timezone.utc)
            expires_at = dt.datetime.strptime(
                expires_at_utc,
                _RUNTIME_QUALIFICATION_TIMESTAMP_FORMAT,
            ).replace(tzinfo=dt.timezone.utc)
        except ValueError as exc:
            raise _forbidden(
                "validated runner runtime qualification provenance is invalid"
            ) from exc
        if expires_at <= issued_at or expires_at - issued_at > MAX_RECEIPT_VALIDITY:
            raise _forbidden("validated runner runtime qualification provenance is invalid")
        for key in _RUNTIME_QUALIFICATION_KEYS:
            status_value = status_data.get(key)
            signed_value = runtime_qualification[key]
            if (
                type(status_value) is not type(signed_value)
                or status_value != signed_value
            ):
                raise _forbidden(
                    "validated runner runtime qualification status binding mismatch"
                )

    execution_evidence = status_provenance.get(EXECUTION_EVIDENCE_PROVENANCE_KEY)
    status_execution_evidence = status_data.get(EXECUTION_EVIDENCE_PROVENANCE_KEY)
    if execution_evidence is None:
        if status_execution_evidence is not None:
            raise _forbidden("validated runner execution evidence is not signed")
    else:
        try:
            validated_evidence = validate_validated_runner_execution_evidence(
                execution_evidence
            )
        except ValueError as exc:
            raise _forbidden(
                "validated runner execution evidence provenance is invalid"
            ) from exc
        if not _exact_json_value_matches(
            status_execution_evidence,
            validated_evidence,
        ):
            raise _forbidden(
                "validated runner execution evidence status binding mismatch"
            )


def verify_completed_result_artifacts(
    *,
    job_id: str,
    record: dict[str, Any],
    status_data: dict[str, Any],
    result_root: str | Path,
    signing_key: str,
    expected_key_id: str,
    snapshot_result: bool = False,
) -> VerifiedResultArtifacts:
    """Verify job/request/result/bundle binding before serving any bytes."""

    if str(record.get("status", "")) != "completed" or str(status_data.get("status", "")) != "completed":
        raise HTTPException(status_code=400, detail="Job is not completed")
    result_snapshot: BinaryIO | None = None
    opened_handles: list[BinaryIO] = []
    try:
        with _ConfinedArtifactRoot(result_root, label="job result") as confined:
            expected_attempt_prefix = _published_attempt_prefix(record)
            if expected_attempt_prefix is not None:
                published_status_path = str(record.get("published_status_path", "") or "")
                _require_attempt_prefix(
                    confined,
                    published_status_path,
                    expected_prefix=expected_attempt_prefix,
                    label="published status",
                )
                _, published_status_handle = confined.open(
                    published_status_path,
                    label="published status",
                )
                opened_handles.append(published_status_handle)
                published_status = _load_json_object(
                    published_status_handle,
                    label="published status",
                )
                if published_status != status_data:
                    raise _forbidden("published status snapshot changed during verification")

            manifest_path, manifest_handle = confined.open(
                _matching_required_value(
                    status_data.get("result_manifest"),
                    record.get("result_manifest_path"),
                    label="result manifest",
                ),
                label="result manifest",
            )
            opened_handles.append(manifest_handle)
            result_path, result_handle = confined.open(
                _matching_required_value(
                    status_data.get("result_file"),
                    record.get("result_file"),
                    label="result file",
                ),
                label="result file",
            )
            opened_handles.append(result_handle)
            evidence_bundle_path, evidence_handle = confined.open(
                _matching_required_value(
                    status_data.get("evidence_bundle"),
                    record.get("evidence_bundle_path"),
                    label="evidence bundle",
                ),
                label="evidence bundle",
            )
            opened_handles.append(evidence_handle)

            for artifact_path, label in (
                (manifest_path, "result manifest"),
                (result_path, "result file"),
                (evidence_bundle_path, "evidence bundle"),
            ):
                _require_attempt_prefix(
                    confined,
                    artifact_path,
                    expected_prefix=expected_attempt_prefix,
                    label=label,
                )

            manifest = _load_json_object(manifest_handle, label="result manifest")
            if not signing_key or not verify_result_manifest(manifest, signing_key=signing_key):
                raise _forbidden("result manifest signature verification failed")
            if str(manifest.get("signature_key_id", "")) != str(expected_key_id or ""):
                raise _forbidden("result manifest key ID does not match active configuration")
            if str(manifest.get("job_id", "")) != str(job_id):
                raise _forbidden("result manifest job binding mismatch")
            if str(manifest.get("status", "")) != "completed":
                raise _forbidden("result manifest status is not completed")
            if expected_attempt_prefix is not None:
                expected_worker_provenance = {
                    "worker_id": str(record.get("published_worker_id", "") or ""),
                    "attempt_count": int(record.get("published_attempt_count", 0) or 0),
                    "attempt_token_sha256": str(
                        record.get("published_attempt_token_sha256", "") or ""
                    ).lower(),
                }
                _require_published_worker_provenance(
                    status_data=status_data,
                    manifest=manifest,
                    expected=expected_worker_provenance,
                )

            request_sha = str(record.get("request_sha256", "") or "").lower()
            if _SHA256_RE.fullmatch(request_sha) is None:
                raise _forbidden("completed job is missing a durable request fingerprint")
            if str(manifest.get("request_sha256", "")) != request_sha:
                raise _forbidden("result manifest request binding mismatch")
            execution_request_sha = str(
                record.get("execution_request_sha256", "") or ""
            ).lower()
            if _SHA256_RE.fullmatch(execution_request_sha) is None:
                raise _forbidden(
                    "completed job is missing a durable execution request fingerprint"
                )
            if not hmac.compare_digest(
                str(manifest.get("execution_request_sha256", "")),
                execution_request_sha,
            ):
                raise _forbidden("result manifest execution request binding mismatch")
            execution_transform_id = str(
                record.get("execution_request_transform_id", "") or ""
            ).strip()
            if not execution_transform_id:
                raise _forbidden(
                    "completed job is missing a durable execution request transform"
                )
            if (
                str(manifest.get("execution_request_transform_id", ""))
                != execution_transform_id
            ):
                raise _forbidden("result manifest request transform binding mismatch")

            manifest_result, _ = confined.normalize(
                str(manifest.get("result_file", "") or ""),
                label="manifest result file",
            )
            if manifest_result != result_path:
                raise _forbidden("result manifest file binding mismatch")

            result_sha, result_snapshot = _hash_handle(
                result_handle,
                snapshot=snapshot_result,
            )
            if str(manifest.get("result_file_sha256", "")) != result_sha:
                raise _forbidden("result file SHA-256 verification failed")

            recorded_evidence_fingerprint = _matching_sha256(
                status_data.get("evidence_bundle_sha256"),
                record.get("evidence_bundle_sha256"),
                label="evidence bundle",
            )
            evidence_fingerprint, evidence_bundle = _evidence_bundle_fingerprint(
                evidence_handle
            )
            if not hmac.compare_digest(
                evidence_fingerprint,
                recorded_evidence_fingerprint,
            ):
                raise _forbidden("evidence bundle fingerprint verification failed")
            evidence_input_hash = str(
                evidence_bundle.source_hashes.get("input_hash", "") or ""
            ).lower()
            if not hmac.compare_digest(evidence_input_hash, execution_request_sha):
                raise _forbidden("evidence bundle execution request binding mismatch")
            request_provenance = evidence_bundle.request_provenance
            if not hmac.compare_digest(
                str(request_provenance.get("admission_request_sha256", "") or "").lower(),
                request_sha,
            ):
                raise _forbidden("evidence bundle admission request binding mismatch")
            if not hmac.compare_digest(
                str(request_provenance.get("execution_request_sha256", "") or "").lower(),
                execution_request_sha,
            ):
                raise _forbidden("evidence bundle execution provenance mismatch")
            if (
                str(request_provenance.get("execution_request_transform_id", "") or "")
                != execution_transform_id
            ):
                raise _forbidden("evidence bundle request transform binding mismatch")

            inferred = infer_result_artifact_metadata(result_path)
            manifest_media_type = str(
                manifest.get("result_file_media_type", "")
                or inferred["result_file_media_type"]
            )
            manifest_artifact_type = str(
                manifest.get("result_artifact_type", "")
                or inferred["result_artifact_type"]
            )
            if manifest_media_type not in _ALLOWED_MEDIA_TYPES:
                raise _forbidden("result media type is not allowed")
            if manifest_media_type != inferred["result_file_media_type"]:
                raise _forbidden("result media type does not match file suffix")
            if manifest_artifact_type != inferred["result_artifact_type"]:
                raise _forbidden("result artifact type does not match file suffix")

            return VerifiedResultArtifacts(
                root=confined.root_path,
                manifest_path=manifest_path,
                result_path=result_path,
                evidence_bundle_path=evidence_bundle_path,
                manifest=manifest,
                result_sha256=result_sha,
                evidence_bundle_sha256=evidence_fingerprint,
                media_type=manifest_media_type,
                artifact_type=manifest_artifact_type,
                result_snapshot=result_snapshot,
            )
    except Exception:
        if result_snapshot is not None:
            result_snapshot.close()
        raise
    finally:
        for handle in opened_handles:
            handle.close()


__all__ = [
    "VerifiedResultArtifacts",
    "open_confined_regular_file",
    "verify_completed_result_artifacts",
]
