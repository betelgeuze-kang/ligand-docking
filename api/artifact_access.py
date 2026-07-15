"""Confined, signed, content-addressed access to completed API artifacts."""

from __future__ import annotations

from dataclasses import dataclass
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
from betelgeuze_ai_md.contracts import EvidenceBundle
from betelgeuze_ai_md.contracts.errors import ContractValidationError


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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
        file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
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
            if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                raise OSError("artifact is not a regular file")
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

            manifest = _load_json_object(manifest_handle, label="result manifest")
            if not signing_key or not verify_result_manifest(manifest, signing_key=signing_key):
                raise _forbidden("result manifest signature verification failed")
            if str(manifest.get("signature_key_id", "")) != str(expected_key_id or ""):
                raise _forbidden("result manifest key ID does not match active configuration")
            if str(manifest.get("job_id", "")) != str(job_id):
                raise _forbidden("result manifest job binding mismatch")
            if str(manifest.get("status", "")) != "completed":
                raise _forbidden("result manifest status is not completed")

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
