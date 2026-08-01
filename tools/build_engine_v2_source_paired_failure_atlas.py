#!/usr/bin/env python3
"""Build a nonclaimable failure atlas from the exact historical torsion A/B."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import statistics
import subprocess
import tarfile
import tempfile

from betelgeuze_engine_v2.benchmark.blind_stage0 import _typed_development_result
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_CANDIDATE_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_DIAGNOSTIC_SCHEMA_ID,
    PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID,
    PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS,
    PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
    PUBLIC_REDOCKING_PROPOSAL_MODES,
    PUBLIC_REDOCKING_RUNNER_ID,
    PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
    PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE,
    _SOURCE_PAIRED_TORSION_RESCUE_REFINEMENT_RECEIPT_FIELDS,
    frozen_public_redocking_case_seed,
)


SCHEMA_ID = "betelgeuze.engine_v2_source_paired_failure_atlas/2.0.0"
AB_SCHEMA_ID = "betelgeuze.engine_v2_source_paired_torsion_rescue_development_ab/1.1.0"
ANALYSIS_SCHEMA_ID = "betelgeuze.engine_v2_scorer_v1_development_analysis/1.2.0"
SUMMARY_SCHEMA_ID = (
    "betelgeuze.engine_v2_historical_development_execution_summary/1.0.0"
)
RESCUE_SUMMARY_SCHEMA_ID = (
    "betelgeuze.engine_v2_historical_development_source_paired_"
    "torsion_rescue_summary/1.0.0"
)
SOURCE_PAIRED_RESCUE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.0.0"
)
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_TAR_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_MEMBER_MANIFEST_BYTES = 256 * 1024
MAX_BUNDLE_CHECKSUM_BYTES = 4 * 1024
EXPECTED_EVIDENCE_ARCHIVE_SHA256 = (
    "8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc"
)
EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256 = (
    "7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21"
)
EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256 = (
    "6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9"
)
EXPECTED_EVIDENCE_MEMBER_COUNT = 59
EXPECTED_SOURCE_COMMIT_SHA256 = "754bebb9ddc2fbffdaca5d4143ff515c3b38c032"
EXPECTED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6M73_FNR",
    "6T88_MWQ",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
EXPECTED_CASE_IDS_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
EXPECTED_UNCOVERED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
EXPECTED_PREPARATION_FAILURE_CASE_ID = "6M73_FNR"
EXPECTED_RECOVERED_CASE_ID = "6T88_MWQ"
EXPECTED_DECISION = (
    "reject_current_lane_parent_coordinates_retained_and_"
    "selection_eligibility_regressed"
)
_POSEBUSTERS_CHECK_IDS = frozenset(
    (
        *PUBLIC_REDOCKING_POSEBUSTERS_CHEMICAL_CHECK_IDS,
        *PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
    )
)
_INTERNAL_CHECK_IDS = frozenset(("internal_steric_clash", "internal_energy"))
_EXECUTION_FIELDS = frozenset(
    {
        "schema_id",
        "runner_id",
        "archive_sha256",
        "source_ids_sha256",
        "command",
        "execution_policy",
        "input_sha256s",
        "materialization_receipt_sha256",
        "implementation_sha256",
        "evaluation_pipeline_sha256",
        "execution_environment_sha256",
        "cache_read_allowed",
        "fresh_execution",
        "result",
        "receipt_sha256",
    }
)
_MATERIALIZATION_FIELDS = frozenset(
    {
        "schema_id",
        "case_id",
        "frozen_case_seed",
        "source_archive_sha256",
        "archive_members",
        "artifact_sha256s",
        "hash_verified_archive",
        "receipt_sha256",
    }
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _execution_policy_tokens(value: object) -> list[str]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError("execution policy is invalid")
    try:
        return [
            f"{key}={json.dumps(item, allow_nan=False, separators=(',', ':'))}"
            for key, item in sorted(value.items())
        ]
    except (TypeError, ValueError) as exc:
        raise ValueError("execution policy is invalid") from exc


def _sha256_payload(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_sha256(value: object, *, name: str) -> str:
    if not _is_sha256(value):
        raise ValueError(f"{name} is not a SHA-256")
    return str(value)


def _self_hash(payload: Mapping[str, object], *, field: str, name: str) -> str:
    projection = dict(payload)
    observed = projection.pop(field, None)
    if not _is_sha256(observed) or observed != _sha256_payload(projection):
        raise ValueError(f"{name} self-hash is invalid")
    return str(observed)


def _finite_number(value: object, *, name: str) -> float:
    if type(value) not in {int, float}:
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _binary64_hex(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be canonical binary64 hex")
    try:
        decoded = float.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be canonical binary64 hex") from exc
    if not math.isfinite(decoded) or decoded.hex() != value:
        raise ValueError(f"{name} must be canonical binary64 hex")
    return value


def _vector_summary(value: object, *, name: str) -> dict[str, object]:
    if value is None or value == () or value == []:
        return {
            "available": False,
            "binary64_hex": [],
            "norm_binary64_hex": None,
        }
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{name} must contain three binary64 values")
    encoded = [
        _binary64_hex(item, name=f"{name}[{index}]") for index, item in enumerate(value)
    ]
    decoded = [float.fromhex(item) for item in encoded]
    return {
        "available": True,
        "binary64_hex": encoded,
        "norm_binary64_hex": math.sqrt(sum(item * item for item in decoded)).hex(),
    }


def _distribution(values: Sequence[float]) -> dict[str, object]:
    if not values:
        return {
            "count": 0,
            "minimum_binary64_hex": None,
            "median_binary64_hex": None,
            "maximum_binary64_hex": None,
        }
    if any(not math.isfinite(value) for value in values):
        raise ValueError("distribution contains a non-finite value")
    return {
        "count": len(values),
        "minimum_binary64_hex": min(values).hex(),
        "median_binary64_hex": float(statistics.median(values)).hex(),
        "maximum_binary64_hex": max(values).hex(),
    }


def _optional_binary64(payload: Mapping[str, object], field: str) -> float | None:
    value = payload.get(field)
    if value in {None, ""}:
        return None
    return float.fromhex(_binary64_hex(value, name=field))


def _prohibited_path(path: Path, *, name: str) -> None:
    text = path.as_posix().lower()
    normalized = text.replace("_", "-")
    if any(
        marker in normalized
        for marker in ("fresh128", "fresh-128", "fresh-redocking-128")
    ):
        raise ValueError(f"{name} cannot reference fresh-128 state")
    for component in path.parts:
        lowered = component.lower()
        if (
            lowered == ".env"
            or lowered.startswith(".env.")
            or lowered.endswith(".env")
            or ".env." in lowered
        ):
            raise ValueError(f"{name} cannot reference environment files")


def _reject_symlink_ancestry(path: Path, *, name: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            if current.is_symlink():
                raise ValueError(f"{name} cannot use symlink path components")
        except OSError as exc:
            raise ValueError(f"{name} ancestry cannot be inspected") from exc


def _lexical_repository_artifact(
    repo_root: Path,
    path: Path,
    *,
    name: str,
) -> tuple[Path, Path]:
    _prohibited_path(path, name=name)
    _prohibited_path(repo_root, name="repository root")
    if any(component in {"", ".", ".."} for component in path.parts):
        raise ValueError(f"{name} must be an existing repository artifact")
    root = Path(os.path.abspath(repo_root))
    candidate = Path(os.path.abspath(path if path.is_absolute() else root / path))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{name} must be an existing repository artifact") from exc
    if (
        len(relative.parts) < 2
        or relative.parts[0] != ".betelgeuze"
        or any(component in {"", ".", ".."} for component in relative.parts)
    ):
        raise ValueError(f"{name} must be an existing repository artifact")
    _prohibited_path(relative, name=name)
    return root, relative


def _open_absolute_directory_no_symlinks(path: Path, *, name: str) -> int:
    if not path.is_absolute():
        raise ValueError(f"{name} must be absolute")
    descriptor = -1
    try:
        descriptor = os.open(path.anchor, _directory_flags())
        for component in path.parts[1:]:
            next_descriptor = os.open(
                component,
                _directory_flags(),
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        status = os.fstat(descriptor)
        if not stat.S_ISDIR(status.st_mode) or (
            hasattr(os, "geteuid") and status.st_uid != os.geteuid()
        ):
            raise ValueError(f"{name} must be an owned directory")
        return descriptor
    except (OSError, ValueError) as exc:
        if descriptor >= 0:
            os.close(descriptor)
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"{name} cannot be opened safely") from exc


def _safe_member_name(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise ValueError("archive member name is unsafe")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("archive member name is unsafe")
    normalized = path.as_posix()
    if normalized != value or not normalized.startswith(".betelgeuze/"):
        raise ValueError("archive member name is unsafe")
    _prohibited_path(Path(*path.parts), name="archive member")
    return normalized


def _member_manifest(raw: bytes) -> dict[str, str]:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("member manifest is not ASCII") from exc
    if not text.endswith("\n"):
        raise ValueError("member manifest must end with a newline")
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        digest, separator, name = line.partition("  ")
        safe_name = _safe_member_name(name)
        if not separator or not _is_sha256(digest):
            raise ValueError("member manifest row is malformed")
        rows.append((safe_name, digest))
    if not rows or len(rows) != len(set(name for name, _ in rows)):
        raise ValueError("member manifest names are empty or duplicated")
    if rows != sorted(rows):
        raise ValueError("member manifest is not ordered")
    return dict(rows)


def _bundle_rows(raw: bytes) -> tuple[tuple[str, str], ...]:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("bundle checksum is not ASCII") from exc
    if not text.endswith("\n"):
        raise ValueError("bundle checksum must end with a newline")
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        digest, separator, name = line.partition("  ")
        if (
            not separator
            or not _is_sha256(digest)
            or not name
            or "/" in name
            or "\\" in name
        ):
            raise ValueError("bundle checksum row is malformed")
        rows.append((digest, name))
    if len(rows) != 2 or len(set(name for _, name in rows)) != 2:
        raise ValueError("bundle checksum must bind exactly two files")
    return tuple(rows)


def _bounded_repository_artifact_bytes(
    repo_root: Path,
    path: Path,
    *,
    maximum: int,
    name: str,
) -> tuple[bytes, str]:
    root, relative = _lexical_repository_artifact(repo_root, path, name=name)
    directory_descriptor = _open_absolute_directory_no_symlinks(
        root,
        name="repository root",
    )
    file_descriptor = -1
    try:
        for component in relative.parts[:-1]:
            try:
                next_descriptor = os.open(
                    component,
                    _directory_flags(),
                    dir_fd=directory_descriptor,
                )
            except OSError as exc:
                raise ValueError(f"{name} cannot be opened safely") from exc
            status = os.fstat(next_descriptor)
            if not stat.S_ISDIR(status.st_mode) or (
                hasattr(os, "geteuid") and status.st_uid != os.geteuid()
            ):
                os.close(next_descriptor)
                raise ValueError(f"{name} parent must be an owned directory")
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            file_descriptor = os.open(
                relative.name,
                flags,
                dir_fd=directory_descriptor,
            )
        except OSError as exc:
            raise ValueError(f"{name} cannot be opened safely") from exc
        status = os.fstat(file_descriptor)
        if (
            not stat.S_ISREG(status.st_mode)
            or stat.S_IMODE(status.st_mode) != 0o600
            or (hasattr(os, "geteuid") and status.st_uid != os.geteuid())
            or status.st_size > maximum
        ):
            raise ValueError(f"{name} exceeds its bounded regular-file contract")
        with os.fdopen(file_descriptor, "rb", closefd=False) as handle:
            payload = handle.read(maximum + 1)
        if len(payload) > maximum:
            raise ValueError(f"{name} exceeds its bounded regular-file contract")
        return payload, relative.as_posix()
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        os.close(directory_descriptor)


def _bounded_zstd_decompress(archive_raw: bytes) -> bytes:
    if len(archive_raw) > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds the bounded compressed size")
    try:
        with tempfile.TemporaryFile() as verified_archive:
            verified_archive.write(archive_raw)
            verified_archive.seek(0)
            process = subprocess.Popen(
                ("zstd", "-dc"),
                stdin=verified_archive,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            if process.stdout is None:
                process.kill()
                process.wait()
                raise ValueError("zstd decompressor stdout is unavailable")
            payload = process.stdout.read(MAX_TAR_BYTES + 1)
            if len(payload) > MAX_TAR_BYTES:
                process.kill()
                process.wait()
                raise ValueError("archive exceeds the bounded tar size")
            returncode = process.wait()
    except OSError as exc:
        raise ValueError("zstd decompressor is unavailable") from exc
    if returncode != 0:
        raise ValueError("archive failed Zstandard decompression")
    return payload


def _verified_archive_members(
    *,
    repo_root: Path,
    archive_path: Path,
    members_path: Path,
    bundle_path: Path,
    expected_archive_sha256: str,
    expected_members_sha256: str,
    expected_bundle_sha256: str,
) -> tuple[dict[str, bytes], dict[str, object]]:
    for digest, name in (
        (expected_archive_sha256, "expected archive SHA-256"),
        (expected_members_sha256, "expected member-manifest SHA-256"),
        (expected_bundle_sha256, "expected bundle SHA-256"),
    ):
        if not _is_sha256(digest):
            raise ValueError(f"{name} is invalid")
    if (
        expected_archive_sha256 != EXPECTED_EVIDENCE_ARCHIVE_SHA256
        or expected_members_sha256 != EXPECTED_EVIDENCE_MEMBER_MANIFEST_SHA256
        or expected_bundle_sha256 != EXPECTED_EVIDENCE_BUNDLE_CHECKSUM_SHA256
    ):
        raise ValueError("archive bundle does not match the pinned evidence identity")
    archive_raw, archive_relative = _bounded_repository_artifact_bytes(
        repo_root,
        archive_path,
        maximum=MAX_ARCHIVE_BYTES,
        name="archive",
    )
    members_raw, members_relative = _bounded_repository_artifact_bytes(
        repo_root,
        members_path,
        maximum=MAX_MEMBER_MANIFEST_BYTES,
        name="member manifest",
    )
    bundle_raw, bundle_relative = _bounded_repository_artifact_bytes(
        repo_root,
        bundle_path,
        maximum=MAX_BUNDLE_CHECKSUM_BYTES,
        name="bundle checksum",
    )
    if (
        _sha256_bytes(archive_raw) != expected_archive_sha256
        or _sha256_bytes(members_raw) != expected_members_sha256
        or _sha256_bytes(bundle_raw) != expected_bundle_sha256
    ):
        raise ValueError("archive bundle does not match the reviewed identities")
    expected_bundle = (
        (expected_archive_sha256, Path(archive_relative).name),
        (expected_members_sha256, Path(members_relative).name),
    )
    if _bundle_rows(bundle_raw) != expected_bundle:
        raise ValueError("bundle checksum cross-links are invalid")
    manifest = _member_manifest(members_raw)
    if len(manifest) != EXPECTED_EVIDENCE_MEMBER_COUNT:
        raise ValueError(
            "archive member manifest count is not the pinned 59-member set"
        )
    tar_raw = _bounded_zstd_decompress(archive_raw)
    retained: dict[str, bytes] = {}
    observed: dict[str, str] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_raw), mode="r:") as archive:
            for member in archive:
                member_name = _safe_member_name(member.name)
                if (
                    member_name in observed
                    or member_name not in manifest
                    or not member.isreg()
                    or stat.S_IMODE(member.mode) != 0o600
                    or member.uid != 0
                    or member.gid != 0
                    or member.mtime != 0
                    or member.size < 0
                    or member.size > MAX_MEMBER_BYTES
                ):
                    raise ValueError("archive member contract is invalid")
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError("archive member payload is missing")
                payload = handle.read()
                if len(payload) != member.size:
                    raise ValueError("archive member size is inconsistent")
                digest = _sha256_bytes(payload)
                if digest != manifest[member_name]:
                    raise ValueError("archive member hash is inconsistent")
                observed[member_name] = digest
                if member_name.endswith(".json"):
                    retained[member_name] = payload
    except (tarfile.TarError, OSError) as exc:
        raise ValueError("archive tar stream is invalid") from exc
    if observed != manifest:
        raise ValueError("archive member set does not match its manifest")
    return retained, {
        "archive_path": archive_relative,
        "archive_sha256": expected_archive_sha256,
        "archive_size_bytes": len(archive_raw),
        "tar_size_bytes": len(tar_raw),
        "member_manifest_path": members_relative,
        "member_manifest_sha256": expected_members_sha256,
        "bundle_checksum_path": bundle_relative,
        "bundle_checksum_sha256": expected_bundle_sha256,
        "member_count": len(observed),
        "all_members_regular_mode_0600": True,
    }


def _validate_ab_report(report: Mapping[str, object]) -> None:
    _self_hash(report, field="report_sha256", name="A/B report")
    forbidden = set(FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS) | set(
        PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
    )
    case_ids = tuple(report.get("case_ids", ()))
    if (
        report.get("schema_id") != AB_SCHEMA_ID
        or report.get("analysis_scope") != "historical_contaminated_development_only"
        or report.get("source_commit_sha256") != EXPECTED_SOURCE_COMMIT_SHA256
        or case_ids != EXPECTED_CASE_IDS
        or report.get("case_ids_sha256") != EXPECTED_CASE_IDS_SHA256
        or _sha256_payload(list(case_ids)) != EXPECTED_CASE_IDS_SHA256
        or set(case_ids) & forbidden
        or report.get("paired_evidence_bound_by_this_report") is not True
        or report.get("development_only") is not True
        or report.get("claim_safe") is not False
        or report.get("fresh_execution_authorized") is not False
        or report.get("public_claim_eligible") is not False
        or report.get("primary_claim_eligible") is not False
        or report.get("product_promotion_eligible") is not False
        or report.get("scientifically_validated") is not False
        or report.get("stage0_eligible") is not False
    ):
        raise ValueError("A/B report identity or safety boundary is invalid")
    acceptance = report.get("acceptance")
    changes = report.get("candidate_level_changes")
    if (
        not isinstance(acceptance, Mapping)
        or acceptance.get("decision") != EXPECTED_DECISION
        or acceptance.get("rescue_vs_parent_coordinate_change_candidate_count") != 0
        or acceptance.get("selection_eligibility_regression_case_ids")
        != [EXPECTED_RECOVERED_CASE_ID]
        or not isinstance(changes, Mapping)
        or changes.get("baseline_to_rescue_coordinate_change_candidate_count") != 28
        or tuple(changes.get("baseline_to_rescue_coordinate_change_case_ids", ()))
        != (
            "5SD5_HWI",
            "5SIS_JSM",
            "6T88_MWQ",
            "6TW5_9M2",
            "6TW7_NZB",
            "6VTA_AKN",
            "6WTN_RXT",
        )
    ):
        raise ValueError("A/B report decision or candidate changes are invalid")
    expected_metrics = {
        "baseline": (31, 3),
        "rescue": (30, 2),
    }
    for lane, (eligible, native_eligible) in expected_metrics.items():
        lane_row = report.get(lane)
        if not isinstance(lane_row, Mapping):
            raise ValueError(f"A/B report {lane} lane is missing")
        metrics = lane_row.get("metrics")
        if (
            not isinstance(metrics, Mapping)
            or metrics.get("case_count") != 9
            or metrics.get("scored_case_count") != 8
            or metrics.get("preparation_failure_count") != 1
            or metrics.get("candidate_success_count") != 512
            or metrics.get("exact_valid_candidate_count") != 7
            or metrics.get("native_like_candidate_count") != 4
            or metrics.get("native_like_posebusters_exact_valid_candidate_count") != 2
            or metrics.get("selection_eligible_candidate_count") != eligible
            or metrics.get("native_like_selection_eligible_candidate_count")
            != native_eligible
            or metrics.get("proposal_oracle_recovery_case_count") != 1
            or metrics.get("top1_recovery_case_count") != 1
            or metrics.get("top5_recovery_case_count") != 1
            or metrics.get("valid_top1_case_count") != 3
        ):
            raise ValueError(f"A/B report {lane} metrics are invalid")
    rescue = report["rescue"]
    allocation = rescue.get("allocation_and_refinement")
    if (
        not isinstance(allocation, Mapping)
        or allocation.get("allocated_candidate_count") != 28
        or allocation.get("parent_coordinate_duplicate_candidate_count") != 28
        or allocation.get("torsion_selected_candidate_count") != 0
    ):
        raise ValueError("A/B report rescue allocation is invalid")


def _validated_candidate(
    candidate: Mapping[str, object],
    *,
    lane: str,
    case_id: str,
) -> dict[str, object]:
    expected_schema = (
        PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID
        if lane == "baseline"
        else PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_CANDIDATE_SCHEMA_ID
    )
    proposal_index = candidate.get("proposal_index")
    failed_checks = candidate.get("posebusters_failed_check_ids")
    allowed_modes = set(PUBLIC_REDOCKING_PROPOSAL_MODES)
    if lane == "rescue":
        allowed_modes.add(PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE)
    if (
        candidate.get("schema_id") != expected_schema
        or candidate.get("status") != "success"
        or type(proposal_index) is not int
        or not 0 <= proposal_index < PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
        or candidate.get("proposal_mode") not in allowed_modes
        or type(candidate.get("geometric_valid")) is not bool
        or type(candidate.get("chemical_valid")) is not bool
        or type(candidate.get("selection_eligible")) is not bool
        or not isinstance(failed_checks, list)
        or any(check_id not in _POSEBUSTERS_CHECK_IDS for check_id in failed_checks)
    ):
        raise ValueError(f"{lane} {case_id} candidate contract is invalid")
    _finite_number(candidate.get("score"), name="candidate score")
    _finite_number(candidate.get("rmsd_angstrom"), name="candidate RMSD")
    for field in (
        "proposal_fingerprint_sha256",
        "coordinate_fingerprint_sha256",
        "pose_artifact_sha256",
        "score_terms_receipt_sha256",
    ):
        _require_sha256(candidate.get(field), name=f"candidate {field}")
    payload = candidate.get("refinement_receipt_payload")
    receipt_sha256 = candidate.get("refinement_receipt_sha256")
    if not isinstance(payload, Mapping):
        raise ValueError("candidate refinement payload must be an object")
    if payload:
        if (
            not _is_sha256(receipt_sha256)
            or payload.get("receipt_sha256") != receipt_sha256
        ):
            raise ValueError("candidate refinement receipt binding is invalid")
        _self_hash(payload, field="receipt_sha256", name="refinement receipt")
    elif receipt_sha256 not in {"", None} and not _is_sha256(receipt_sha256):
        raise ValueError("compact refinement receipt hash is invalid")
    if candidate.get("proposal_mode") == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE:
        parent = candidate.get("torsion_rescue_parent_proposal_index")
        if (
            lane != "rescue"
            or type(parent) is not int
            or parent == proposal_index
            or set(payload) != _SOURCE_PAIRED_TORSION_RESCUE_REFINEMENT_RECEIPT_FIELDS
            or payload.get("schema_id") != SOURCE_PAIRED_RESCUE_RECEIPT_SCHEMA_ID
            or payload.get("source_paired_parent_proposal_index") != parent
            or any(
                type(payload.get(field)) is not bool
                for field in (
                    "torsion_evaluated",
                    "torsion_variant_available",
                    "torsion_selected",
                )
            )
            or payload.get("development_only") is not True
            or any(
                payload.get(field) is not False
                for field in (
                    "claim_safe",
                    "fresh_execution_authorized",
                    "scientifically_validated",
                    "stage0_eligible",
                )
            )
        ):
            raise ValueError(
                f"{lane} {case_id} source-paired rescue receipt is invalid"
            )
    _vector_summary(
        candidate.get("refinement_total_translation_binary64_hex"),
        name="refinement translation",
    )
    _vector_summary(
        candidate.get("refinement_total_rotation_vector_binary64_hex"),
        name="refinement rotation",
    )
    return dict(candidate)


def _case_candidates(
    result: Mapping[str, object],
    *,
    lane: str,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    case_id = str(result.get("case_id", ""))
    expected_diagnostic_schema = (
        PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID
        if lane == "baseline"
        else PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_DIAGNOSTIC_SCHEMA_ID
    )
    diagnostics = result.get("engine_v2_diagnostics")
    if (
        result.get("engine_id") != "engine_v2"
        or not isinstance(diagnostics, Mapping)
        or diagnostics.get("schema_id") != expected_diagnostic_schema
    ):
        raise ValueError(f"{lane} {case_id} diagnostics are invalid")
    preparation_status = diagnostics.get("preparation_status")
    raw_candidates = diagnostics.get("candidates", [])
    if preparation_status == "failure":
        if (
            case_id != EXPECTED_PREPARATION_FAILURE_CASE_ID
            or result.get("status") != "failure"
            or diagnostics.get("preparation_failure_code")
            != "unsupported_large_ring_system"
            or raw_candidates
        ):
            raise ValueError(f"{lane} preparation failure is invalid")
        _validate_ranked_result_projection(
            result,
            (),
            lane=lane,
            case_id=case_id,
        )
        return dict(diagnostics), ()
    if (
        preparation_status != "success"
        or result.get("status") != "success"
        or not isinstance(raw_candidates, list)
        or len(raw_candidates) != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
        or diagnostics.get("candidate_budget")
        != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
        or diagnostics.get("candidate_success_count")
        != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
        or diagnostics.get("candidate_failure_count") != 0
    ):
        raise ValueError(f"{lane} {case_id} candidate denominator is invalid")
    candidates = tuple(
        _validated_candidate(candidate, lane=lane, case_id=case_id)
        for candidate in raw_candidates
        if isinstance(candidate, Mapping)
    )
    if len(candidates) != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT or {
        int(candidate["proposal_index"]) for candidate in candidates
    } != set(range(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT)):
        raise ValueError(f"{lane} {case_id} candidate indices are invalid")
    _validate_ranked_result_projection(
        result,
        candidates,
        lane=lane,
        case_id=case_id,
    )
    return dict(diagnostics), candidates


def _ranked(
    candidates: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                float(candidate["score"]),
                int(candidate["proposal_index"]),
            ),
        )
    )


def _validate_ranked_result_projection(
    result: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
    *,
    lane: str,
    case_id: str,
) -> None:
    rmsds = result.get("rmsd_angstroms")
    geometric = result.get("geometric_valid")
    chemical = result.get("chemical_valid")
    pose_hashes = result.get("pose_artifact_sha256s")
    projections = (rmsds, geometric, chemical, pose_hashes)
    if any(not isinstance(value, list) for value in projections):
        raise ValueError(f"{lane} {case_id} ranked result projection is invalid")
    assert isinstance(rmsds, list)
    assert isinstance(geometric, list)
    assert isinstance(chemical, list)
    assert isinstance(pose_hashes, list)
    if result.get("status") == "failure":
        if any(projections):
            raise ValueError(
                f"{lane} {case_id} ranked result contradicts candidate diagnostics"
            )
        return
    if any(len(value) != 5 for value in projections):
        raise ValueError(f"{lane} {case_id} ranked result projection is invalid")
    for index, candidate in enumerate(_ranked(candidates)[:5]):
        rmsd = rmsds[index]
        if (
            isinstance(rmsd, bool)
            or not isinstance(rmsd, (int, float))
            or not math.isfinite(float(rmsd))
            or float(rmsd).hex() != float(candidate["rmsd_angstrom"]).hex()
            or type(geometric[index]) is not bool
            or geometric[index] is not candidate.get("geometric_valid")
            or type(chemical[index]) is not bool
            or chemical[index] is not candidate.get("chemical_valid")
            or not _is_sha256(pose_hashes[index])
            or pose_hashes[index] != candidate.get("pose_artifact_sha256")
        ):
            raise ValueError(
                f"{lane} {case_id} ranked result contradicts candidate diagnostics"
            )


def _posebusters_exact_valid(candidate: Mapping[str, object]) -> bool:
    return bool(
        candidate.get("geometric_valid") is True
        and candidate.get("chemical_valid") is True
    )


def _lane_counts(
    results: Mapping[str, Mapping[str, object]], *, lane: str
) -> dict[str, int]:
    counts = Counter(
        {
            "case_count": len(results),
            "scored_case_count": 0,
            "preparation_failure_count": 0,
            "candidate_success_count": 0,
            "exact_valid_candidate_count": 0,
            "native_like_candidate_count": 0,
            "native_like_posebusters_exact_valid_candidate_count": 0,
            "selection_eligible_candidate_count": 0,
            "native_like_selection_eligible_candidate_count": 0,
            "proposal_oracle_recovery_case_count": 0,
            "top1_recovery_case_count": 0,
            "top5_recovery_case_count": 0,
            "valid_top1_case_count": 0,
        }
    )
    for result in results.values():
        _, candidates = _case_candidates(result, lane=lane)
        if not candidates:
            counts["preparation_failure_count"] += 1
            continue
        counts["scored_case_count"] += 1
        counts["candidate_success_count"] += len(candidates)
        ranked = _ranked(candidates)
        native = [
            candidate
            for candidate in candidates
            if float(candidate["rmsd_angstrom"]) <= 2.0
        ]
        exact_valid = [
            candidate for candidate in candidates if _posebusters_exact_valid(candidate)
        ]
        eligible = [
            candidate
            for candidate in candidates
            if candidate["selection_eligible"] is True
        ]
        counts["native_like_candidate_count"] += len(native)
        counts["exact_valid_candidate_count"] += len(exact_valid)
        counts["selection_eligible_candidate_count"] += len(eligible)
        counts["native_like_posebusters_exact_valid_candidate_count"] += sum(
            float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in exact_valid
        )
        counts["native_like_selection_eligible_candidate_count"] += sum(
            float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in eligible
        )
        counts["proposal_oracle_recovery_case_count"] += bool(native)
        counts["top1_recovery_case_count"] += float(ranked[0]["rmsd_angstrom"]) <= 2.0
        counts["top5_recovery_case_count"] += any(
            float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in ranked[:5]
        )
        counts["valid_top1_case_count"] += _posebusters_exact_valid(ranked[0])
    return dict(counts)


def _validate_lane(
    results: Mapping[str, Mapping[str, object]],
    *,
    lane: str,
    report: Mapping[str, object],
) -> None:
    if tuple(sorted(results)) != tuple(sorted(EXPECTED_CASE_IDS)):
        raise ValueError(f"{lane} receipt case set is invalid")
    expected_metrics = report[lane]["metrics"]
    observed = _lane_counts(results, lane=lane)
    for field, value in observed.items():
        if expected_metrics.get(field) != value:
            raise ValueError(f"{lane} receipt metric contradicts A/B report: {field}")
    per_case = expected_metrics.get("per_case")
    if not isinstance(per_case, Mapping) or set(per_case) != set(EXPECTED_CASE_IDS):
        raise ValueError(f"{lane} per-case report metrics are invalid")
    for case_id in EXPECTED_CASE_IDS:
        diagnostics, candidates = _case_candidates(results[case_id], lane=lane)
        recorded = per_case[case_id]
        if not isinstance(recorded, Mapping):
            raise ValueError(f"{lane} {case_id} report row is invalid")
        if not candidates:
            if recorded.get("preparation_status") != "failure" or recorded.get(
                "preparation_failure_code"
            ) != diagnostics.get("preparation_failure_code"):
                raise ValueError(f"{lane} {case_id} preparation report is invalid")
            continue
        ranked = _ranked(candidates)
        exact_valid = [
            candidate for candidate in candidates if _posebusters_exact_valid(candidate)
        ]
        eligible = [
            candidate
            for candidate in candidates
            if candidate["selection_eligible"] is True
        ]
        oracle = any(
            float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in candidates
        )
        top1 = float(ranked[0]["rmsd_angstrom"]) <= 2.0
        top5 = any(float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in ranked[:5])
        if (
            recorded.get("candidate_success_count") != len(candidates)
            or recorded.get("exact_valid_candidate_count") != len(exact_valid)
            or recorded.get("selection_eligible_candidate_count") != len(eligible)
            or recorded.get("proposal_oracle_recovery") is not oracle
            or recorded.get("top1_recovery") is not top1
            or recorded.get("top5_recovery") is not top5
            or recorded.get("top1_proposal_index") != ranked[0]["proposal_index"]
            or recorded.get("top1_valid") is not _posebusters_exact_valid(ranked[0])
            or recorded.get("top1_rmsd_angstrom_binary64_hex")
            != float(ranked[0]["rmsd_angstrom"]).hex()
            or recorded.get("minimum_candidate_rmsd_angstrom_binary64_hex")
            != min(float(candidate["rmsd_angstrom"]) for candidate in candidates).hex()
        ):
            raise ValueError(f"{lane} {case_id} metrics contradict A/B report")


def _cross_lane_changes(
    baseline_results: Mapping[str, Mapping[str, object]],
    rescue_results: Mapping[str, Mapping[str, object]],
    *,
    report: Mapping[str, object],
) -> dict[str, object]:
    changed_by_case: dict[str, list[int]] = {}
    selection_changes: list[tuple[str, int, bool, bool]] = []
    rescue_candidate_count = 0
    rescue_parent_duplicate_count = 0
    torsion_selected_count = 0
    for case_id in EXPECTED_CASE_IDS:
        _, baseline_candidates = _case_candidates(
            baseline_results[case_id], lane="baseline"
        )
        rescue_diagnostics, rescue_candidates = _case_candidates(
            rescue_results[case_id], lane="rescue"
        )
        if not baseline_candidates or not rescue_candidates:
            continue
        _, allocation_pairs = _rescue_allocation(
            rescue_diagnostics,
            rescue_candidates,
        )
        parent_by_target = {
            row["target_proposal_index"]: row["parent_proposal_index"]
            for row in allocation_pairs
        }
        baseline_by_index = {
            int(candidate["proposal_index"]): candidate
            for candidate in baseline_candidates
        }
        rescue_by_index = {
            int(candidate["proposal_index"]): candidate
            for candidate in rescue_candidates
        }
        changed = [
            index
            for index in range(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT)
            if baseline_by_index[index]["coordinate_fingerprint_sha256"]
            != rescue_by_index[index]["coordinate_fingerprint_sha256"]
        ]
        if set(changed) != set(parent_by_target):
            raise ValueError("rescue coordinate changes contradict the allocation")
        if changed:
            changed_by_case[case_id] = changed
        for index in range(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT):
            before = bool(baseline_by_index[index]["selection_eligible"])
            after = bool(rescue_by_index[index]["selection_eligible"])
            if before is not after:
                selection_changes.append((case_id, index, before, after))
        for candidate in rescue_candidates:
            if (
                candidate["proposal_mode"]
                != PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            ):
                continue
            rescue_candidate_count += 1
            proposal_index = int(candidate["proposal_index"])
            parent = parent_by_target.get(proposal_index)
            if type(parent) is not int or parent not in rescue_by_index:
                raise ValueError("rescue candidate parent binding is invalid")
            if (
                candidate["coordinate_fingerprint_sha256"]
                == rescue_by_index[parent]["coordinate_fingerprint_sha256"]
            ):
                rescue_parent_duplicate_count += 1
            payload = candidate["refinement_receipt_payload"]
            assert isinstance(payload, Mapping)
            torsion_selected_count += payload.get("torsion_selected") is True
    expected_changes = report["candidate_level_changes"]
    if (
        sum(len(indices) for indices in changed_by_case.values()) != 28
        or sorted(changed_by_case)
        != list(expected_changes["baseline_to_rescue_coordinate_change_case_ids"])
        or rescue_candidate_count != 28
        or rescue_parent_duplicate_count != 28
        or torsion_selected_count != 0
        or selection_changes != [(EXPECTED_RECOVERED_CASE_ID, 13, True, False)]
    ):
        raise ValueError("candidate-level A/B changes contradict the report")
    return {
        "baseline_to_rescue_coordinate_change_count_by_case": {
            case_id: len(indices)
            for case_id, indices in sorted(changed_by_case.items())
        },
        "baseline_to_rescue_coordinate_change_indices_by_case": {
            case_id: indices for case_id, indices in sorted(changed_by_case.items())
        },
        "rescue_candidate_count": rescue_candidate_count,
        "rescue_parent_duplicate_count": rescue_parent_duplicate_count,
        "torsion_selected_count": torsion_selected_count,
    }


def _candidate_snapshot(candidate: Mapping[str, object]) -> dict[str, object]:
    return {
        "proposal_index": candidate["proposal_index"],
        "proposal_mode": candidate["proposal_mode"],
        "ensemble_source_proposal_index": candidate.get(
            "ensemble_source_proposal_index"
        ),
        "torsion_rescue_parent_proposal_index": candidate.get(
            "torsion_rescue_parent_proposal_index"
        ),
        "proposal_fingerprint_sha256": candidate["proposal_fingerprint_sha256"],
        "coordinate_fingerprint_sha256": candidate["coordinate_fingerprint_sha256"],
        "rmsd_angstrom_binary64_hex": float(candidate["rmsd_angstrom"]).hex(),
        "score_binary64_hex": float(candidate["score"]).hex(),
        "posebusters_exact_valid": _posebusters_exact_valid(candidate),
        "geometric_valid": candidate["geometric_valid"],
        "chemical_valid": candidate["chemical_valid"],
        "selection_eligible": candidate["selection_eligible"],
        "posebusters_failed_check_ids": list(candidate["posebusters_failed_check_ids"]),
        "refinement_receipt_sha256": candidate.get("refinement_receipt_sha256", ""),
    }


def _penalty_summary(payload: Mapping[str, object], *, scope: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for stage in ("initial", "baseline_v6", "optimized", "final"):
        field = f"{stage}_{scope}_penalty_binary64_hex"
        value = payload.get(field)
        result[f"{stage}_penalty_binary64_hex"] = (
            _binary64_hex(value, name=field) if value is not None else None
        )
    return result


def _rescue_allocation(
    diagnostics: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
) -> tuple[int, list[dict[str, int]]]:
    proposal = diagnostics.get("source_paired_torsion_rescue_proposal_receipt")
    if not isinstance(proposal, Mapping):
        raise ValueError("source-paired proposal receipt is missing")
    allocation = proposal.get("allocation")
    if not isinstance(allocation, Mapping):
        raise ValueError("source-paired allocation is missing")
    rotor_count = allocation.get("authority_rotor_count")
    raw_pairs = allocation.get("rescue_target_parent_pairs")
    if (
        type(rotor_count) is not int
        or rotor_count < 0
        or not isinstance(raw_pairs, list)
    ):
        raise ValueError("source-paired allocation values are invalid")
    pairs: list[dict[str, int]] = []
    for row in raw_pairs:
        if not isinstance(row, Mapping) or set(row) != {
            "target_proposal_index",
            "parent_proposal_index",
        }:
            raise ValueError("source-paired pair row is invalid")
        target = row["target_proposal_index"]
        parent = row["parent_proposal_index"]
        if (
            type(target) is not int
            or type(parent) is not int
            or not 0 <= target < PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
            or not 0 <= parent < PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
        ):
            raise ValueError("source-paired pair indices are invalid")
        pairs.append({"target_proposal_index": target, "parent_proposal_index": parent})
    candidate_by_index = {
        int(candidate["proposal_index"]): candidate for candidate in candidates
    }
    rescue_targets = {
        int(candidate["proposal_index"])
        for candidate in candidates
        if candidate["proposal_mode"] == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
    }
    pair_targets = [row["target_proposal_index"] for row in pairs]
    if rescue_targets != set(pair_targets) or len(pair_targets) != len(
        set(pair_targets)
    ):
        raise ValueError("rescue candidate modes contradict the allocation")
    for row in pairs:
        target = row["target_proposal_index"]
        parent = row["parent_proposal_index"]
        candidate = candidate_by_index[target]
        parent_candidate = candidate_by_index[parent]
        payload = candidate.get("refinement_receipt_payload")
        if (
            target == parent
            or parent in rescue_targets
            or candidate.get("torsion_rescue_parent_proposal_index") != parent
            or parent_candidate.get("proposal_mode")
            == PUBLIC_REDOCKING_TORSION_RESCUE_PROPOSAL_MODE
            or not isinstance(payload, Mapping)
            or payload.get("source_paired_parent_proposal_index") != parent
            or payload.get("source_paired_torsion_rescue_pairs") != pairs
        ):
            raise ValueError("rescue allocation parent binding is invalid")
    return rotor_count, pairs


def _case_atlas_row(
    *,
    case_id: str,
    baseline_result: Mapping[str, object],
    rescue_result: Mapping[str, object],
) -> dict[str, object]:
    _, baseline_candidates = _case_candidates(baseline_result, lane="baseline")
    rescue_diagnostics, rescue_candidates = _case_candidates(
        rescue_result, lane="rescue"
    )
    if not baseline_candidates or not rescue_candidates:
        raise ValueError("failure atlas case must be scored in both lanes")
    ranked = _ranked(rescue_candidates)
    top1 = ranked[0]
    if any(float(candidate["rmsd_angstrom"]) <= 2.0 for candidate in rescue_candidates):
        raise ValueError("failure atlas case unexpectedly has oracle recovery")
    valid_candidates = tuple(
        candidate
        for candidate in rescue_candidates
        if _posebusters_exact_valid(candidate)
    )
    failure_class = (
        "valid_nonnative_top1" if _posebusters_exact_valid(top1) else "invalid_top1"
    )
    if failure_class == "invalid_top1" and valid_candidates:
        raise ValueError("invalid-Top1 atlas case unexpectedly has a valid candidate")
    best_rmsd = min(
        rescue_candidates,
        key=lambda candidate: (
            float(candidate["rmsd_angstrom"]),
            int(candidate["proposal_index"]),
        ),
    )
    best_valid = (
        min(
            valid_candidates,
            key=lambda candidate: (
                float(candidate["rmsd_angstrom"]),
                int(candidate["proposal_index"]),
            ),
        )
        if valid_candidates
        else None
    )
    failed_check_counts = Counter(
        check_id
        for candidate in rescue_candidates
        for check_id in candidate["posebusters_failed_check_ids"]
    )
    top1_payload = top1["refinement_receipt_payload"]
    if not isinstance(top1_payload, Mapping):
        raise ValueError("top1 refinement payload is invalid")
    baseline_by_index = {
        int(candidate["proposal_index"]): candidate for candidate in baseline_candidates
    }
    rescue_by_index = {
        int(candidate["proposal_index"]): candidate for candidate in rescue_candidates
    }
    changed_indices = [
        index
        for index in range(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT)
        if baseline_by_index[index]["coordinate_fingerprint_sha256"]
        != rescue_by_index[index]["coordinate_fingerprint_sha256"]
    ]
    rotor_count, pairs = _rescue_allocation(rescue_diagnostics, rescue_candidates)
    rescue_rows = [rescue_by_index[row["target_proposal_index"]] for row in pairs]
    parent_duplicate_count = sum(
        rescue_by_index[row["target_proposal_index"]]["coordinate_fingerprint_sha256"]
        == rescue_by_index[row["parent_proposal_index"]][
            "coordinate_fingerprint_sha256"
        ]
        for row in pairs
    )
    torsion_payloads = [
        candidate["refinement_receipt_payload"] for candidate in rescue_rows
    ]
    skip_reasons = Counter(
        str(payload.get("torsion_evaluation_skip_reason", ""))
        for payload in torsion_payloads
    )
    selection_reasons = Counter(
        str(payload.get("selection_reason", "")) for payload in torsion_payloads
    )
    translation_norms: list[float] = []
    rotation_norms: list[float] = []
    for candidate in rescue_candidates:
        translation = _vector_summary(
            candidate.get("refinement_total_translation_binary64_hex"),
            name="candidate translation",
        )
        rotation = _vector_summary(
            candidate.get("refinement_total_rotation_vector_binary64_hex"),
            name="candidate rotation",
        )
        if translation["available"] is True:
            translation_norms.append(
                float.fromhex(str(translation["norm_binary64_hex"]))
            )
        if rotation["available"] is True:
            rotation_norms.append(float.fromhex(str(rotation["norm_binary64_hex"])))
    evaluated_paths = [
        value
        for payload in torsion_payloads
        if (
            value := _optional_binary64(
                payload, "evaluated_total_torsion_path_radians_binary64_hex"
            )
        )
        is not None
    ]
    selected_paths = [
        value
        for payload in torsion_payloads
        if (
            value := _optional_binary64(
                payload, "total_torsion_path_radians_binary64_hex"
            )
        )
        is not None
    ]
    available_payloads = [
        payload
        for payload in torsion_payloads
        if payload.get("torsion_variant_available") is True
    ]
    optimized_receptor_penalties: list[float] = []
    for payload in torsion_payloads:
        minimum = _optional_binary64(
            payload, "minimum_selected_final_receptor_penalty_binary64_hex"
        )
        maximum = _optional_binary64(
            payload, "maximum_selected_final_receptor_penalty_binary64_hex"
        )
        if (minimum, maximum) != (2.0, 4.0):
            raise ValueError("torsion selection-window authority is invalid")
    for payload in available_payloads:
        optimized = _optional_binary64(
            payload, "optimized_receptor_penalty_binary64_hex"
        )
        if optimized is None:
            raise ValueError("available torsion variant lacks receptor penalty")
        optimized_receptor_penalties.append(optimized)
    optimized_penalty_bands = {
        "below_2": sum(value < 2.0 for value in optimized_receptor_penalties),
        "from_2_inclusive_to_4_exclusive": sum(
            2.0 <= value < 4.0 for value in optimized_receptor_penalties
        ),
        "at_or_above_4": sum(value >= 4.0 for value in optimized_receptor_penalties),
    }
    blocker_ids = ["no_oracle_candidate"]
    if failure_class == "invalid_top1":
        blocker_ids.extend(("top1_invalid", "no_valid_candidate"))
    if rotor_count == 0:
        blocker_ids.append("no_authority_rotor")
    if rescue_rows and not any(
        payload.get("torsion_selected") is True for payload in torsion_payloads
    ):
        blocker_ids.append("no_torsion_variant_selected")
    if any(
        payload.get("selection_window_reachable_from_baseline_v6_receptor_penalty")
        is False
        for payload in torsion_payloads
    ):
        blocker_ids.append("torsion_selection_window_unreachable")
    proposal_mode_counts = Counter(
        str(candidate["proposal_mode"]) for candidate in rescue_candidates
    )
    top1_failed_checks = set(top1["posebusters_failed_check_ids"])
    cause_category_status = {
        "good_conformer_absence": "unresolved_no_independent_conformer_axis",
        "wrong_global_orientation": "unresolved_receipt_motion_scale_only",
        "pocket_boundary": "unresolved_no_numeric_boundary_metric",
        "receptor_minimum_distance": (
            "observed_top1_failure"
            if "minimum_distance_to_protein" in top1_failed_checks
            else "not_observed_at_top1"
        ),
        "volume_overlap": (
            "observed_top1_failure"
            if "volume_overlap_with_protein" in top1_failed_checks
            else "not_observed_at_top1"
        ),
        "ligand_internal_clash": (
            "observed_top1_failure"
            if "internal_steric_clash" in top1_failed_checks
            else "not_observed_at_top1"
        ),
        "internal_energy": (
            "observed_top1_failure"
            if "internal_energy" in top1_failed_checks
            else "not_observed_at_top1"
        ),
        "torsion_freedom": (
            "observed_no_authority_rotor"
            if rotor_count == 0
            else "unresolved_bounded_rescue_unsuccessful"
        ),
        "ring_conformer": "unresolved_profile_not_in_receipts",
        "unsupported_chemistry": "not_observed_preparation_succeeded",
    }
    return {
        "case_id": case_id,
        "failure_class": failure_class,
        "selection_stage": "proposal_oracle_absent",
        "validity_stage": (
            "top1_valid_but_nonnative"
            if failure_class == "valid_nonnative_top1"
            else "no_valid_candidate"
        ),
        "causal_diagnosis": "unresolved_requires_coordinate_replay",
        "observed_blocker_ids": blocker_ids,
        "candidate_counts": {
            "successful": len(rescue_candidates),
            "posebusters_exact_valid": len(valid_candidates),
            "selection_eligible": sum(
                candidate["selection_eligible"] is True
                for candidate in rescue_candidates
            ),
            "proposal_modes": dict(sorted(proposal_mode_counts.items())),
        },
        "top1": _candidate_snapshot(top1),
        "best_rmsd_candidate": _candidate_snapshot(best_rmsd),
        "best_posebusters_exact_valid_candidate": (
            _candidate_snapshot(best_valid) if best_valid is not None else None
        ),
        "placement_orientation": {
            "evidence_scope": (
                "receipt_derived_refinement_displacement_not_native_orientation_error"
            ),
            "top1_translation": _vector_summary(
                top1["refinement_total_translation_binary64_hex"],
                name="top1 translation",
            ),
            "top1_rigid_rotation": _vector_summary(
                top1["refinement_total_rotation_vector_binary64_hex"],
                name="top1 rotation",
            ),
            "top1_pre_coordinates_sha256": top1_payload.get("pre_coordinates_sha256"),
            "top1_post_coordinates_sha256": top1_payload.get("post_coordinates_sha256"),
            "baseline_to_rescue_coordinate_change_count": len(changed_indices),
            "baseline_to_rescue_coordinate_change_proposal_indices": changed_indices,
            "rescue_to_parent_coordinate_change_count": len(pairs)
            - parent_duplicate_count,
            "source_proposal_to_final_translation_norm_angstrom": _distribution(
                translation_norms
            ),
            "accepted_axis_angle_vector_norm_radians": _distribution(rotation_norms),
        },
        "clearance": {
            "numeric_minimum_clearance_available": False,
            "top1_failed_check_ids": [
                check_id
                for check_id in top1["posebusters_failed_check_ids"]
                if check_id in PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS
            ],
            "candidate_failed_check_counts": {
                check_id: failed_check_counts[check_id]
                for check_id in PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS
                if failed_check_counts[check_id]
            },
            "top1_receptor_overlap_penalty": _penalty_summary(
                top1_payload, scope="receptor"
            ),
        },
        "internal_geometry_energy": {
            "top1_failed_check_ids": [
                check_id
                for check_id in top1["posebusters_failed_check_ids"]
                if check_id in _INTERNAL_CHECK_IDS
            ],
            "candidate_failed_check_counts": {
                check_id: failed_check_counts[check_id]
                for check_id in sorted(_INTERNAL_CHECK_IDS)
                if failed_check_counts[check_id]
            },
            "top1_internal_overlap_penalty": _penalty_summary(
                top1_payload, scope="internal"
            ),
        },
        "torsion": {
            "authority_rotor_count": rotor_count,
            "rescue_target_parent_pairs": pairs,
            "rescue_candidate_count": len(rescue_rows),
            "parent_coordinate_duplicate_count": parent_duplicate_count,
            "evaluated_candidate_count": sum(
                payload.get("torsion_evaluated") is True for payload in torsion_payloads
            ),
            "variant_available_candidate_count": sum(
                payload.get("torsion_variant_available") is True
                for payload in torsion_payloads
            ),
            "selected_candidate_count": sum(
                payload.get("torsion_selected") is True for payload in torsion_payloads
            ),
            "evaluated_step_count": sum(
                int(payload.get("evaluated_torsion_steps", 0))
                for payload in torsion_payloads
            ),
            "accepted_step_count": sum(
                int(payload.get("accepted_torsion_steps", 0))
                for payload in torsion_payloads
            ),
            "selection_window_unreachable_candidate_count": sum(
                payload.get(
                    "selection_window_reachable_from_baseline_v6_receptor_penalty"
                )
                is False
                for payload in torsion_payloads
            ),
            "skip_reason_counts": dict(sorted(skip_reasons.items())),
            "selection_reason_counts": dict(sorted(selection_reasons.items())),
            "evaluated_path_radians": _distribution(evaluated_paths),
            "selected_path_radians": _distribution(selected_paths),
            "selection_window": {
                "minimum_inclusive_binary64_hex": (2.0).hex(),
                "maximum_exclusive_binary64_hex": (4.0).hex(),
                "available_variant_optimized_receptor_penalty": _distribution(
                    optimized_receptor_penalties
                ),
                "available_variant_optimized_receptor_penalty_bands": (
                    optimized_penalty_bands
                ),
            },
        },
        "cause_category_status": cause_category_status,
    }


def _build_failure_atlas_payload(
    *,
    ab_report: Mapping[str, object],
    baseline_results: Mapping[str, Mapping[str, object]],
    rescue_results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Build an unsealed seven-case draft from authenticated input objects."""
    _validate_ab_report(ab_report)
    _validate_lane(baseline_results, lane="baseline", report=ab_report)
    _validate_lane(rescue_results, lane="rescue", report=ab_report)
    cross_lane = _cross_lane_changes(
        baseline_results,
        rescue_results,
        report=ab_report,
    )
    rows = [
        _case_atlas_row(
            case_id=case_id,
            baseline_result=baseline_results[case_id],
            rescue_result=rescue_results[case_id],
        )
        for case_id in EXPECTED_UNCOVERED_CASE_IDS
    ]
    observed_uncovered = tuple(row["case_id"] for row in rows)
    class_counts = Counter(str(row["failure_class"]) for row in rows)
    if observed_uncovered != EXPECTED_UNCOVERED_CASE_IDS or class_counts != Counter(
        {"invalid_top1": 5, "valid_nonnative_top1": 2}
    ):
        raise ValueError("failure-atlas seven-case split is invalid")
    blocker_counts = Counter(
        blocker for row in rows for blocker in row["observed_blocker_ids"]
    )
    uncovered_torsion_counts = Counter()
    uncovered_selection_reasons: Counter[str] = Counter()
    uncovered_penalty_bands: Counter[str] = Counter()
    for row in rows:
        torsion = row["torsion"]
        uncovered_torsion_counts.update(
            {
                "rescue_candidate_count": int(torsion["rescue_candidate_count"]),
                "evaluated_candidate_count": int(torsion["evaluated_candidate_count"]),
                "variant_available_candidate_count": int(
                    torsion["variant_available_candidate_count"]
                ),
                "selected_candidate_count": int(torsion["selected_candidate_count"]),
            }
        )
        uncovered_selection_reasons.update(torsion["selection_reason_counts"])
        uncovered_penalty_bands.update(
            torsion["selection_window"][
                "available_variant_optimized_receptor_penalty_bands"
            ]
        )
    if uncovered_torsion_counts != Counter(
        {
            "rescue_candidate_count": 24,
            "evaluated_candidate_count": 23,
            "variant_available_candidate_count": 22,
            "selected_candidate_count": 0,
        }
    ) or uncovered_penalty_bands != Counter(
        {
            "below_2": 0,
            "from_2_inclusive_to_4_exclusive": 0,
            "at_or_above_4": 22,
        }
    ):
        raise ValueError("uncovered torsion-scale partition drifted")
    return {
        "analysis_scope": "historical_contaminated_development_only",
        "evidence_role": "source_paired_failure_atlas_companion",
        "development_only": True,
        "contains_engineering_smoke": False,
        "contains_fresh_internal_blind_holdout": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
        "stage0_eligible": False,
        "primary_claim_eligible": False,
        "public_claim_eligible": False,
        "product_promotion_eligible": False,
        "source_commit_sha256": EXPECTED_SOURCE_COMMIT_SHA256,
        "source_archive_sha256": PUBLIC_REDOCKING_ARCHIVE_SHA256,
        "source_identifiers_sha256": PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
        "ab_report_sha256": ab_report["report_sha256"],
        "engine_identity": dict(ab_report["engine_identity"]),
        "case_count": len(rows),
        "case_ids": list(observed_uncovered),
        "case_ids_sha256": _sha256_payload(list(observed_uncovered)),
        "failure_class_counts": dict(sorted(class_counts.items())),
        "observed_blocker_counts": dict(sorted(blocker_counts.items())),
        "cross_lane_summary": cross_lane,
        "uncovered_torsion_scale_summary": {
            **dict(sorted(uncovered_torsion_counts.items())),
            "selection_reason_counts": dict(
                sorted(uncovered_selection_reasons.items())
            ),
            "available_variant_optimized_receptor_penalty_bands": dict(
                sorted(uncovered_penalty_bands.items())
            ),
            "absolute_window_scale_mismatch": "unconfirmed_hypothesis",
            "automatic_policy_change_allowed": False,
        },
        "measurement_limitations": [
            "receipt displacement is not native-referenced orientation error",
            "PoseBusters check IDs do not provide numeric minimum clearance",
            "causal diagnosis remains unresolved without coordinate replay",
        ],
        "cases": rows,
    }


def _archive_object(
    members: Mapping[str, bytes],
    path: object,
    *,
    name: str,
    require_canonical_bytes: bool,
) -> tuple[dict[str, object], bytes, str]:
    member = _safe_member_name(str(path))
    raw = members.get(member)
    if raw is None:
        raise ValueError(f"{name} archive member is missing")
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must contain a JSON object")
    if require_canonical_bytes and raw != _canonical_bytes(parsed) + b"\n":
        raise ValueError(f"{name} is not canonical JSON")
    return parsed, raw, member


def _load_receipt_set(
    members: Mapping[str, bytes],
    *,
    run_root: object,
    lane: str,
    engine_identity: Mapping[str, object],
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, str],
    dict[str, dict[str, object]],
]:
    root = _safe_member_name(str(run_root))
    prefix = f"{root}/receipts/engine_v2/"
    expected_members = {f"{prefix}{case_id}.json" for case_id in EXPECTED_CASE_IDS}
    observed_members = {
        member
        for member in members
        if member.startswith(prefix) and member.endswith(".json")
    }
    if observed_members != expected_members:
        raise ValueError(f"{lane} execution receipt member set is invalid")
    results: dict[str, dict[str, object]] = {}
    hashes: dict[str, str] = {}
    payloads: dict[str, dict[str, object]] = {}
    for case_id in EXPECTED_CASE_IDS:
        member = f"{prefix}{case_id}.json"
        payload, raw, _ = _archive_object(
            members,
            member,
            name=f"{lane} execution receipt {case_id}",
            require_canonical_bytes=True,
        )
        if set(payload) != _EXECUTION_FIELDS:
            raise ValueError(f"{lane} execution receipt fields are invalid")
        _self_hash(payload, field="receipt_sha256", name=f"{lane} execution receipt")
        result = payload.get("result")
        if (
            payload.get("schema_id") != PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID
            or payload.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID
            or payload.get("archive_sha256") != PUBLIC_REDOCKING_ARCHIVE_SHA256
            or payload.get("source_ids_sha256") != PUBLIC_REDOCKING_SOURCE_IDS_SHA256
            or payload.get("cache_read_allowed") is not False
            or payload.get("fresh_execution") is not True
            or not isinstance(result, Mapping)
            or payload.get("implementation_sha256")
            != engine_identity.get("implementation_sha256")
            or payload.get("evaluation_pipeline_sha256")
            != engine_identity.get("evaluation_pipeline_sha256")
            or payload.get("execution_environment_sha256")
            != engine_identity.get("execution_environment_sha256")
        ):
            raise ValueError(f"{lane} execution receipt identity is invalid")
        if result.get("case_id") != case_id:
            raise ValueError(f"{lane} execution receipt case identity is invalid")
        try:
            typed_result = _typed_development_result(result)
        except ValueError as exc:
            raise ValueError(
                f"{lane} execution receipt strict result binding is invalid"
            ) from exc
        typed_payload = typed_result.to_dict()
        try:
            policy_tokens = _execution_policy_tokens(payload.get("execution_policy"))
        except ValueError as exc:
            raise ValueError(f"{lane} execution receipt policy is invalid") from exc
        if (
            typed_result.case_id != case_id
            or typed_result.engine_id != "engine_v2"
            or typed_payload != dict(result)
            or payload.get("command") != typed_payload.get("execution_command")
            or policy_tokens != typed_payload.get("execution_policy")
        ):
            raise ValueError(f"{lane} execution receipt typed result is cross-wired")
        results[case_id] = typed_payload
        hashes[case_id] = _sha256_bytes(raw)
        payloads[case_id] = payload
    return results, hashes, payloads


def _load_bound_analysis(
    members: Mapping[str, bytes],
    *,
    lane: str,
    ab_report: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    lane_row = ab_report[lane]
    if not isinstance(lane_row, Mapping):
        raise ValueError(f"A/B report {lane} lane is invalid")
    payload, raw, _ = _archive_object(
        members,
        lane_row.get("analysis_path"),
        name=f"{lane} analysis",
        require_canonical_bytes=True,
    )
    self_hash = _self_hash(payload, field="report_sha256", name=f"{lane} analysis")
    file_hash = _sha256_bytes(raw)
    if (
        payload.get("schema_id") != ANALYSIS_SCHEMA_ID
        or payload.get("analysis_scope") != "historical_contaminated_development_only"
        or payload.get("contains_fresh_internal_blind_holdout") is not False
        or tuple(payload.get("case_ids", ())) != EXPECTED_CASE_IDS
        or self_hash != lane_row.get("analysis_self_sha256")
        or file_hash != lane_row.get("analysis_file_sha256")
    ):
        raise ValueError(f"{lane} analysis binding is invalid")
    return payload, file_hash


def _materialization_inputs(
    materialization: Mapping[str, object],
    *,
    case_id: str,
) -> dict[str, str]:
    artifact_filenames = (
        "protein.pdb",
        "ligands.sdf",
        "ligand.sdf",
        "ligand_start_conf.sdf",
    )
    expected_members = {
        filename: f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}"
        for filename in artifact_filenames
    }
    artifacts = materialization.get("artifact_sha256s")
    if (
        set(materialization) != _MATERIALIZATION_FIELDS
        or materialization.get("frozen_case_seed")
        != frozen_public_redocking_case_seed(case_id)
        or materialization.get("archive_members") != expected_members
        or not isinstance(artifacts, Mapping)
        or set(artifacts) != set(artifact_filenames)
        or any(not _is_sha256(artifacts.get(name)) for name in artifact_filenames)
    ):
        raise ValueError("materialization input identity is invalid")
    return {
        "receptor": str(artifacts["protein.pdb"]),
        "reference": str(artifacts["ligands.sdf"]),
        "native": str(artifacts["ligand.sdf"]),
        "seed": str(artifacts["ligand_start_conf.sdf"]),
    }


def _validate_lane_summary(
    members: Mapping[str, bytes],
    *,
    lane: str,
    ab_report: Mapping[str, object],
    receipt_payloads: Mapping[str, Mapping[str, object]],
) -> tuple[str, str]:
    lane_row = ab_report[lane]
    if not isinstance(lane_row, Mapping):
        raise ValueError(f"A/B report {lane} lane is invalid")
    summary, raw, _ = _archive_object(
        members,
        lane_row.get("summary_path"),
        name=f"{lane} summary",
        require_canonical_bytes=True,
    )
    summary_self_sha256 = _self_hash(
        summary,
        field="summary_sha256",
        name=f"{lane} summary",
    )
    summary_file_sha256 = _sha256_bytes(raw)
    false_fields = (
        "benchmark_validated",
        "claim_safe",
        "contains_engineering_smoke",
        "contains_fresh_internal_blind_holdout",
        "fresh_execution_authorized",
        "primary_claim_eligible",
        "product_promotion_eligible",
        "product_qualified",
        "public_claim_eligible",
        "scientifically_validated",
    )
    engine_identity = summary.get("engine_identity")
    report_identity = ab_report.get("engine_identity")
    expected_schema_id = (
        SUMMARY_SCHEMA_ID if lane == "baseline" else RESCUE_SUMMARY_SCHEMA_ID
    )
    if (
        summary.get("schema_id") != expected_schema_id
        or summary.get("analysis_scope") != "historical_contaminated_development_only"
        or summary.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID
        or summary.get("case_count") != len(EXPECTED_CASE_IDS)
        or tuple(summary.get("case_ids", ())) != EXPECTED_CASE_IDS
        or summary.get("case_ids_sha256") != EXPECTED_CASE_IDS_SHA256
        or any(summary.get(field) is not False for field in false_fields)
        or summary_self_sha256 != lane_row.get("summary_self_sha256")
        or summary_file_sha256 != lane_row.get("summary_file_sha256")
        or not isinstance(engine_identity, Mapping)
        or not isinstance(report_identity, Mapping)
    ):
        raise ValueError(f"{lane} summary identity or boundary is invalid")
    for key in (
        "implementation_sha256",
        "evaluation_pipeline_sha256",
        "execution_environment_sha256",
        "interaction_refiner_config_sha256",
    ):
        if engine_identity.get(key) != report_identity.get(key):
            raise ValueError(f"{lane} summary engine identity is cross-wired")
    rows = summary.get("rows")
    embedded_receipts = summary.get("execution_receipts")
    materializations = summary.get("materializations")
    profiles = summary.get("profiles")
    if not all(
        isinstance(value, list)
        for value in (rows, embedded_receipts, materializations, profiles)
    ):
        raise ValueError(f"{lane} summary collections are invalid")
    assert isinstance(rows, list)
    assert isinstance(embedded_receipts, list)
    assert isinstance(materializations, list)
    assert isinstance(profiles, list)
    if any(
        len(value) != len(EXPECTED_CASE_IDS)
        for value in (rows, embedded_receipts, materializations, profiles)
    ):
        raise ValueError(f"{lane} summary collection lengths are invalid")
    run_root = _safe_member_name(str(lane_row.get("run_root", "")))
    for index, case_id in enumerate(EXPECTED_CASE_IDS):
        receipt = receipt_payloads.get(case_id)
        materialization = materializations[index]
        profile = profiles[index]
        if (
            receipt is None
            or embedded_receipts[index] != receipt
            or rows[index] != receipt.get("result")
            or not isinstance(materialization, Mapping)
            or not isinstance(profile, Mapping)
            or materialization.get("case_id") != case_id
            or profile.get("case_id") != case_id
        ):
            raise ValueError(f"{lane} summary row or receipt is cross-wired")
        standalone, standalone_raw, _ = _archive_object(
            members,
            f"{run_root}/receipts/materializations/{case_id}.json",
            name=f"{lane} materialization {case_id}",
            require_canonical_bytes=True,
        )
        _self_hash(
            standalone,
            field="receipt_sha256",
            name=f"{lane} materialization {case_id}",
        )
        expected_inputs = _materialization_inputs(standalone, case_id=case_id)
        result = receipt.get("result")
        if (
            standalone != materialization
            or standalone_raw != _canonical_bytes(materialization) + b"\n"
            or standalone.get("schema_id") != PUBLIC_REDOCKING_MATERIALIZATION_SCHEMA_ID
            or standalone.get("source_archive_sha256")
            != PUBLIC_REDOCKING_ARCHIVE_SHA256
            or standalone.get("hash_verified_archive") is not True
            or receipt.get("materialization_receipt_sha256")
            != standalone.get("receipt_sha256")
            or receipt.get("input_sha256s") != expected_inputs
            or not isinstance(result, Mapping)
            or {
                "receptor": result.get("receptor_artifact_sha256"),
                "reference": result.get("reference_artifact_sha256"),
                "native": result.get("native_artifact_sha256"),
                "seed": result.get("seed_artifact_sha256"),
            }
            != expected_inputs
        ):
            raise ValueError(f"{lane} materialization is cross-wired")
    return summary_file_sha256, summary_self_sha256


def _validate_analysis_receipts(
    analysis: Mapping[str, object],
    actual_hashes: Mapping[str, str],
    *,
    lane: str,
) -> str:
    source = analysis.get("source_receipts_sha256")
    if not isinstance(source, Mapping):
        raise ValueError(f"{lane} analysis source receipts are missing")
    expected: dict[str, str] = {}
    for receipt_path, digest in source.items():
        case_id = Path(str(receipt_path)).stem
        if case_id in expected or not _is_sha256(digest):
            raise ValueError(f"{lane} analysis source receipt binding is invalid")
        expected[case_id] = str(digest)
    if expected != dict(actual_hashes):
        raise ValueError(f"{lane} restored receipts contradict the analysis")
    return _sha256_payload(expected)


def build_authenticated_failure_atlas(
    *,
    repo_root: Path,
    archive_path: Path,
    members_path: Path,
    bundle_path: Path,
    report_member: str,
    expected_archive_sha256: str,
    expected_members_sha256: str,
    expected_bundle_sha256: str,
    expected_report_sha256: str,
) -> dict[str, object]:
    members, archive_identity = _verified_archive_members(
        repo_root=repo_root,
        archive_path=archive_path,
        members_path=members_path,
        bundle_path=bundle_path,
        expected_archive_sha256=expected_archive_sha256,
        expected_members_sha256=expected_members_sha256,
        expected_bundle_sha256=expected_bundle_sha256,
    )
    ab_report, ab_raw, safe_report_member = _archive_object(
        members,
        report_member,
        name="A/B report",
        require_canonical_bytes=False,
    )
    _validate_ab_report(ab_report)
    if (
        not _is_sha256(expected_report_sha256)
        or ab_report.get("report_sha256") != expected_report_sha256
    ):
        raise ValueError("A/B report does not match the expected self-hash")
    engine_identity = ab_report.get("engine_identity")
    if not isinstance(engine_identity, Mapping):
        raise ValueError("A/B report engine identity is invalid")
    baseline_analysis, baseline_analysis_file_sha256 = _load_bound_analysis(
        members, lane="baseline", ab_report=ab_report
    )
    rescue_analysis, rescue_analysis_file_sha256 = _load_bound_analysis(
        members, lane="rescue", ab_report=ab_report
    )
    baseline_row = ab_report.get("baseline")
    rescue_row = ab_report.get("rescue")
    if not isinstance(baseline_row, Mapping) or not isinstance(rescue_row, Mapping):
        raise ValueError("A/B report lanes are invalid")
    baseline_results, baseline_hashes, baseline_receipts = _load_receipt_set(
        members,
        run_root=baseline_row.get("run_root"),
        lane="baseline",
        engine_identity=engine_identity,
    )
    rescue_results, rescue_hashes, rescue_receipts = _load_receipt_set(
        members,
        run_root=rescue_row.get("run_root"),
        lane="rescue",
        engine_identity=engine_identity,
    )
    baseline_summary_file_sha256, baseline_summary_self_sha256 = _validate_lane_summary(
        members,
        lane="baseline",
        ab_report=ab_report,
        receipt_payloads=baseline_receipts,
    )
    rescue_summary_file_sha256, rescue_summary_self_sha256 = _validate_lane_summary(
        members,
        lane="rescue",
        ab_report=ab_report,
        receipt_payloads=rescue_receipts,
    )
    evidence_binding: dict[str, object] = {
        **archive_identity,
        "ab_report_member": safe_report_member,
        "ab_report_file_sha256": _sha256_bytes(ab_raw),
        "ab_report_self_sha256": ab_report["report_sha256"],
        "baseline_analysis_file_sha256": baseline_analysis_file_sha256,
        "baseline_analysis_self_sha256": baseline_analysis["report_sha256"],
        "baseline_summary_file_sha256": baseline_summary_file_sha256,
        "baseline_summary_self_sha256": baseline_summary_self_sha256,
        "rescue_analysis_file_sha256": rescue_analysis_file_sha256,
        "rescue_analysis_self_sha256": rescue_analysis["report_sha256"],
        "rescue_summary_file_sha256": rescue_summary_file_sha256,
        "rescue_summary_self_sha256": rescue_summary_self_sha256,
        "baseline_source_receipts_sha256": _validate_analysis_receipts(
            baseline_analysis, baseline_hashes, lane="baseline"
        ),
        "rescue_source_receipts_sha256": _validate_analysis_receipts(
            rescue_analysis, rescue_hashes, lane="rescue"
        ),
    }
    draft = _build_failure_atlas_payload(
        ab_report=ab_report,
        baseline_results=baseline_results,
        rescue_results=rescue_results,
    )
    report: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        **draft,
        "authentication": {
            "status": "verified_archive_member_bundle",
            "authoritative_builder_path": "authenticated_only",
            "both_raw_receipt_lanes_verified": True,
            "both_summary_receipt_sets_cross_checked": True,
        },
        "input_evidence": dict(sorted(evidence_binding.items())),
    }
    report["report_sha256"] = _sha256_payload(report)
    return report


def _output_relative_path(repo_root: Path, path: Path) -> Path:
    _prohibited_path(path, name="output")
    _reject_symlink_ancestry(repo_root, name="repository root")
    root = repo_root.resolve(strict=True)
    try:
        relative = path.relative_to(root) if path.is_absolute() else path
    except ValueError as exc:
        raise ValueError("output must remain inside the repository") from exc
    if (
        not relative.parts
        or relative.parts[0] != ".betelgeuze"
        or any(component in {"", ".", ".."} for component in relative.parts)
        or relative.name == ".betelgeuze"
    ):
        raise ValueError("mutable atlas output must be stored under .betelgeuze")
    return relative


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _owned_output_directory_descriptor(
    repo_root: Path,
    relative_directory: Path,
) -> int:
    _reject_symlink_ancestry(repo_root, name="repository root")
    descriptor = os.open(repo_root.resolve(strict=True), _directory_flags())
    try:
        root_status = os.fstat(descriptor)
        if not stat.S_ISDIR(root_status.st_mode) or (
            hasattr(os, "geteuid") and root_status.st_uid != os.geteuid()
        ):
            raise ValueError("repository root must be an owned directory")
        for component in relative_directory.parts:
            try:
                next_descriptor = os.open(
                    component,
                    _directory_flags(),
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                next_descriptor = os.open(
                    component,
                    _directory_flags(),
                    dir_fd=descriptor,
                )
            status = os.fstat(next_descriptor)
            if not stat.S_ISDIR(status.st_mode) or (
                hasattr(os, "geteuid") and status.st_uid != os.geteuid()
            ):
                os.close(next_descriptor)
                raise ValueError("atlas output parent must be an owned directory")
            os.fchmod(next_descriptor, 0o700)
            if stat.S_IMODE(os.fstat(next_descriptor).st_mode) != 0o700:
                os.close(next_descriptor)
                raise ValueError("atlas output parent permissions are invalid")
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _write_exclusive(repo_root: Path, relative_path: Path, payload: bytes) -> None:
    parent_descriptor = _owned_output_directory_descriptor(
        repo_root, relative_path.parent
    )
    descriptor = -1
    temporary_name = f".{relative_path.name}.{secrets.token_hex(16)}.tmp"
    temporary_created = False
    try:
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        temporary_created = True
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(
            temporary_name,
            relative_path.name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        os.fsync(parent_descriptor)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        raise
    finally:
        if temporary_created:
            try:
                os.unlink(temporary_name, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
            except FileNotFoundError:
                pass
        os.close(parent_descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--members-sha256", type=Path, required=True)
    parser.add_argument("--bundle-sha256", type=Path, required=True)
    parser.add_argument("--report-member", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--expected-members-sha256", required=True)
    parser.add_argument("--expected-bundle-sha256", required=True)
    parser.add_argument("--expected-report-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    _prohibited_path(arguments.repo_root, name="repository root")
    repo_root = arguments.repo_root.resolve()
    report = build_authenticated_failure_atlas(
        repo_root=repo_root,
        archive_path=arguments.archive,
        members_path=arguments.members_sha256,
        bundle_path=arguments.bundle_sha256,
        report_member=arguments.report_member,
        expected_archive_sha256=arguments.expected_archive_sha256,
        expected_members_sha256=arguments.expected_members_sha256,
        expected_bundle_sha256=arguments.expected_bundle_sha256,
        expected_report_sha256=arguments.expected_report_sha256,
    )
    output = _output_relative_path(repo_root, arguments.output)
    _write_exclusive(
        repo_root,
        output,
        _canonical_bytes(report) + b"\n",
    )
    print(
        json.dumps(
            {
                "case_count": report["case_count"],
                "output": str(arguments.output),
                "report_sha256": report["report_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
