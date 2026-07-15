"""Confined, signed, content-addressed access to completed API artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, BinaryIO, Iterator

from fastapi import HTTPException

from api.result_manifest import infer_result_artifact_metadata, verify_result_manifest


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


def _open_regular_no_follow(path: Path, *, label: str) -> BinaryIO:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise _forbidden(f"{label} file could not be opened safely") from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise _forbidden(f"{label} must be a regular file")
        return os.fdopen(fd, "rb")
    except Exception:
        os.close(fd)
        raise


def _hash_file(
    path: Path,
    *,
    label: str,
    snapshot: bool = False,
) -> tuple[str, BinaryIO | None]:
    digest = hashlib.sha256()
    captured: BinaryIO | None = None
    if snapshot:
        captured = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    try:
        with _open_regular_no_follow(path, label=label) as handle:
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


def sha256_file(path: Path) -> str:
    digest, _ = _hash_file(path, label="artifact")
    return digest


def confined_regular_file(
    root: str | Path,
    path_like: str | Path,
    *,
    label: str,
) -> Path:
    """Resolve a regular file below root without traversing symlinks."""

    root_path = Path(root).expanduser()
    if not root_path.exists() or not root_path.is_dir() or root_path.is_symlink():
        raise _forbidden(f"{label} root is unavailable")
    resolved_root = root_path.resolve(strict=True)
    candidate = Path(path_like).expanduser()
    if not candidate.is_absolute():
        candidate = resolved_root / candidate
    try:
        relative = candidate.absolute().relative_to(resolved_root)
    except ValueError as exc:
        raise _forbidden(f"{label} path escapes the job result root") from exc
    if ".." in relative.parts:
        raise _forbidden(f"{label} path traversal is forbidden")
    current = resolved_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise _forbidden(f"{label} path may not traverse symlinks")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise _forbidden(f"{label} file is unavailable or outside the job result root") from exc
    if not resolved.is_file():
        raise _forbidden(f"{label} must be a regular file")
    return resolved


def _unique_path(*values: object, label: str) -> str:
    observed = {str(value or "").strip() for value in values if str(value or "").strip()}
    if not observed:
        raise _forbidden(f"completed job is missing {label} provenance")
    if len(observed) != 1:
        raise _forbidden(f"{label} provenance paths disagree")
    return observed.pop()


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        with _open_regular_no_follow(path, label=label) as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _forbidden(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise _forbidden(f"{label} root must be a JSON object")
    return payload


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
    manifest_path = confined_regular_file(
        result_root,
        _unique_path(
            status_data.get("result_manifest"),
            record.get("result_manifest_path"),
            label="result manifest",
        ),
        label="result manifest",
    )
    result_path = confined_regular_file(
        result_root,
        _unique_path(
            status_data.get("result_file"),
            record.get("result_file"),
            label="result file",
        ),
        label="result file",
    )
    evidence_bundle_path = confined_regular_file(
        result_root,
        _unique_path(
            status_data.get("evidence_bundle"),
            record.get("evidence_bundle_path"),
            label="evidence bundle",
        ),
        label="evidence bundle",
    )

    result_snapshot: BinaryIO | None = None
    try:
        manifest = _load_json_object(manifest_path, label="result manifest")
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

        manifest_result = confined_regular_file(
            result_root,
            str(manifest.get("result_file", "") or ""),
            label="manifest result file",
        )
        if manifest_result != result_path:
            raise _forbidden("result manifest file binding mismatch")

        result_sha, result_snapshot = _hash_file(
            result_path,
            label="result file",
            snapshot=snapshot_result,
        )
        if str(manifest.get("result_file_sha256", "")) != result_sha:
            raise _forbidden("result file SHA-256 verification failed")

        evidence_sha, _ = _hash_file(evidence_bundle_path, label="evidence bundle")
        recorded_evidence_hashes = {
            str(value or "").lower()
            for value in (
                status_data.get("evidence_bundle_sha256"),
                record.get("evidence_bundle_sha256"),
            )
            if str(value or "").strip()
        }
        if len(recorded_evidence_hashes) != 1 or evidence_sha not in recorded_evidence_hashes:
            raise _forbidden("evidence bundle SHA-256 verification failed")

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
            root=Path(result_root).resolve(strict=True),
            manifest_path=manifest_path,
            result_path=result_path,
            evidence_bundle_path=evidence_bundle_path,
            manifest=manifest,
            result_sha256=result_sha,
            evidence_bundle_sha256=evidence_sha,
            media_type=manifest_media_type,
            artifact_type=manifest_artifact_type,
            result_snapshot=result_snapshot,
        )
    except Exception:
        if result_snapshot is not None:
            result_snapshot.close()
        raise


__all__ = [
    "VerifiedResultArtifacts",
    "confined_regular_file",
    "sha256_file",
    "verify_completed_result_artifacts",
]
