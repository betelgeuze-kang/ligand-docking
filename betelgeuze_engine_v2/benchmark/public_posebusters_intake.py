"""Bounded, extraction-free intake for the published PoseBusters 308 set.

The official workflow verifies the exact Zenodo archive and peer-review 308-ID
selection bytes, audits the ZIP central directory, and streams the four required
members for each selected case into a failure-inclusive identity receipt.  It
never extracts archive members, fetches data, accepts license terms, launches a
docking engine, or promotes a benchmark claim.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any, Sequence
import zipfile

from .public_split_provenance import (
    POSEBUSTERS_2023_308_CASE_ID_PROJECTION_SHA256,
    POSEBUSTERS_2023_308_DATASET_ID,
    POSEBUSTERS_2023_308_SELECTION_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SHA256,
    POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES,
)


POSEBUSTERS_ARCHIVE_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_archive_contract/1.0.0"
)
POSEBUSTERS_ARCHIVE_ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_archive_artifact/1.0.0"
)
POSEBUSTERS_ARCHIVE_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_archive_case/1.0.0"
)
POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_archive_intake/1.0.0"
)
POSEBUSTERS_ARCHIVE_MEMBER_ROLES = (
    "receptor_pdb",
    "reference_ligand_sdf",
    "reference_ligands_sdf",
    "ligand_start_conformer_sdf",
)
POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES = {
    "receptor_pdb": "_protein.pdb",
    "reference_ligand_sdf": "_ligand.sdf",
    "reference_ligands_sdf": "_ligands.sdf",
    "ligand_start_conformer_sdf": "_ligand_start_conf.sdf",
}
POSEBUSTERS_ARCHIVE_README_SHA256 = (
    "9ccdb00aa1f6238500f98d0a582e98ebca43d2e65d8a08d3b364eae61c76909b"
)
POSEBUSTERS_ARCHIVE_428_ID_SHA256 = (
    "83fc63e6fe7acc7245b31eb69438b0739abdf510a05adc7110dac7afa8b46412"
)
POSEBUSTERS_ARCHIVE_SELECTION_SIZE_BYTES = 2_772
POSEBUSTERS_ARCHIVE_ENTRY_COUNT = 2_570
POSEBUSTERS_ARCHIVE_UNCOMPRESSED_SIZE_BYTES = 214_916_765
POSEBUSTERS_ARCHIVE_BENCHMARK_CASE_COUNT = 428
POSEBUSTERS_ARCHIVE_SELECTED_CASE_COUNT = 308
POSEBUSTERS_ARCHIVE_MAX_BYTES = 64 * 1024 * 1024
POSEBUSTERS_ARCHIVE_MAX_SELECTION_BYTES = 4 * 1024
POSEBUSTERS_ARCHIVE_MAX_ENTRIES = 3_000
POSEBUSTERS_ARCHIVE_MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES = 8 * 1024 * 1024
POSEBUSTERS_ARCHIVE_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES = 1024 * 1024
POSEBUSTERS_ARCHIVE_SCIENTIFIC_BLOCKERS = (
    "target_family_assignments_missing",
    "protein_chain_sequence_identity_receipt_missing",
    "release_date_receipts_missing",
    "cofactor_and_supported_chemistry_dispositions_missing",
    "prepared_pdbqt_inputs_missing",
    "pose_generation_and_validity_results_missing",
    "same_input_external_baseline_results_missing",
    "confidence_intervals_missing",
    "independent_external_rerun_missing",
    "scientific_review_missing",
)

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_ALLOWED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})


class PoseBustersArchiveIntakeError(ValueError):
    """PoseBusters archive, selection, or receipt verification failed closed."""


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
        raise PoseBustersArchiveIntakeError(
            "PoseBusters intake value is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PoseBustersArchiveIntakeError(f"{name} must be non-empty text")
    return value.strip()


def _sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersArchiveIntakeError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _positive_int(value: object, *, name: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PoseBustersArchiveIntakeError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise PoseBustersArchiveIntakeError(f"{name} exceeds the frozen maximum")
    return value


def _case_id(value: object) -> str:
    case_id = _text(value, name="PoseBusters case ID")
    parts = case_id.split("_")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or len(parts[1]) != 3
        or not all(part.isascii() and part.isalnum() and part.upper() == part for part in parts)
    ):
        raise PoseBustersArchiveIntakeError(
            "PoseBusters case ID must use uppercase PDB4_CCD3 form"
        )
    return case_id


def _regular_file_descriptor(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
) -> tuple[int, int]:
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise PoseBustersArchiveIntakeError(
            "secure PoseBusters file access is unavailable"
        )
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(os.fspath(path), flags)
    except OSError as exc:
        raise PoseBustersArchiveIntakeError(
            "PoseBusters input cannot be opened securely"
        ) from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size <= 0
            or metadata.st_size > maximum_bytes
        ):
            raise PoseBustersArchiveIntakeError(
                "PoseBusters input violates the bounded regular-file policy"
            )
        return descriptor, int(metadata.st_size)
    except Exception:
        os.close(descriptor)
        raise


def _read_exact_regular_file(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
) -> bytes:
    descriptor, size = _regular_file_descriptor(path, maximum_bytes=maximum_bytes)
    try:
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            chunk = os.read(descriptor, min(remaining, POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES))
            if not chunk:
                raise PoseBustersArchiveIntakeError(
                    "PoseBusters input ended before its observed size"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise PoseBustersArchiveIntakeError(
                "PoseBusters input grew while being read"
            )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _hash_descriptor(descriptor: int, size: int) -> str:
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        chunk = os.read(
            descriptor,
            min(remaining, POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES),
        )
        if not chunk:
            raise PoseBustersArchiveIntakeError(
                "PoseBusters archive ended before its observed size"
            )
        digest.update(chunk)
        remaining -= len(chunk)
    if os.read(descriptor, 1):
        raise PoseBustersArchiveIntakeError(
            "PoseBusters archive grew while being read"
        )
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class PoseBustersArchiveContract:
    dataset_id: str
    archive_sha256: str
    archive_size_bytes: int
    selection_sha256: str
    selection_size_bytes: int
    case_id_projection_sha256: str
    selected_case_count: int
    archive_entry_count: int
    archive_uncompressed_size_bytes: int
    archive_benchmark_case_count: int
    benchmark_root: str
    embedded_case_list_member: str
    embedded_case_list_sha256: str
    readme_member: str
    readme_sha256: str
    schema_id: str = POSEBUSTERS_ARCHIVE_CONTRACT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_ARCHIVE_CONTRACT_SCHEMA_ID:
            raise PoseBustersArchiveIntakeError("unsupported archive-contract schema")
        object.__setattr__(self, "dataset_id", _text(self.dataset_id, name="dataset_id"))
        for name in (
            "archive_sha256",
            "selection_sha256",
            "case_id_projection_sha256",
            "embedded_case_list_sha256",
            "readme_sha256",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name=name))
        for name, maximum in (
            ("archive_size_bytes", POSEBUSTERS_ARCHIVE_MAX_BYTES),
            ("selection_size_bytes", POSEBUSTERS_ARCHIVE_MAX_SELECTION_BYTES),
            ("selected_case_count", POSEBUSTERS_ARCHIVE_MAX_ENTRIES),
            ("archive_entry_count", POSEBUSTERS_ARCHIVE_MAX_ENTRIES),
            (
                "archive_uncompressed_size_bytes",
                POSEBUSTERS_ARCHIVE_MAX_UNCOMPRESSED_BYTES,
            ),
            ("archive_benchmark_case_count", POSEBUSTERS_ARCHIVE_MAX_ENTRIES),
        ):
            object.__setattr__(
                self,
                name,
                _positive_int(getattr(self, name), name=name, maximum=maximum),
            )
        for name in (
            "benchmark_root",
            "embedded_case_list_member",
            "readme_member",
        ):
            value = _text(getattr(self, name), name=name)
            path = PurePosixPath(value)
            if path.is_absolute() or ".." in path.parts or "\\" in value:
                raise PoseBustersArchiveIntakeError(
                    "archive contract member path is unsafe"
                )
            object.__setattr__(self, name, value.rstrip("/"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "dataset_id": self.dataset_id,
            "archive_sha256": self.archive_sha256,
            "archive_size_bytes": self.archive_size_bytes,
            "selection_sha256": self.selection_sha256,
            "selection_size_bytes": self.selection_size_bytes,
            "case_id_projection_sha256": self.case_id_projection_sha256,
            "selected_case_count": self.selected_case_count,
            "archive_entry_count": self.archive_entry_count,
            "archive_uncompressed_size_bytes": self.archive_uncompressed_size_bytes,
            "archive_benchmark_case_count": self.archive_benchmark_case_count,
            "benchmark_root": self.benchmark_root,
            "embedded_case_list_member": self.embedded_case_list_member,
            "embedded_case_list_sha256": self.embedded_case_list_sha256,
            "readme_member": self.readme_member,
            "readme_sha256": self.readme_sha256,
            "member_roles": list(POSEBUSTERS_ARCHIVE_MEMBER_ROLES),
            "member_role_suffixes": dict(POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES),
            "archive_extraction_allowed": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT = PoseBustersArchiveContract(
    dataset_id=POSEBUSTERS_2023_308_DATASET_ID,
    archive_sha256=POSEBUSTERS_2023_ARCHIVE_SHA256,
    archive_size_bytes=POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES,
    selection_sha256=POSEBUSTERS_2023_308_SELECTION_SHA256,
    selection_size_bytes=POSEBUSTERS_ARCHIVE_SELECTION_SIZE_BYTES,
    case_id_projection_sha256=POSEBUSTERS_2023_308_CASE_ID_PROJECTION_SHA256,
    selected_case_count=POSEBUSTERS_ARCHIVE_SELECTED_CASE_COUNT,
    archive_entry_count=POSEBUSTERS_ARCHIVE_ENTRY_COUNT,
    archive_uncompressed_size_bytes=POSEBUSTERS_ARCHIVE_UNCOMPRESSED_SIZE_BYTES,
    archive_benchmark_case_count=POSEBUSTERS_ARCHIVE_BENCHMARK_CASE_COUNT,
    benchmark_root="posebusters_benchmark_set",
    embedded_case_list_member="posebusters_benchmark_set_ids.txt",
    embedded_case_list_sha256=POSEBUSTERS_ARCHIVE_428_ID_SHA256,
    readme_member="README.txt",
    readme_sha256=POSEBUSTERS_ARCHIVE_README_SHA256,
)


@dataclass(frozen=True, slots=True)
class PoseBustersArchiveArtifact:
    role: str
    member_path: str
    sha256: str
    size_bytes: int
    schema_id: str = POSEBUSTERS_ARCHIVE_ARTIFACT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_ARCHIVE_ARTIFACT_SCHEMA_ID:
            raise PoseBustersArchiveIntakeError("unsupported archive-artifact schema")
        if self.role not in POSEBUSTERS_ARCHIVE_MEMBER_ROLES:
            raise PoseBustersArchiveIntakeError("archive artifact role is invalid")
        member = _text(self.member_path, name="archive member path")
        path = PurePosixPath(member)
        if path.is_absolute() or ".." in path.parts or "\\" in member:
            raise PoseBustersArchiveIntakeError("archive artifact path is unsafe")
        object.__setattr__(self, "member_path", member)
        object.__setattr__(self, "sha256", _sha256(self.sha256, name="archive artifact"))
        object.__setattr__(
            self,
            "size_bytes",
            _positive_int(
                self.size_bytes,
                name="archive artifact size",
                maximum=POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "role": self.role,
            "member_path": self.member_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersArchiveCaseRow:
    case_id: str
    status: str
    artifacts: tuple[PoseBustersArchiveArtifact, ...]
    error_codes: tuple[str, ...]
    schema_id: str = POSEBUSTERS_ARCHIVE_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_ARCHIVE_CASE_SCHEMA_ID:
            raise PoseBustersArchiveIntakeError("unsupported archive-case schema")
        case_id = _case_id(self.case_id)
        status = _text(self.status, name="archive case status").lower()
        if status not in {"ready", "failure"}:
            raise PoseBustersArchiveIntakeError("archive case status is invalid")
        artifacts = tuple(self.artifacts)
        errors = tuple(_text(value, name="archive case error") for value in self.error_codes)
        if any(not isinstance(item, PoseBustersArchiveArtifact) for item in artifacts):
            raise PoseBustersArchiveIntakeError("archive case artifact type is invalid")
        roles = tuple(item.role for item in artifacts)
        if len(roles) != len(set(roles)):
            raise PoseBustersArchiveIntakeError("archive case artifact roles repeat")
        if status == "ready":
            valid = roles == POSEBUSTERS_ARCHIVE_MEMBER_ROLES and not errors
        else:
            valid = bool(errors) and len(errors) == len(set(errors))
        if not valid:
            raise PoseBustersArchiveIntakeError(
                "archive case status, artifacts, and errors are inconsistent"
            )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "error_codes", errors)

    def to_dict(self) -> dict[str, Any]:
        pdb_id, ccd_id = self.case_id.split("_")
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "pdb_id": pdb_id,
            "ccd_id": ccd_id,
            "status": self.status,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "error_codes": list(self.error_codes),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersArchiveIntakeReceipt:
    contract: PoseBustersArchiveContract
    archive_observed_sha256: str
    archive_observed_size_bytes: int
    selection_observed_sha256: str
    selection_observed_size_bytes: int
    archive_entry_count: int
    archive_uncompressed_size_bytes: int
    archive_benchmark_case_count: int
    global_error_codes: tuple[str, ...]
    case_rows: tuple[PoseBustersArchiveCaseRow, ...]
    schema_id: str = POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID:
            raise PoseBustersArchiveIntakeError("unsupported archive-intake schema")
        if not isinstance(self.contract, PoseBustersArchiveContract):
            raise PoseBustersArchiveIntakeError("archive intake contract has the wrong type")
        for name in ("archive_observed_sha256", "selection_observed_sha256"):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        for name in (
            "archive_observed_size_bytes",
            "selection_observed_size_bytes",
        ):
            object.__setattr__(
                self,
                name,
                _positive_int(getattr(self, name), name=name),
            )
        for name in (
            "archive_entry_count",
            "archive_uncompressed_size_bytes",
            "archive_benchmark_case_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PoseBustersArchiveIntakeError(
                    "archive structure counts must be non-negative integers"
                )
        global_errors = tuple(
            _text(value, name="archive global error") for value in self.global_error_codes
        )
        if len(global_errors) != len(set(global_errors)):
            raise PoseBustersArchiveIntakeError("archive global errors must be unique")
        rows = tuple(self.case_rows)
        if (
            len(rows) != self.contract.selected_case_count
            or any(not isinstance(row, PoseBustersArchiveCaseRow) for row in rows)
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersArchiveIntakeError(
                "archive intake must retain every selected case in canonical order"
            )
        if global_errors and any(row.status != "failure" for row in rows):
            raise PoseBustersArchiveIntakeError(
                "archive global failure must fail every selected case"
            )
        object.__setattr__(self, "global_error_codes", global_errors)
        object.__setattr__(self, "case_rows", rows)

    @property
    def official_contract(self) -> bool:
        return (
            self.contract.fingerprint_sha256
            == OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT.fingerprint_sha256
        )

    @property
    def ready_case_count(self) -> int:
        return sum(row.status == "ready" for row in self.case_rows)

    @property
    def input_identity_ready(self) -> bool:
        return (
            self.official_contract
            and not self.global_error_codes
            and self.ready_case_count == len(self.case_rows)
        )

    def _payload(self) -> dict[str, Any]:
        blockers = list(POSEBUSTERS_ARCHIVE_SCIENTIFIC_BLOCKERS)
        if not self.official_contract:
            blockers.insert(0, "non_official_archive_contract")
        if not self.input_identity_ready:
            blockers.insert(0, "posebusters_archive_input_identity_not_ready")
        return {
            "schema_id": self.schema_id,
            "contract": self.contract.to_dict(),
            "contract_sha256": self.contract.fingerprint_sha256,
            "official_contract": self.official_contract,
            "archive_observed_sha256": self.archive_observed_sha256,
            "archive_observed_size_bytes": self.archive_observed_size_bytes,
            "selection_observed_sha256": self.selection_observed_sha256,
            "selection_observed_size_bytes": self.selection_observed_size_bytes,
            "archive_entry_count": self.archive_entry_count,
            "archive_uncompressed_size_bytes": self.archive_uncompressed_size_bytes,
            "archive_benchmark_case_count": self.archive_benchmark_case_count,
            "selected_case_count": len(self.case_rows),
            "ready_case_count": self.ready_case_count,
            "failed_case_count": len(self.case_rows) - self.ready_case_count,
            "global_error_codes": list(self.global_error_codes),
            "case_rows": [row.to_dict() for row in self.case_rows],
            "input_identity_ready": self.input_identity_ready,
            "archive_extracted": False,
            "network_fetch_performed": False,
            "license_acceptance_performed": False,
            "pose_generation_performed": False,
            "benchmark_executed": False,
            "scientific_blockers": blockers,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=str(output.parent),
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, output, follow_symlinks=False)
            except FileExistsError as exc:
                raise PoseBustersArchiveIntakeError(
                    "PoseBusters intake output already exists"
                ) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return output


def _selection_case_ids(
    selection_path: str | os.PathLike[str],
    contract: PoseBustersArchiveContract,
) -> tuple[bytes, tuple[str, ...]]:
    source = _read_exact_regular_file(
        selection_path,
        maximum_bytes=POSEBUSTERS_ARCHIVE_MAX_SELECTION_BYTES,
    )
    if (
        len(source) != contract.selection_size_bytes
        or hashlib.sha256(source).hexdigest() != contract.selection_sha256
    ):
        raise PoseBustersArchiveIntakeError(
            "PoseBusters selection does not match the frozen identity"
        )
    try:
        case_ids = tuple(_case_id(value) for value in source.decode("ascii").split())
    except UnicodeDecodeError as exc:
        raise PoseBustersArchiveIntakeError(
            "PoseBusters selection must be ASCII"
        ) from exc
    if (
        len(case_ids) != contract.selected_case_count
        or len(set(case_ids)) != len(case_ids)
        or case_ids != tuple(sorted(case_ids))
        or _canonical_sha256(list(case_ids)) != contract.case_id_projection_sha256
    ):
        raise PoseBustersArchiveIntakeError(
            "PoseBusters selection case projection is invalid"
        )
    return source, case_ids


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(
        name
        and "\x00" not in name
        and "\\" not in name
        and not path.is_absolute()
        and ".." not in path.parts
    )


def _stream_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> tuple[str, int]:
    if info.file_size <= 0 or info.file_size > POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES:
        raise PoseBustersArchiveIntakeError("archive member size is outside the bound")
    digest = hashlib.sha256()
    observed = 0
    try:
        with archive.open(info, "r") as handle:
            while True:
                chunk = handle.read(POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                observed += len(chunk)
                if observed > info.file_size:
                    raise PoseBustersArchiveIntakeError(
                        "archive member exceeded its declared size"
                    )
                digest.update(chunk)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PoseBustersArchiveIntakeError(
            "archive member failed bounded CRC-checked streaming"
        ) from exc
    if observed != info.file_size:
        raise PoseBustersArchiveIntakeError(
            "archive member size disagrees with streamed bytes"
        )
    return digest.hexdigest(), observed


def _all_failure_rows(
    case_ids: Sequence[str],
    error_code: str,
) -> tuple[PoseBustersArchiveCaseRow, ...]:
    return tuple(
        PoseBustersArchiveCaseRow(
            case_id=case_id,
            status="failure",
            artifacts=(),
            error_codes=(error_code,),
        )
        for case_id in case_ids
    )


def _receipt_for_global_failure(
    *,
    contract: PoseBustersArchiveContract,
    archive_sha256: str,
    archive_size: int,
    selection_sha256: str,
    selection_size: int,
    case_ids: Sequence[str],
    error_code: str,
) -> PoseBustersArchiveIntakeReceipt:
    return PoseBustersArchiveIntakeReceipt(
        contract=contract,
        archive_observed_sha256=archive_sha256,
        archive_observed_size_bytes=archive_size,
        selection_observed_sha256=selection_sha256,
        selection_observed_size_bytes=selection_size,
        archive_entry_count=0,
        archive_uncompressed_size_bytes=0,
        archive_benchmark_case_count=0,
        global_error_codes=(error_code,),
        case_rows=_all_failure_rows(case_ids, error_code),
    )


def materialize_posebusters_archive_intake(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersArchiveIntakeReceipt:
    """Stream exact selected artifacts into a failure-inclusive receipt."""

    selection_source, case_ids = _selection_case_ids(selection_path, contract)
    selection_sha256 = hashlib.sha256(selection_source).hexdigest()
    archive_descriptor, archive_size = _regular_file_descriptor(
        archive_path,
        maximum_bytes=POSEBUSTERS_ARCHIVE_MAX_BYTES,
    )
    try:
        archive_sha256 = _hash_descriptor(archive_descriptor, archive_size)
        if (
            archive_sha256 != contract.archive_sha256
            or archive_size != contract.archive_size_bytes
        ):
            return _receipt_for_global_failure(
                contract=contract,
                archive_sha256=archive_sha256,
                archive_size=archive_size,
                selection_sha256=selection_sha256,
                selection_size=len(selection_source),
                case_ids=case_ids,
                error_code="archive_identity_verification_failed",
            )
        with os.fdopen(archive_descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    infos = archive.infolist()
                    names = tuple(info.filename for info in infos)
                    unsafe = (
                        len(infos) != contract.archive_entry_count
                        or len(infos) > POSEBUSTERS_ARCHIVE_MAX_ENTRIES
                        or len(names) != len(set(names))
                        or any(not _safe_member_name(name) for name in names)
                        or any(info.flag_bits & 0x1 for info in infos)
                        or any(
                            info.compress_type not in _ALLOWED_COMPRESSION
                            for info in infos
                        )
                        or any(
                            stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)
                            for info in infos
                        )
                    )
                    file_infos = tuple(info for info in infos if not info.is_dir())
                    uncompressed = sum(info.file_size for info in file_infos)
                    if (
                        unsafe
                        or uncompressed != contract.archive_uncompressed_size_bytes
                        or uncompressed > POSEBUSTERS_ARCHIVE_MAX_UNCOMPRESSED_BYTES
                        or any(
                            info.file_size > POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES
                            for info in file_infos
                        )
                    ):
                        return _receipt_for_global_failure(
                            contract=contract,
                            archive_sha256=archive_sha256,
                            archive_size=archive_size,
                            selection_sha256=selection_sha256,
                            selection_size=len(selection_source),
                            case_ids=case_ids,
                            error_code="archive_structure_verification_failed",
                        )
                    info_by_name = {info.filename: info for info in infos}
                    benchmark_case_ids = {
                        parts[1]
                        for name in names
                        if len(parts := PurePosixPath(name).parts) >= 2
                        and parts[0] == contract.benchmark_root
                        and parts[1]
                    }
                    if len(benchmark_case_ids) != contract.archive_benchmark_case_count:
                        return _receipt_for_global_failure(
                            contract=contract,
                            archive_sha256=archive_sha256,
                            archive_size=archive_size,
                            selection_sha256=selection_sha256,
                            selection_size=len(selection_source),
                            case_ids=case_ids,
                            error_code="archive_benchmark_case_count_mismatch",
                        )
                    for member_name, expected_sha256 in (
                        (
                            contract.embedded_case_list_member,
                            contract.embedded_case_list_sha256,
                        ),
                        (contract.readme_member, contract.readme_sha256),
                    ):
                        info = info_by_name.get(member_name)
                        if info is None or info.is_dir():
                            return _receipt_for_global_failure(
                                contract=contract,
                                archive_sha256=archive_sha256,
                                archive_size=archive_size,
                                selection_sha256=selection_sha256,
                                selection_size=len(selection_source),
                                case_ids=case_ids,
                                error_code="archive_metadata_member_missing",
                            )
                        observed_sha256, _ = _stream_member(archive, info)
                        if observed_sha256 != expected_sha256:
                            return _receipt_for_global_failure(
                                contract=contract,
                                archive_sha256=archive_sha256,
                                archive_size=archive_size,
                                selection_sha256=selection_sha256,
                                selection_size=len(selection_source),
                                case_ids=case_ids,
                                error_code="archive_metadata_member_identity_mismatch",
                            )
                    rows: list[PoseBustersArchiveCaseRow] = []
                    for case_id in case_ids:
                        artifacts: list[PoseBustersArchiveArtifact] = []
                        errors: list[str] = []
                        for role in POSEBUSTERS_ARCHIVE_MEMBER_ROLES:
                            member_name = (
                                f"{contract.benchmark_root}/{case_id}/"
                                f"{case_id}{POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES[role]}"
                            )
                            info = info_by_name.get(member_name)
                            if info is None or info.is_dir():
                                errors.append(f"{role}_missing")
                                continue
                            try:
                                member_sha256, member_size = _stream_member(
                                    archive,
                                    info,
                                )
                            except PoseBustersArchiveIntakeError:
                                errors.append(f"{role}_stream_verification_failed")
                                continue
                            artifacts.append(
                                PoseBustersArchiveArtifact(
                                    role=role,
                                    member_path=member_name,
                                    sha256=member_sha256,
                                    size_bytes=member_size,
                                )
                            )
                        rows.append(
                            PoseBustersArchiveCaseRow(
                                case_id=case_id,
                                status="failure" if errors else "ready",
                                artifacts=tuple(artifacts),
                                error_codes=tuple(errors),
                            )
                        )
                    return PoseBustersArchiveIntakeReceipt(
                        contract=contract,
                        archive_observed_sha256=archive_sha256,
                        archive_observed_size_bytes=archive_size,
                        selection_observed_sha256=selection_sha256,
                        selection_observed_size_bytes=len(selection_source),
                        archive_entry_count=len(infos),
                        archive_uncompressed_size_bytes=uncompressed,
                        archive_benchmark_case_count=len(benchmark_case_ids),
                        global_error_codes=(),
                        case_rows=tuple(rows),
                    )
            except (OSError, RuntimeError, zipfile.BadZipFile):
                return _receipt_for_global_failure(
                    contract=contract,
                    archive_sha256=archive_sha256,
                    archive_size=archive_size,
                    selection_sha256=selection_sha256,
                    selection_size=len(selection_source),
                    case_ids=case_ids,
                    error_code="archive_zip_verification_failed",
                )
    finally:
        os.close(archive_descriptor)


def verify_posebusters_archive_intake_receipt(
    receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersArchiveIntakeReceipt:
    """Reexecute intake and require exact canonical receipt equality."""

    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=POSEBUSTERS_ARCHIVE_MAX_RECEIPT_BYTES,
    )
    expected = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )
    expected_bytes = _canonical_bytes(expected.to_dict()) + b"\n"
    if source != expected_bytes:
        raise PoseBustersArchiveIntakeError(
            "PoseBusters intake receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-intake",
        description="Verify the exact public PoseBusters 308 archive without extraction.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--archive", required=True)
    materialize.add_argument("--selection", required=True)
    materialize.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--archive", required=True)
    verify.add_argument("--selection", required=True)
    verify.add_argument("--receipt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "materialize":
        receipt = materialize_posebusters_archive_intake(
            args.archive,
            args.selection,
        )
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_archive_intake_receipt(
            args.receipt,
            args.archive,
            args.selection,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "selected_case_count": len(receipt.case_rows),
                "ready_case_count": receipt.ready_case_count,
                "input_identity_ready": receipt.input_identity_ready,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT",
    "POSEBUSTERS_ARCHIVE_ARTIFACT_SCHEMA_ID",
    "POSEBUSTERS_ARCHIVE_CASE_SCHEMA_ID",
    "POSEBUSTERS_ARCHIVE_CONTRACT_SCHEMA_ID",
    "POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID",
    "POSEBUSTERS_ARCHIVE_MAX_BYTES",
    "POSEBUSTERS_ARCHIVE_MAX_ENTRIES",
    "POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES",
    "POSEBUSTERS_ARCHIVE_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_ARCHIVE_MAX_SELECTION_BYTES",
    "POSEBUSTERS_ARCHIVE_MAX_UNCOMPRESSED_BYTES",
    "POSEBUSTERS_ARCHIVE_MEMBER_ROLES",
    "POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES",
    "POSEBUSTERS_ARCHIVE_SCIENTIFIC_BLOCKERS",
    "PoseBustersArchiveArtifact",
    "PoseBustersArchiveCaseRow",
    "PoseBustersArchiveContract",
    "PoseBustersArchiveIntakeError",
    "PoseBustersArchiveIntakeReceipt",
    "main",
    "materialize_posebusters_archive_intake",
    "verify_posebusters_archive_intake_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
