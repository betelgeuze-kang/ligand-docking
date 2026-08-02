"""Terminal, owner-only artifact manifest for the Fresh-128 lane.

The Fresh report is not sufficient retention evidence by itself.  This module
walks the completed run directory without following links, records every file
that existed immediately before the terminal completion receipt, and verifies
the same closed file set later.  The manifest never grants scientific,
product, or exactly-once authority; it only proves local artifact-set
integrity for one retained run directory.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat


FRESH_ARTIFACT_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_fresh_redocking_artifact_manifest/1.0.0"
)
FRESH_ARTIFACT_MANIFEST_FILENAME = "fresh-redocking-artifact-manifest.json"
FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME = "stage0-policy-snapshot.json"
FRESH_EXECUTION_ENVIRONMENT_FILENAME = "execution-environment-receipt.json"
FRESH_EXECUTION_LOG_FILENAME = "execution-log-receipt.json"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_FILE_BYTES = 1024 * 1024 * 1024
_MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
_MAX_FILE_COUNT = 4096


class FreshArtifactManifestError(ValueError):
    """The retained Fresh-128 artifact set is unsafe, incomplete, or changed."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise FreshArtifactManifestError(
            "Fresh artifact manifest is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise FreshArtifactManifestError(f"{name} must be a lowercase SHA-256")
    return value


def _require_text(value: object, *, name: str) -> str:
    if type(value) is not str or not value or len(value) > 512:
        raise FreshArtifactManifestError(f"{name} must be bounded non-empty text")
    return value


def _descriptor_sha256(descriptor: int) -> str:
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def _open_root(root: Path) -> tuple[Path, int]:
    if not root.is_absolute() or any(part in {".", ".."} for part in root.parts):
        raise FreshArtifactManifestError(
            "Fresh artifact root must be an absolute lexical path"
        )
    if root != Path(os.path.abspath(root)):
        raise FreshArtifactManifestError("Fresh artifact root must be normalized")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(root, flags)
    except OSError as exc:
        raise FreshArtifactManifestError(
            "Fresh artifact root is missing or contains a symlink"
        ) from exc
    status = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(status.st_mode)
        or stat.S_IMODE(status.st_mode) != 0o700
        or (hasattr(os, "geteuid") and status.st_uid != os.geteuid())
    ):
        os.close(descriptor)
        raise FreshArtifactManifestError(
            "Fresh artifact root must be an owner-only directory"
        )
    return root, descriptor


def _entry_role(relative_path: str) -> str:
    path = PurePosixPath(relative_path)
    parts = path.parts
    if relative_path == "fresh-redocking-run-once-reservation.json":
        return "local_attempt_reservation"
    if relative_path == "stage0-admission-receipt.json":
        return "stage0_admission_receipt"
    if relative_path == FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME:
        return "stage0_policy_snapshot"
    if relative_path == FRESH_EXECUTION_ENVIRONMENT_FILENAME:
        return "execution_environment_receipt"
    if relative_path == FRESH_EXECUTION_LOG_FILENAME:
        return "execution_log_receipt"
    if relative_path == "fresh-redocking-internal-report.json":
        return "fresh_internal_report"
    if (
        len(parts) == 2
        and parts[0] == "private-external-binary"
        and _SHA256_RE.fullmatch(parts[1]) is not None
    ):
        return "gnina_binary"
    if (
        len(parts) == 3
        and parts[0] == "receipts"
        and parts[1] == "materializations"
        and parts[2].endswith(".json")
    ):
        return "materialization_receipt"
    if (
        len(parts) == 3
        and parts[0] == "receipts"
        and parts[1] in {"engine_v2", "vina", "gnina"}
        and parts[2].endswith(".json")
    ):
        return "engine_execution_receipt"
    if (
        len(parts) == 3
        and parts[0] == "poses"
        and parts[1] in {"engine_v2", "vina", "gnina"}
        and parts[2].endswith(".sdf")
    ):
        return "pose_output"
    raise FreshArtifactManifestError(
        f"unexpected retained Fresh artifact: {relative_path}"
    )


def _directory_allowed(relative_path: str) -> bool:
    return relative_path in {
        "inputs",
        "poses",
        "poses/engine_v2",
        "poses/vina",
        "poses/gnina",
        "private-external-binary",
        "receipts",
        "receipts/materializations",
        "receipts/engine_v2",
        "receipts/vina",
        "receipts/gnina",
    }


def _scan_directory(
    descriptor: int,
    *,
    prefix: tuple[str, ...],
    excluded_root_names: frozenset[str],
    entries: list[dict[str, object]],
) -> None:
    try:
        names = sorted(os.listdir(descriptor))
    except OSError as exc:
        raise FreshArtifactManifestError(
            "Fresh artifact directory could not be enumerated"
        ) from exc
    for name in names:
        if not name or name in {".", ".."} or "/" in name or "\x00" in name:
            raise FreshArtifactManifestError("Fresh artifact name is invalid")
        if not prefix and name in excluded_root_names:
            continue
        try:
            status = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except OSError as exc:
            raise FreshArtifactManifestError(
                "Fresh artifact changed during enumeration"
            ) from exc
        relative_parts = (*prefix, name)
        relative_path = PurePosixPath(*relative_parts).as_posix()
        if stat.S_ISDIR(status.st_mode):
            if (
                not _directory_allowed(relative_path)
                or stat.S_IMODE(status.st_mode) != 0o700
                or (hasattr(os, "geteuid") and status.st_uid != os.geteuid())
            ):
                raise FreshArtifactManifestError(
                    f"Fresh artifact directory is not owner-only: {relative_path}"
                )
            flags = (
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                child = os.open(name, flags, dir_fd=descriptor)
            except OSError as exc:
                raise FreshArtifactManifestError(
                    f"Fresh artifact directory cannot be pinned: {relative_path}"
                ) from exc
            try:
                pinned_status = os.fstat(child)
                if (pinned_status.st_dev, pinned_status.st_ino) != (
                    status.st_dev,
                    status.st_ino,
                ):
                    raise FreshArtifactManifestError(
                        f"Fresh artifact directory changed: {relative_path}"
                    )
                _scan_directory(
                    child,
                    prefix=relative_parts,
                    excluded_root_names=excluded_root_names,
                    entries=entries,
                )
            finally:
                os.close(child)
            continue
        if not stat.S_ISREG(status.st_mode):
            raise FreshArtifactManifestError(
                f"Fresh artifact must be a regular file: {relative_path}"
            )
        role = _entry_role(relative_path)
        expected_mode = 0o500 if role == "gnina_binary" else 0o600
        if (
            status.st_nlink != 1
            or stat.S_IMODE(status.st_mode) != expected_mode
            or (hasattr(os, "geteuid") and status.st_uid != os.geteuid())
            or status.st_size < 1
            or status.st_size > _MAX_FILE_BYTES
        ):
            raise FreshArtifactManifestError(
                f"Fresh artifact ownership or bounds are invalid: {relative_path}"
            )
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            file_descriptor = os.open(name, flags, dir_fd=descriptor)
        except OSError as exc:
            raise FreshArtifactManifestError(
                f"Fresh artifact cannot be pinned: {relative_path}"
            ) from exc
        try:
            pinned_status = os.fstat(file_descriptor)
            if (
                not stat.S_ISREG(pinned_status.st_mode)
                or (pinned_status.st_dev, pinned_status.st_ino)
                != (status.st_dev, status.st_ino)
                or pinned_status.st_size != status.st_size
                or pinned_status.st_nlink != 1
            ):
                raise FreshArtifactManifestError(
                    f"Fresh artifact changed while pinned: {relative_path}"
                )
            sha256 = _descriptor_sha256(file_descriptor)
            final_status = os.fstat(file_descriptor)
            if (
                final_status.st_size != pinned_status.st_size
                or final_status.st_mtime_ns != pinned_status.st_mtime_ns
                or final_status.st_ctime_ns != pinned_status.st_ctime_ns
            ):
                raise FreshArtifactManifestError(
                    f"Fresh artifact changed while hashed: {relative_path}"
                )
        finally:
            os.close(file_descriptor)
        entries.append(
            {
                "relative_path": relative_path,
                "artifact_role": role,
                "size_bytes": status.st_size,
                "mode_octal": f"{expected_mode:04o}",
                "sha256": sha256,
            }
        )
        if (
            len(entries) > _MAX_FILE_COUNT
            or sum(int(entry["size_bytes"]) for entry in entries) > _MAX_TOTAL_BYTES
        ):
            raise FreshArtifactManifestError(
                "Fresh artifact set exceeds its frozen retention bounds"
            )


def scan_fresh_artifacts(
    output_root: Path,
    *,
    exclude_root_names: Sequence[str] = (),
) -> list[dict[str, object]]:
    """Return the descriptor-pinned, sorted local artifact inventory."""

    root, descriptor = _open_root(output_root)
    del root
    try:
        entries: list[dict[str, object]] = []
        _scan_directory(
            descriptor,
            prefix=(),
            excluded_root_names=frozenset(exclude_root_names),
            entries=entries,
        )
    finally:
        os.close(descriptor)
    entries.sort(key=lambda row: str(row["relative_path"]))
    if not entries:
        raise FreshArtifactManifestError("Fresh artifact set is empty")
    return entries


def build_fresh_artifact_manifest(
    *,
    output_root: Path,
    runner_id: str,
    retention_root: str,
    reservation_sha256: str,
    report_fingerprint_sha256: str,
    report_file_sha256: str,
    stage0_policy_sha256: str,
    source_freeze_sha256: str,
    execution_profile_sha256: str,
    fresh_holdout_manifest_sha256: str,
    completion_filename: str,
) -> dict[str, object]:
    """Build the one terminal inventory written before completion."""

    if not retention_root.startswith(".betelgeuze/"):
        raise FreshArtifactManifestError("retention_root is outside .betelgeuze")
    entries = scan_fresh_artifacts(
        output_root,
        exclude_root_names=(FRESH_ARTIFACT_MANIFEST_FILENAME, completion_filename),
    )
    payload: dict[str, object] = {
        "schema_id": FRESH_ARTIFACT_MANIFEST_SCHEMA_ID,
        "runner_id": _require_text(runner_id, name="runner_id"),
        "retention_root": retention_root,
        "reservation_sha256": _require_digest(
            reservation_sha256, name="reservation_sha256"
        ),
        "report_fingerprint_sha256": _require_digest(
            report_fingerprint_sha256, name="report_fingerprint_sha256"
        ),
        "report_file_sha256": _require_digest(
            report_file_sha256, name="report_file_sha256"
        ),
        "stage0_policy_sha256": _require_digest(
            stage0_policy_sha256, name="stage0_policy_sha256"
        ),
        "source_freeze_sha256": _require_digest(
            source_freeze_sha256, name="source_freeze_sha256"
        ),
        "execution_profile_sha256": _require_digest(
            execution_profile_sha256, name="execution_profile_sha256"
        ),
        "fresh_holdout_manifest_sha256": _require_digest(
            fresh_holdout_manifest_sha256,
            name="fresh_holdout_manifest_sha256",
        ),
        "file_count": len(entries),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in entries),
        "entries": entries,
        "artifact_set_sha256": _canonical_sha256(entries),
        "terminal_before_completion": True,
        "local_integrity_only": True,
        "exactly_once_authority_granted": False,
        "scientific_validation_granted": False,
        "product_promotion_granted": False,
    }
    payload["manifest_sha256"] = _canonical_sha256(payload)
    verify_fresh_artifact_manifest_document(payload)
    return payload


def verify_fresh_artifact_manifest_document(
    payload: Mapping[str, object],
) -> str:
    """Validate the closed manifest schema and return its self-hash."""

    required = {
        "schema_id",
        "runner_id",
        "retention_root",
        "reservation_sha256",
        "report_fingerprint_sha256",
        "report_file_sha256",
        "stage0_policy_sha256",
        "source_freeze_sha256",
        "execution_profile_sha256",
        "fresh_holdout_manifest_sha256",
        "file_count",
        "total_size_bytes",
        "entries",
        "artifact_set_sha256",
        "terminal_before_completion",
        "local_integrity_only",
        "exactly_once_authority_granted",
        "scientific_validation_granted",
        "product_promotion_granted",
        "manifest_sha256",
    }
    if not isinstance(payload, Mapping) or set(payload) != required:
        raise FreshArtifactManifestError("Fresh artifact manifest fields drifted")
    if (
        payload.get("schema_id") != FRESH_ARTIFACT_MANIFEST_SCHEMA_ID
        or not str(payload.get("retention_root", "")).startswith(".betelgeuze/")
        or payload.get("terminal_before_completion") is not True
        or payload.get("local_integrity_only") is not True
        or payload.get("exactly_once_authority_granted") is not False
        or payload.get("scientific_validation_granted") is not False
        or payload.get("product_promotion_granted") is not False
    ):
        raise FreshArtifactManifestError("Fresh artifact manifest authority is invalid")
    _require_text(payload.get("runner_id"), name="runner_id")
    for name in (
        "reservation_sha256",
        "report_fingerprint_sha256",
        "report_file_sha256",
        "stage0_policy_sha256",
        "source_freeze_sha256",
        "execution_profile_sha256",
        "fresh_holdout_manifest_sha256",
        "artifact_set_sha256",
        "manifest_sha256",
    ):
        _require_digest(payload.get(name), name=name)
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, Sequence) or isinstance(
        raw_entries, (str, bytes, bytearray)
    ):
        raise FreshArtifactManifestError("Fresh artifact entries must be an array")
    entries: list[dict[str, object]] = []
    entry_fields = {
        "relative_path",
        "artifact_role",
        "size_bytes",
        "mode_octal",
        "sha256",
    }
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping) or set(raw_entry) != entry_fields:
            raise FreshArtifactManifestError("Fresh artifact entry fields drifted")
        relative_path = _require_text(
            raw_entry.get("relative_path"), name="relative_path"
        )
        pure = PurePosixPath(relative_path)
        if (
            pure.is_absolute()
            or pure.as_posix() != relative_path
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise FreshArtifactManifestError("Fresh artifact path is not normalized")
        expected_role = _entry_role(relative_path)
        if raw_entry.get("artifact_role") != expected_role:
            raise FreshArtifactManifestError("Fresh artifact role is cross-wired")
        expected_mode = "0500" if expected_role == "gnina_binary" else "0600"
        if (
            type(raw_entry.get("size_bytes")) is not int
            or not 1 <= int(raw_entry["size_bytes"]) <= _MAX_FILE_BYTES
            or raw_entry.get("mode_octal") != expected_mode
        ):
            raise FreshArtifactManifestError("Fresh artifact bounds are invalid")
        _require_digest(raw_entry.get("sha256"), name="entry sha256")
        entries.append(dict(raw_entry))
    if (
        not entries
        or len(entries) > _MAX_FILE_COUNT
        or entries != sorted(entries, key=lambda row: str(row["relative_path"]))
        or len({str(row["relative_path"]) for row in entries}) != len(entries)
        or payload.get("file_count") != len(entries)
        or payload.get("total_size_bytes")
        != sum(int(row["size_bytes"]) for row in entries)
        or int(payload["total_size_bytes"]) > _MAX_TOTAL_BYTES
        or payload.get("artifact_set_sha256") != _canonical_sha256(entries)
    ):
        raise FreshArtifactManifestError("Fresh artifact inventory is inconsistent")
    projection = dict(payload)
    observed = projection.pop("manifest_sha256")
    expected = _canonical_sha256(projection)
    if observed != expected:
        raise FreshArtifactManifestError("Fresh artifact manifest self-hash is invalid")
    return expected


def verify_fresh_artifact_set(
    *,
    output_root: Path,
    manifest: Mapping[str, object],
    completion_filename: str,
) -> str:
    """Re-scan the retained root and require byte-identical inventory."""

    manifest_sha256 = verify_fresh_artifact_manifest_document(manifest)
    observed = scan_fresh_artifacts(
        output_root,
        exclude_root_names=(FRESH_ARTIFACT_MANIFEST_FILENAME, completion_filename),
    )
    if observed != manifest.get("entries"):
        raise FreshArtifactManifestError("retained Fresh artifact set changed")
    return manifest_sha256


__all__ = [
    "FRESH_ARTIFACT_MANIFEST_FILENAME",
    "FRESH_ARTIFACT_MANIFEST_SCHEMA_ID",
    "FRESH_EXECUTION_ENVIRONMENT_FILENAME",
    "FRESH_EXECUTION_LOG_FILENAME",
    "FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME",
    "FreshArtifactManifestError",
    "build_fresh_artifact_manifest",
    "scan_fresh_artifacts",
    "verify_fresh_artifact_manifest_document",
    "verify_fresh_artifact_set",
]
