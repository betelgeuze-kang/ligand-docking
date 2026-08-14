"""Fail-closed support for the synthetic fixed64 full-pipeline CPU profile.

The implementation profile intentionally has no live execution capability.
It can verify the exact main-push native artifact and its minimal CPython
runtime, and it contains an injected-clock test double for the future paired
measurement core.  A separately reviewed activation contract must bind the
merged source before one local synthetic attempt can be consumed.
"""

from __future__ import annotations

import base64
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
from types import MappingProxyType
from typing import Callable, Final, Mapping, Protocol, Sequence
import zipfile


PROFILE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_full_pipeline_cpu_performance_profile/1.0.0"
)
PROFILE_ID: Final = "engine_v2_full_pipeline_cpu_performance_v1"
PROFILE_SHA256: Final = (
    "385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000"
)
LOCAL_RUNTIME_EVIDENCE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_full_pipeline_cpu_runtime_binding_evidence/1.0.0"
)
DURABLE_ARCHIVE_EVIDENCE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_full_pipeline_cpu_durable_archive_evidence/1.0.0"
)
TEST_DOUBLE_RECEIPT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_full_pipeline_cpu_performance_test_double_receipt/1.0.0"
)

BASELINE_BACKEND: Final = "cpp_cpu_reference"
EXPERIMENTAL_BACKEND: Final = "rust_cpu"
BACKENDS: Final = (BASELINE_BACKEND, EXPERIMENTAL_BACKEND)
CONSUMER_SURFACE: Final = "benchmark"
WARMUP_COUNT: Final = 5
SAMPLE_COUNT: Final = 30
PERCENTILE_NUMERATORS: Final = (50, 95)
PERCENTILE_DENOMINATOR: Final = 100
EXPECTED_DECISION_SHA256: Final = (
    "8908c757de4e7a8f5d12452e40ec0292b44c3db7893f98d5b92956e1f0c9d9f4"
)
PARITY_ABSOLUTE_TOLERANCE: Final = 1.0e-11
PARITY_RELATIVE_TOLERANCE: Final = 4.0e-12
EXPECTED_PARITY_F64_COUNT: Final = 16_896
EXPECTED_STAGE_COUNTS: Final = MappingProxyType(
    {
        "generated_count": 54,
        "typed_failure_count": 10,
        "initial_admitted_count": 30,
        "refined_count": 16,
        "post_admitted_count": 16,
        "post_rejected_count": 0,
        "scored_count": 16,
        "valid_count": 16,
        "cluster_count": 12,
    }
)
EXPECTED_RANK_SELECTION: Final = MappingProxyType(
    {
        "primary_slot_indices": (
            23,
            63,
            9,
            10,
            29,
            16,
            61,
            8,
            11,
            52,
            20,
            13,
            33,
            26,
            34,
            22,
        ),
        "valid_slot_indices": (
            23,
            63,
            9,
            10,
            29,
            16,
            61,
            8,
            11,
            52,
            20,
            13,
            33,
            26,
            34,
            22,
        ),
        "representative_slot_indices": (23, 9, 10, 29, 16, 8, 11, 52, 20, 13, 33, 22),
        "top_k_slot_indices": (23, 9, 10, 29, 16),
    }
)
EXPECTED_SOURCE_IDENTITIES: Final = MappingProxyType(
    {
        "repository_source_bundle_receipt_sha256": (
            "80a7ee8fe919523c7afab78467dddb9bc2e653e028f1e731c9058db3ef17a68f"
        ),
        "repository_source_prepared_input_receipt_sha256": (
            "9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e"
        ),
        "repository_allocation_receipt_sha256": (
            "8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb"
        ),
    }
)
SYNTHETIC_ONLY_ACKNOWLEDGMENT: Final = (
    "repository-synthetic-d0-only:no-reservation:no-molecular-experiment:"
    "no-qualification-rerun:no-product-action:no-public-or-scientific-claim"
)

EXPECTED_ARTIFACT_ROWS: Final = (
    MappingProxyType(
        {
            "path": "betelgeuze-engine-v2-native-0.2.0rc6.spdx.json",
            "sha256": (
                "c72445b0153cec5edd16e7b3b76918ad91eaf7aee5bd167f3142414d92cbd737"
            ),
            "size_bytes": 49_844,
        }
    ),
    MappingProxyType(
        {
            "path": (
                "betelgeuze_engine_v2_native-0.2.0rc6-cp310-cp310-"
                "manylinux_2_28_x86_64.whl"
            ),
            "sha256": (
                "54f21885cdf6b4410bd084a876fb73f53a8a7b8c37b9e615e4dae36225f2e4b4"
            ),
            "size_bytes": 1_182_649,
        }
    ),
)
EXPECTED_ARTIFACT_MANIFEST_SHA256: Final = (
    "9f99bcea4f56768d6e9187b5c0d04ca2528411aced2efceae31481b7330e24b2"
)
DURABLE_ARCHIVE_DIRECTORY: Final = PurePosixPath(
    "packaging/engine-v2/native-runtime-archive/0.2.0rc6/cp310-cp310"
)
EXPECTED_DURABLE_ARCHIVE_ROWS: Final = tuple(
    MappingProxyType(
        {
            "path": str(DURABLE_ARCHIVE_DIRECTORY / str(row["path"])),
            "sha256": row["sha256"],
            "size_bytes": row["size_bytes"],
        }
    )
    for row in EXPECTED_ARTIFACT_ROWS
)
EXPECTED_DURABLE_ARCHIVE_MANIFEST_SHA256: Final = (
    "a85cf282dbf26d26bf9e2679dbc47a0b2df2e12f53ee4e88bf7fcb6d0a273a18"
)
EXPECTED_SITE_ROWS: Final = (
    MappingProxyType(
        {
            "path": "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/METADATA",
            "sha256": (
                "e8a7e538cee43befb3a0b8b63b9b7b88db8d2969cf3da012af4694b902d5f64b"
            ),
            "size_bytes": 284,
        }
    ),
    MappingProxyType(
        {
            "path": "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/RECORD",
            "sha256": (
                "bc0a36835a71cccb363db81b0a26c1846d875477e175eb9dfbc12fecb9ee7c12"
            ),
            "size_bytes": 517,
        }
    ),
    MappingProxyType(
        {
            "path": "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/WHEEL",
            "sha256": (
                "e0b0b2962b6b3e1aca30116e39ad7ee772d32cf103803fd598f0f56370f0203b"
            ),
            "size_bytes": 109,
        }
    ),
    MappingProxyType(
        {
            "path": "betelgeuze_engine_v2_native/__init__.py",
            "sha256": (
                "5fe535168f9dcffd7d7d4807f5c33b09c1a8936d9d532f49f2af196b4f82ff92"
            ),
            "size_bytes": 191,
        }
    ),
    MappingProxyType(
        {
            "path": (
                "betelgeuze_engine_v2_native/"
                "betelgeuze_engine_v2_native.cpython-310-x86_64-linux-gnu.so"
            ),
            "sha256": (
                "ff7b5e6ba7c0e250cf739292d34c562d0bd142d5f7f6c842c5c191d42b2504e1"
            ),
            "size_bytes": 2_599_704,
        }
    ),
)
EXPECTED_SITE_MANIFEST_SHA256: Final = (
    "5b720c659aec55ad416f7d263d240b98b75d2d699f247f0b83c42f7002f63119"
)
EXPECTED_RUNTIME_SCOPE_MANIFEST_SHA256: Final = (
    "72b90f500af43c921ce0b8f7d6774c5e99a7e4f3fe366478b3fc33b524b4b404"
)
EXPECTED_PYTHON_SHA256: Final = (
    "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86"
)
EXPECTED_PYTHON_SHARED_LIBRARY_SHA256: Final = (
    "1ece943a1641101b1c678b553a7a0fbb6683ff0ad76f7ebce9f8844354e3f153"
)
EXPECTED_PYVENV_SHA256: Final = (
    "db6c8a96f25493eda9f74f23f0b5f248a8b50a5b469b15c5ee7313875b416364"
)
EXPECTED_PYVENV_BYTES: Final = (
    b"home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.10.12\n"
)
EXPECTED_TOP_LEVEL_SITE_NAMES: Final = (
    "betelgeuze_engine_v2_native",
    "betelgeuze_engine_v2_native-0.2.0rc6.dist-info",
)
EXPECTED_INTERPRETER_LINKS: Final = MappingProxyType(
    {
        "bin/python": "python3.10",
        "bin/python3": "python3.10",
        "bin/python3.10": "/usr/bin/python3.10",
    }
)
EXPECTED_SESSION_AUTHORITY_FALSE_FIELDS: Final = (
    "reservation_authorized",
    "molecular_execution_authorized",
    "benchmark_execution_authorized",
    "scientific_claim_authorized",
    "hip_device_execution_authorized",
    "existing_rank_auto_change_authorized",
    "customer_pose_emission_authorized",
    "production_claim_authorized",
    "qualification_rerun_authorized",
    "d1_d2_molecular_execution_authorized",
    "historical_ab_execution_authorized",
    "fresh_holdout_execution_authorized",
    "public_benchmark_authorized",
    "stage0_admission_authorized",
    "product_performance_claim_authorized",
)
EXPECTED_EVIDENCE_AUTHORITY_FALSE_FIELDS: Final = (
    "reservation_authorized",
    "molecular_execution_authorized",
    "existing_rank_auto_change_authorized",
    "customer_pose_emission_authorized",
    "production_claim_authorized",
    "result_dependent_input_consumed",
    "fallback_allowed",
    "multi_anchor_consumed",
    "benchmark_execution_authorized",
    "scientific_claim_authorized",
    "qualification_rerun_authorized",
    "d1_d2_molecular_execution_authorized",
    "historical_ab_execution_authorized",
    "fresh_holdout_execution_authorized",
    "public_benchmark_authorized",
    "stage0_admission_authorized",
    "product_performance_claim_authorized",
)
EXPECTED_SCORER_FIELDS: Final = frozenset(
    {
        "status",
        "failure_code",
        "weighted_terms",
        "total_score",
        "receptor_candidate_pair_count",
        "ligand_pair_count",
        "hbond_count",
        "hydrophobic_contact_count",
        "buried_polar_count",
    }
)
EXPECTED_VALIDITY_FIELDS: Final = frozenset(
    {
        "status",
        "failure_code",
        "upstream_scorer_failure_code",
        "passed_check_mask",
        "blocker_mask",
        "observed_count",
        "atom_count",
        "rotation_orthogonality_max_error",
        "rotation_determinant",
        "max_bond_length_delta_angstrom",
        "minimum_ligand_nonbonded_distance_angstrom",
        "evaluated_ligand_nonbonded_pair_count",
        "excluded_ligand_pair_count",
        "minimum_receptor_ligand_distance_angstrom",
        "evaluated_receptor_ligand_pair_count",
        "minimum_declared_chiral_volume",
        "declared_chirality_center_count",
        "maximum_pocket_center_distance_angstrom",
        "element_vdw_ligand_pair_count",
        "element_vdw_ligand_severe_overlap_count",
        "element_vdw_ligand_minimum_distance_angstrom",
        "element_vdw_ligand_minimum_ratio",
        "element_vdw_receptor_candidate_pair_count",
        "element_vdw_receptor_full_cartesian_pair_count",
        "element_vdw_receptor_cell_count",
        "element_vdw_receptor_severe_overlap_count",
        "element_vdw_receptor_minimum_distance_angstrom",
        "element_vdw_receptor_minimum_ratio",
    }
)
EXPECTED_VALIDITY_FLOAT_FIELDS: Final = frozenset(
    {
        "rotation_orthogonality_max_error",
        "rotation_determinant",
        "max_bond_length_delta_angstrom",
        "minimum_ligand_nonbonded_distance_angstrom",
        "minimum_receptor_ligand_distance_angstrom",
        "minimum_declared_chiral_volume",
        "maximum_pocket_center_distance_angstrom",
        "element_vdw_ligand_minimum_distance_angstrom",
        "element_vdw_ligand_minimum_ratio",
        "element_vdw_receptor_minimum_distance_angstrom",
        "element_vdw_receptor_minimum_ratio",
    }
)
EXPECTED_RANKING_FIELDS: Final = frozenset(
    {
        "rank_eligible",
        "valid_rank_eligible",
        "stable_rank",
        "stable_valid_rank",
        "total_score",
        "coordinate_sha256",
    }
)
REQUIRED_LINEAGE_DIGEST_FIELDS: Final = (
    "scorer_evidence_sha256",
    "validity_evidence_sha256",
    "ranking_evidence_sha256",
    "row_receipt_sha256",
)
REQUIRED_EXACT_CANDIDATE_SOURCE_DIGEST_FIELDS: Final = frozenset(
    {
        "allocation_slot_receipt_sha256",
        "source_coordinate_sha256",
        "source_payload_receipt_sha256",
        "source_proposal_sha256",
    }
)

MAX_RUNTIME_FILE_BYTES: Final = 16 * 1024 * 1024
MAX_ARTIFACT_FILE_BYTES: Final = 4 * 1024 * 1024


class FullPipelineCPUPerformanceV1Error(RuntimeError):
    """The implementation profile or its exact runtime failed closed."""


class _Evidence(Protocol):
    def to_dict(self) -> dict[str, object]: ...


class _PreparedSession(Protocol):
    def describe(self) -> dict[str, object]: ...

    def run(self, *, surface: str) -> _Evidence: ...


@dataclass(frozen=True, slots=True)
class _ValidatedEvidence:
    document: dict[str, object]
    pipeline_receipt_sha256: str
    scientific_projection_sha256: str


@dataclass(frozen=True, slots=True)
class LocalRuntimeBindingEvidenceV1:
    """Offline verification of the exact downloaded artifact and runtime copy."""

    artifact_manifest_sha256: str
    runtime_scope_manifest_sha256: str
    site_packages_manifest_sha256: str
    python_executable_sha256: str
    native_extension_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": LOCAL_RUNTIME_EVIDENCE_SCHEMA_ID,
            "profile_id": PROFILE_ID,
            "artifact_manifest_sha256": self.artifact_manifest_sha256,
            "runtime_scope_manifest_sha256": self.runtime_scope_manifest_sha256,
            "site_packages_manifest_sha256": self.site_packages_manifest_sha256,
            "python_executable_sha256": self.python_executable_sha256,
            "native_extension_sha256": self.native_extension_sha256,
            "artifact_and_runtime_verified": True,
            "imports_performed": False,
            "performance_measurement_performed": False,
            "qualification_consumed": False,
            "reservation_created": False,
            "all_authority_false": True,
        }


@dataclass(frozen=True, slots=True)
class DurableRepositoryArchiveEvidenceV1:
    """Offline proof that expiring transport payloads survive in Git history."""

    repository_archive_manifest_sha256: str
    sbom_sha256: str
    wheel_sha256: str
    payload_total_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": DURABLE_ARCHIVE_EVIDENCE_SCHEMA_ID,
            "profile_id": PROFILE_ID,
            "repository_archive_manifest_sha256": (
                self.repository_archive_manifest_sha256
            ),
            "sbom_sha256": self.sbom_sha256,
            "wheel_sha256": self.wheel_sha256,
            "payload_total_bytes": self.payload_total_bytes,
            "durable_repository_archive_verified": True,
            "actions_artifact_is_transport_only": True,
            "imports_performed": False,
            "performance_measurement_performed": False,
            "qualification_consumed": False,
            "reservation_created": False,
            "all_authority_false": True,
        }


@dataclass(frozen=True, slots=True)
class TestDoubleMeasurementReceiptV1:
    """Immutable unit-test receipt; it can never attest a live qualification."""

    observations: tuple[Mapping[str, object], ...]
    parity_observations: tuple[Mapping[str, object], ...]
    summaries: Mapping[str, Mapping[str, int]]
    schedule_sha256: str
    backend_pipeline_receipts: Mapping[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": TEST_DOUBLE_RECEIPT_SCHEMA_ID,
            "profile_id": PROFILE_ID,
            "test_double_only": True,
            "live_qualification_authority": False,
            "performance_claim_authority": False,
            "candidate_denominator": 64,
            "scientific_decision_sha256": EXPECTED_DECISION_SHA256,
            "warmup_count_per_backend": WARMUP_COUNT,
            "sample_count_per_backend": SAMPLE_COUNT,
            "schedule_sha256": self.schedule_sha256,
            "backend_pipeline_receipts": dict(self.backend_pipeline_receipts),
            "observations": [dict(row) for row in self.observations],
            "parity_pair_count": len(self.parity_observations),
            "parity_observations": [dict(row) for row in self.parity_observations],
            "full_numeric_parity_passed": True,
            "summaries": {
                backend: dict(values) for backend, values in self.summaries.items()
            },
            "reservation_created": False,
            "molecular_execution_performed": False,
            "qualification_consumed": False,
        }


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _manifest_sha256(rows: Sequence[Mapping[str, object]]) -> str:
    return _sha256_bytes(_canonical_json_bytes([dict(row) for row in rows]))


def _require_real_owner_directory(path: Path, *, name: str) -> Path:
    try:
        unresolved = path.absolute()
        resolved = path.resolve(strict=True)
        metadata = unresolved.lstat()
    except OSError as exc:
        raise FullPipelineCPUPerformanceV1Error(f"{name} is unavailable") from exc
    if unresolved != resolved or not stat.S_ISDIR(metadata.st_mode):
        raise FullPipelineCPUPerformanceV1Error(
            f"{name} must be a real directory without symlinks"
        )
    if metadata.st_uid != os.geteuid() or metadata.st_mode & (
        stat.S_IWGRP | stat.S_IWOTH
    ):
        raise FullPipelineCPUPerformanceV1Error(f"{name} is not owner-controlled")
    return resolved


def _read_owner_regular_file(
    path: Path,
    *,
    name: str,
    maximum_bytes: int,
    owner_uids: tuple[int, ...] | None = None,
) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise FullPipelineCPUPerformanceV1Error(
            f"{name} cannot be opened safely"
        ) from exc
    try:
        before = os.fstat(descriptor)
        allowed_owners = owner_uids or (os.geteuid(),)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid not in allowed_owners
            or before.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            or before.st_nlink != 1
            or not 1 <= before.st_size <= maximum_bytes
        ):
            raise FullPipelineCPUPerformanceV1Error(
                f"{name} is not a bounded owner-controlled regular file"
            )
        chunks: list[bytes] = []
        observed = 0
        while observed <= maximum_bytes:
            chunk = os.read(
                descriptor,
                min(1 << 20, maximum_bytes + 1 - observed),
            )
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
        identity_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if observed != before.st_size or any(
            getattr(before, field) != getattr(after, field) for field in identity_fields
        ):
            raise FullPipelineCPUPerformanceV1Error(f"{name} changed while it was read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_repository_regular_file(
    path: Path,
    *,
    name: str,
    maximum_bytes: int,
) -> bytes:
    """Read a tracked payload without following links or accepting live drift.

    Git worktrees may be group-writable under a collaborative umask.  The exact
    profile digest and payload SHA-256 provide the integrity boundary here, so
    this archive reader permits group write while still rejecting other-write,
    foreign ownership, links, non-regular files, and mutation during the read.
    """

    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise FullPipelineCPUPerformanceV1Error(
            f"{name} cannot be opened safely"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_mode & stat.S_IWOTH
            or before.st_nlink != 1
            or not 1 <= before.st_size <= maximum_bytes
        ):
            raise FullPipelineCPUPerformanceV1Error(
                f"{name} is not a bounded repository regular file"
            )
        chunks: list[bytes] = []
        observed = 0
        while observed <= maximum_bytes:
            chunk = os.read(
                descriptor,
                min(1 << 20, maximum_bytes + 1 - observed),
            )
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
        identity_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if observed != before.st_size or any(
            getattr(before, field) != getattr(after, field) for field in identity_fields
        ):
            raise FullPipelineCPUPerformanceV1Error(f"{name} changed while it was read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _require_expected_rows(
    observed: Sequence[Mapping[str, object]],
    expected: Sequence[Mapping[str, object]],
    *,
    name: str,
) -> None:
    if [dict(row) for row in observed] != [dict(row) for row in expected]:
        raise FullPipelineCPUPerformanceV1Error(f"{name} manifest changed")


def _artifact_rows(
    artifact_directory: Path,
) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    expected_names = tuple(str(row["path"]) for row in EXPECTED_ARTIFACT_ROWS)
    try:
        entries = sorted(os.scandir(artifact_directory), key=lambda item: item.name)
    except OSError as exc:
        raise FullPipelineCPUPerformanceV1Error(
            "artifact directory cannot be enumerated"
        ) from exc
    if tuple(entry.name for entry in entries) != expected_names:
        raise FullPipelineCPUPerformanceV1Error("artifact inventory changed")
    rows: list[dict[str, object]] = []
    payloads: dict[str, bytes] = {}
    for entry in entries:
        raw = _read_owner_regular_file(
            Path(entry.path),
            name=f"artifact payload {entry.name}",
            maximum_bytes=MAX_ARTIFACT_FILE_BYTES,
        )
        rows.append(
            {
                "path": entry.name,
                "sha256": _sha256_bytes(raw),
                "size_bytes": len(raw),
            }
        )
        payloads[entry.name] = raw
    return rows, payloads


def _verify_wheel(raw: bytes) -> None:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise FullPipelineCPUPerformanceV1Error("native wheel is invalid") from exc
    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise FullPipelineCPUPerformanceV1Error(
                "native wheel contains duplicate member names"
            )
        expected_names = [str(row["path"]) for row in EXPECTED_SITE_ROWS]
        if sorted(names) != expected_names:
            raise FullPipelineCPUPerformanceV1Error(
                "native wheel member inventory changed"
            )
        observed: list[dict[str, object]] = []
        member_payloads: dict[str, bytes] = {}
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or info.is_dir():
                raise FullPipelineCPUPerformanceV1Error(
                    "native wheel contains an unsafe member"
                )
            member_raw = archive.read(info)
            observed.append(
                {
                    "path": info.filename,
                    "sha256": _sha256_bytes(member_raw),
                    "size_bytes": len(member_raw),
                }
            )
            member_payloads[info.filename] = member_raw
        observed.sort(key=lambda row: str(row["path"]))
        _require_expected_rows(
            observed,
            EXPECTED_SITE_ROWS,
            name="native wheel member",
        )
        record_name = "betelgeuze_engine_v2_native-0.2.0rc6.dist-info/RECORD"
        try:
            record_text = member_payloads[record_name].decode("utf-8")
            record_rows = list(csv.reader(io.StringIO(record_text, newline="")))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise FullPipelineCPUPerformanceV1Error(
                "native wheel RECORD is invalid"
            ) from exc
        if len(record_rows) != len(EXPECTED_SITE_ROWS):
            raise FullPipelineCPUPerformanceV1Error(
                "native wheel RECORD row count changed"
            )
        record_by_name: dict[str, tuple[str, str]] = {}
        for row in record_rows:
            if len(row) != 3 or row[0] in record_by_name:
                raise FullPipelineCPUPerformanceV1Error(
                    "native wheel RECORD schema changed"
                )
            record_by_name[row[0]] = (row[1], row[2])
        if set(record_by_name) != set(expected_names):
            raise FullPipelineCPUPerformanceV1Error(
                "native wheel RECORD inventory changed"
            )
        for expected in EXPECTED_SITE_ROWS:
            name = str(expected["path"])
            digest_text, size_text = record_by_name[name]
            if name == record_name:
                if digest_text or size_text:
                    raise FullPipelineCPUPerformanceV1Error(
                        "native wheel RECORD self-row changed"
                    )
                continue
            if not digest_text.startswith("sha256=") or size_text != str(
                expected["size_bytes"]
            ):
                raise FullPipelineCPUPerformanceV1Error(
                    "native wheel RECORD binding changed"
                )
            encoded = digest_text.removeprefix("sha256=")
            try:
                padding = "=" * (-len(encoded) % 4)
                digest = base64.urlsafe_b64decode(encoded + padding).hex()
            except (ValueError, base64.binascii.Error) as exc:
                raise FullPipelineCPUPerformanceV1Error(
                    "native wheel RECORD digest is invalid"
                ) from exc
            if digest != expected["sha256"]:
                raise FullPipelineCPUPerformanceV1Error(
                    "native wheel RECORD digest changed"
                )


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise FullPipelineCPUPerformanceV1Error(
                f"SBOM contains duplicate JSON key: {key}"
            )
        value[key] = item
    return value


def _verify_sbom(raw: bytes) -> None:
    try:
        document = json.loads(
            raw.decode("ascii"), object_pairs_hook=_reject_duplicate_json_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FullPipelineCPUPerformanceV1Error("native SBOM is invalid") from exc
    if type(document) is not dict or document.get("spdxVersion") != "SPDX-2.3":
        raise FullPipelineCPUPerformanceV1Error("native SBOM schema changed")
    if document.get("name") != "betelgeuze-engine-v2-native-0.2.0rc6-sbom":
        raise FullPipelineCPUPerformanceV1Error("native SBOM identity changed")
    packages = document.get("packages")
    if type(packages) is not list:
        raise FullPipelineCPUPerformanceV1Error("native SBOM packages are absent")
    roots = [
        row
        for row in packages
        if type(row) is dict and row.get("SPDXID") == "SPDXRef-Package-EngineV2"
    ]
    if len(roots) != 1:
        raise FullPipelineCPUPerformanceV1Error("native SBOM root package changed")
    root = roots[0]
    checksums = root.get("checksums")
    expected_wheel_sha256 = str(EXPECTED_ARTIFACT_ROWS[1]["sha256"])
    if (
        root.get("name") != "betelgeuze-engine-v2-native"
        or root.get("versionInfo") != "0.2.0rc6"
        or type(checksums) is not list
        or {tuple(sorted(item.items())) for item in checksums if type(item) is dict}
        != {(("algorithm", "SHA256"), ("checksumValue", expected_wheel_sha256))}
    ):
        raise FullPipelineCPUPerformanceV1Error(
            "native SBOM wheel checksum binding changed"
        )
    namespace = document.get("documentNamespace")
    if type(namespace) is not str or not namespace.endswith(expected_wheel_sha256):
        raise FullPipelineCPUPerformanceV1Error(
            "native SBOM namespace is not wheel-bound"
        )


def verify_durable_repository_archive(
    *, repository_root: Path
) -> DurableRepositoryArchiveEvidenceV1:
    """Verify the exact wheel and SBOM preserved under the tracked archive path."""

    try:
        unresolved_root = repository_root.absolute()
        resolved_root = repository_root.resolve(strict=True)
        root_metadata = unresolved_root.lstat()
    except OSError as exc:
        raise FullPipelineCPUPerformanceV1Error(
            "repository root is unavailable"
        ) from exc
    if (
        unresolved_root != resolved_root
        or not stat.S_ISDIR(root_metadata.st_mode)
        or root_metadata.st_uid != os.geteuid()
        or root_metadata.st_mode & stat.S_IWOTH
    ):
        raise FullPipelineCPUPerformanceV1Error(
            "repository root must be a real owner-controlled directory"
        )

    archive_directory = resolved_root.joinpath(*DURABLE_ARCHIVE_DIRECTORY.parts)
    expected_names = tuple(
        str(row["path"]).rsplit("/", 1)[-1] for row in EXPECTED_DURABLE_ARCHIVE_ROWS
    )
    try:
        entries = sorted(os.scandir(archive_directory), key=lambda item: item.name)
    except OSError as exc:
        raise FullPipelineCPUPerformanceV1Error(
            "durable repository archive cannot be enumerated"
        ) from exc
    if tuple(entry.name for entry in entries) != expected_names:
        raise FullPipelineCPUPerformanceV1Error(
            "durable repository archive inventory changed"
        )

    rows: list[dict[str, object]] = []
    payloads: dict[str, bytes] = {}
    for expected, entry in zip(EXPECTED_DURABLE_ARCHIVE_ROWS, entries, strict=True):
        raw = _read_repository_regular_file(
            Path(entry.path),
            name=f"durable repository archive payload {entry.name}",
            maximum_bytes=MAX_ARTIFACT_FILE_BYTES,
        )
        rows.append(
            {
                "path": expected["path"],
                "sha256": _sha256_bytes(raw),
                "size_bytes": len(raw),
            }
        )
        payloads[entry.name] = raw
    _require_expected_rows(
        rows,
        EXPECTED_DURABLE_ARCHIVE_ROWS,
        name="durable repository archive",
    )
    archive_manifest_sha256 = _manifest_sha256(rows)
    if archive_manifest_sha256 != EXPECTED_DURABLE_ARCHIVE_MANIFEST_SHA256:
        raise FullPipelineCPUPerformanceV1Error(
            "durable repository archive manifest is not independently rederivable"
        )

    sbom_name = str(EXPECTED_ARTIFACT_ROWS[0]["path"])
    wheel_name = str(EXPECTED_ARTIFACT_ROWS[1]["path"])
    _verify_sbom(payloads[sbom_name])
    _verify_wheel(payloads[wheel_name])
    return DurableRepositoryArchiveEvidenceV1(
        repository_archive_manifest_sha256=archive_manifest_sha256,
        sbom_sha256=_sha256_bytes(payloads[sbom_name]),
        wheel_sha256=_sha256_bytes(payloads[wheel_name]),
        payload_total_bytes=sum(len(raw) for raw in payloads.values()),
    )


def _site_package_rows(site_packages: Path) -> list[dict[str, object]]:
    try:
        roots = sorted(os.scandir(site_packages), key=lambda item: item.name)
    except OSError as exc:
        raise FullPipelineCPUPerformanceV1Error(
            "runtime site-packages cannot be enumerated"
        ) from exc
    if tuple(entry.name for entry in roots) != EXPECTED_TOP_LEVEL_SITE_NAMES:
        raise FullPipelineCPUPerformanceV1Error(
            "runtime site-packages top-level inventory changed"
        )
    pending: list[Path] = []
    for entry in roots:
        metadata = entry.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise FullPipelineCPUPerformanceV1Error(
                "runtime site-packages root is not owner-controlled"
            )
        pending.append(Path(entry.path))
    rows: list[dict[str, object]] = []
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise FullPipelineCPUPerformanceV1Error(
                "runtime site-packages payload cannot be enumerated"
            ) from exc
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(site_packages).as_posix()
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                if (
                    entry.name == "__pycache__"
                    or metadata.st_uid != os.geteuid()
                    or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                ):
                    raise FullPipelineCPUPerformanceV1Error(
                        "runtime site-packages directory changed"
                    )
                pending.append(path)
                continue
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise FullPipelineCPUPerformanceV1Error(
                    "runtime site-packages contains a forbidden file type"
                )
            raw = _read_owner_regular_file(
                path,
                name=f"runtime site-packages file {relative}",
                maximum_bytes=MAX_RUNTIME_FILE_BYTES,
            )
            rows.append(
                {
                    "path": relative,
                    "sha256": _sha256_bytes(raw),
                    "size_bytes": len(raw),
                }
            )
    rows.sort(key=lambda row: str(row["path"]))
    return rows


def verify_local_runtime_binding(
    *, artifact_directory: Path, runtime_root: Path
) -> LocalRuntimeBindingEvidenceV1:
    """Verify exact local bytes without importing the extension or timing work."""

    artifact_directory = _require_real_owner_directory(
        artifact_directory, name="native artifact directory"
    )
    runtime_root = _require_real_owner_directory(
        runtime_root, name="native runtime root"
    )
    artifact_rows, payloads = _artifact_rows(artifact_directory)
    _require_expected_rows(
        artifact_rows, EXPECTED_ARTIFACT_ROWS, name="artifact payload"
    )
    artifact_manifest_sha256 = _manifest_sha256(artifact_rows)
    if artifact_manifest_sha256 != EXPECTED_ARTIFACT_MANIFEST_SHA256:
        raise FullPipelineCPUPerformanceV1Error(
            "artifact payload manifest is not independently rederivable"
        )
    wheel_name = str(EXPECTED_ARTIFACT_ROWS[1]["path"])
    sbom_name = str(EXPECTED_ARTIFACT_ROWS[0]["path"])
    _verify_wheel(payloads[wheel_name])
    _verify_sbom(payloads[sbom_name])

    pyvenv = _read_owner_regular_file(
        runtime_root / "pyvenv.cfg",
        name="runtime pyvenv configuration",
        maximum_bytes=4096,
    )
    if (
        pyvenv != EXPECTED_PYVENV_BYTES
        or _sha256_bytes(pyvenv) != EXPECTED_PYVENV_SHA256
    ):
        raise FullPipelineCPUPerformanceV1Error("runtime pyvenv configuration changed")
    for relative, target in EXPECTED_INTERPRETER_LINKS.items():
        path = runtime_root / relative
        try:
            metadata = path.lstat()
            observed_target = os.readlink(path)
        except OSError as exc:
            raise FullPipelineCPUPerformanceV1Error(
                f"runtime interpreter link {relative} is unavailable"
            ) from exc
        if not stat.S_ISLNK(metadata.st_mode) or observed_target != target:
            raise FullPipelineCPUPerformanceV1Error(
                f"runtime interpreter link {relative} changed"
            )
    real_python = (runtime_root / "bin/python3.10").resolve(strict=True)
    if real_python != Path("/usr/bin/python3.10"):
        raise FullPipelineCPUPerformanceV1Error("runtime interpreter real path changed")
    python_raw = _read_owner_regular_file(
        real_python,
        name="runtime CPython executable",
        maximum_bytes=16 * 1024 * 1024,
        owner_uids=(0,),
    )
    python_sha256 = _sha256_bytes(python_raw)
    if python_sha256 != EXPECTED_PYTHON_SHA256:
        raise FullPipelineCPUPerformanceV1Error("runtime CPython executable changed")
    shared_library_raw = _read_owner_regular_file(
        Path("/usr/lib/x86_64-linux-gnu/libpython3.10.so.1.0"),
        name="runtime CPython shared library",
        maximum_bytes=16 * 1024 * 1024,
        owner_uids=(0,),
    )
    if _sha256_bytes(shared_library_raw) != EXPECTED_PYTHON_SHARED_LIBRARY_SHA256:
        raise FullPipelineCPUPerformanceV1Error(
            "runtime CPython shared library changed"
        )
    site_packages = _require_real_owner_directory(
        runtime_root / "lib/python3.10/site-packages",
        name="native runtime site-packages",
    )
    site_rows = _site_package_rows(site_packages)
    _require_expected_rows(site_rows, EXPECTED_SITE_ROWS, name="runtime site-packages")
    site_manifest_sha256 = _manifest_sha256(site_rows)
    if site_manifest_sha256 != EXPECTED_SITE_MANIFEST_SHA256:
        raise FullPipelineCPUPerformanceV1Error(
            "runtime site-packages manifest is not independently rederivable"
        )
    runtime_rows: list[dict[str, object]] = [
        {
            "kind": "file",
            "path": "pyvenv.cfg",
            "sha256": EXPECTED_PYVENV_SHA256,
            "size_bytes": len(pyvenv),
        }
    ]
    runtime_rows.extend(
        {"kind": "symlink", "path": relative, "target": target}
        for relative, target in EXPECTED_INTERPRETER_LINKS.items()
    )
    runtime_rows.extend(
        {
            "kind": "file",
            "path": f"lib/python3.10/site-packages/{row['path']}",
            "sha256": row["sha256"],
            "size_bytes": row["size_bytes"],
        }
        for row in site_rows
    )
    runtime_scope_manifest_sha256 = _manifest_sha256(runtime_rows)
    if runtime_scope_manifest_sha256 != EXPECTED_RUNTIME_SCOPE_MANIFEST_SHA256:
        raise FullPipelineCPUPerformanceV1Error(
            "runtime scope manifest is not independently rederivable"
        )
    native_extension_sha256 = str(EXPECTED_SITE_ROWS[-1]["sha256"])
    return LocalRuntimeBindingEvidenceV1(
        artifact_manifest_sha256=artifact_manifest_sha256,
        runtime_scope_manifest_sha256=runtime_scope_manifest_sha256,
        site_packages_manifest_sha256=site_manifest_sha256,
        python_executable_sha256=python_sha256,
        native_extension_sha256=native_extension_sha256,
    )


def _paired_schedule(
    *, phase: str, count: int
) -> tuple[tuple[str, int, int, str], ...]:
    if phase not in {"warmup", "sample"} or type(count) is not int or count < 0:
        raise FullPipelineCPUPerformanceV1Error("paired schedule request is invalid")
    rows: list[tuple[str, int, int, str]] = []
    for ordinal in range(count):
        order = BACKENDS if ordinal % 2 == 0 else tuple(reversed(BACKENDS))
        rows.extend(
            (phase, ordinal, position, backend)
            for position, backend in enumerate(order)
        )
    return tuple(rows)


def _require_digest(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FullPipelineCPUPerformanceV1Error(f"{name} is not SHA-256")
    return value


def _validate_session_metadata(document: object, *, backend: str) -> None:
    if type(document) is not dict:
        raise FullPipelineCPUPerformanceV1Error(
            "test-double prepared-session metadata must be an exact dict"
        )
    if (
        document.get("backend") != backend
        or document.get("candidate_denominator") != 64
        or document.get("persistent_native_context") is not True
        or document.get("context_reused_across_runs") is not True
        or document.get("scientific_result_cached") is not False
        or document.get("result_dependent_input_consumed") is not False
        or document.get("caller_science_transport_consumed") is not False
        or document.get("synthetic_only_acknowledgment")
        != SYNTHETIC_ONLY_ACKNOWLEDGMENT
    ):
        raise FullPipelineCPUPerformanceV1Error(
            "test-double prepared-session metadata is cross-wired"
        )
    for field in EXPECTED_SESSION_AUTHORITY_FALSE_FIELDS:
        if document.get(field) is not False:
            raise FullPipelineCPUPerformanceV1Error(
                f"test-double prepared-session granted {field}"
            )


def _validate_evidence(document: object, *, backend: str) -> _ValidatedEvidence:
    if type(document) is not dict:
        raise FullPipelineCPUPerformanceV1Error(
            "test-double full-pipeline evidence must be an exact dict"
        )
    candidates = document.get("candidates")
    if (
        document.get("backend") != backend
        or document.get("consumer") != CONSUMER_SURFACE
        or document.get("candidate_denominator") != 64
        or type(candidates) is not list
        or len(candidates) != 64
        or document.get("repository_scientific_decision_sha256")
        != EXPECTED_DECISION_SHA256
        or document.get("denominator_preserved") is not True
        or document.get("result_dependent_input_consumed") is not False
        or document.get("operator_second_opinion_authorized") is not False
    ):
        raise FullPipelineCPUPerformanceV1Error(
            "test-double full-pipeline evidence is cross-wired"
        )
    for field in EXPECTED_EVIDENCE_AUTHORITY_FALSE_FIELDS:
        if document.get(field) is not False:
            raise FullPipelineCPUPerformanceV1Error(
                f"test-double full-pipeline evidence granted {field}"
            )
    for field, expected in EXPECTED_STAGE_COUNTS.items():
        if document.get(field) != expected:
            raise FullPipelineCPUPerformanceV1Error(
                f"test-double full-pipeline stage count {field} changed"
            )
    for field, expected in EXPECTED_RANK_SELECTION.items():
        value = document.get(field)
        if type(value) is not list or tuple(value) != expected:
            raise FullPipelineCPUPerformanceV1Error(
                f"test-double full-pipeline rank selection {field} changed"
            )
    for field, expected in EXPECTED_SOURCE_IDENTITIES.items():
        if document.get(field) != expected:
            raise FullPipelineCPUPerformanceV1Error(
                f"test-double full-pipeline source identity {field} changed"
            )
    for index, candidate in enumerate(candidates):
        if type(candidate) is not dict or candidate.get("slot_index") != index:
            raise FullPipelineCPUPerformanceV1Error(
                "test-double candidate denominator is reordered"
            )
        scorer = candidate.get("scorer_v1")
        validity = candidate.get("validity")
        ranking = candidate.get("ranking")
        lineage = candidate.get("lineage")
        if (
            type(scorer) is not dict
            or frozenset(scorer) != EXPECTED_SCORER_FIELDS
            or type(validity) is not dict
            or frozenset(validity) != EXPECTED_VALIDITY_FIELDS
            or type(ranking) is not dict
            or frozenset(ranking) != EXPECTED_RANKING_FIELDS
            or type(lineage) is not dict
        ):
            raise FullPipelineCPUPerformanceV1Error(
                "test-double scorer, validity, ranking, or lineage evidence is incomplete"
            )
        terms = scorer.get("weighted_terms")
        if (
            type(terms) is not list
            or len(terms) != 8
            or any(type(term) is not float or not math.isfinite(term) for term in terms)
        ):
            raise FullPipelineCPUPerformanceV1Error(
                "test-double complete ScorerV1 term receipt changed"
            )
        total_score = scorer.get("total_score")
        scorer_counts = (
            scorer.get("receptor_candidate_pair_count"),
            scorer.get("ligand_pair_count"),
            scorer.get("hbond_count"),
            scorer.get("hydrophobic_contact_count"),
            scorer.get("buried_polar_count"),
        )
        if (
            type(scorer.get("status")) is not int
            or scorer["status"] < 0
            or type(scorer.get("failure_code")) is not int
            or scorer["failure_code"] < 0
            or type(total_score) is not float
            or not math.isfinite(total_score)
            or not math.isclose(
                total_score,
                math.fsum(terms),
                rel_tol=4.0e-12,
                abs_tol=1.0e-11,
            )
            or any(type(value) is not int or value < 0 for value in scorer_counts)
            or type(ranking.get("rank_eligible")) is not bool
            or type(ranking.get("valid_rank_eligible")) is not bool
            or (ranking["valid_rank_eligible"] and not ranking["rank_eligible"])
            or type(ranking.get("stable_rank")) is not int
            or ranking["stable_rank"] < 0
            or type(ranking.get("stable_valid_rank")) is not int
            or ranking["stable_valid_rank"] < 0
            or type(ranking.get("total_score")) is not float
            or not math.isfinite(ranking["total_score"])
            or not math.isclose(
                ranking["total_score"],
                total_score,
                rel_tol=4.0e-12,
                abs_tol=1.0e-11,
            )
        ):
            raise FullPipelineCPUPerformanceV1Error(
                "test-double ScorerV1 or ranking semantics changed"
            )
        _require_digest(
            ranking.get("coordinate_sha256"),
            name="candidate ranking coordinate",
        )
        for field, value in validity.items():
            if field in EXPECTED_VALIDITY_FLOAT_FIELDS:
                if type(value) is not float or not math.isfinite(value):
                    raise FullPipelineCPUPerformanceV1Error(
                        "test-double validity numeric evidence changed"
                    )
            elif type(value) is not int or value < 0:
                raise FullPipelineCPUPerformanceV1Error(
                    "test-double validity numeric evidence changed"
                )
        for field in REQUIRED_LINEAGE_DIGEST_FIELDS:
            _require_digest(lineage.get(field), name=f"candidate lineage {field}")
        for field in REQUIRED_EXACT_CANDIDATE_SOURCE_DIGEST_FIELDS:
            _require_digest(candidate.get(field), name=f"candidate source {field}")
    return _ValidatedEvidence(
        document=document,
        pipeline_receipt_sha256=_require_digest(
            document.get("pipeline_receipt_sha256"), name="pipeline receipt"
        ),
        scientific_projection_sha256=_require_digest(
            document.get("scientific_projection_sha256"),
            name="scientific projection",
        ),
    )


def _compare_scientific_values(
    baseline: object,
    experimental: object,
    *,
    path: str,
) -> tuple[int, float, float]:
    if type(baseline) is not type(experimental):
        raise FullPipelineCPUPerformanceV1Error(
            f"cross-backend scientific parity changed at {path}"
        )
    if type(baseline) is dict:
        if frozenset(baseline) != frozenset(experimental):
            raise FullPipelineCPUPerformanceV1Error(
                f"cross-backend scientific parity changed at {path}"
            )
        compared = 0
        maximum_absolute = 0.0
        maximum_scaled = 0.0
        for key in sorted(baseline):
            if type(key) is not str:
                raise FullPipelineCPUPerformanceV1Error(
                    f"cross-backend scientific parity changed at {path}"
                )
            if key == "producer_backend" or (
                key.endswith("sha256")
                and key not in REQUIRED_EXACT_CANDIDATE_SOURCE_DIGEST_FIELDS
            ):
                continue
            count, absolute, scaled = _compare_scientific_values(
                baseline[key],
                experimental[key],
                path=f"{path}.{key}",
            )
            compared += count
            maximum_absolute = max(maximum_absolute, absolute)
            maximum_scaled = max(maximum_scaled, scaled)
        return compared, maximum_absolute, maximum_scaled
    if type(baseline) is list:
        if len(baseline) != len(experimental):
            raise FullPipelineCPUPerformanceV1Error(
                f"cross-backend scientific parity changed at {path}"
            )
        compared = 0
        maximum_absolute = 0.0
        maximum_scaled = 0.0
        for index, (baseline_item, experimental_item) in enumerate(
            zip(baseline, experimental, strict=True)
        ):
            count, absolute, scaled = _compare_scientific_values(
                baseline_item,
                experimental_item,
                path=f"{path}[{index}]",
            )
            compared += count
            maximum_absolute = max(maximum_absolute, absolute)
            maximum_scaled = max(maximum_scaled, scaled)
        return compared, maximum_absolute, maximum_scaled
    if type(baseline) is float:
        if not math.isfinite(baseline) or not math.isfinite(experimental):
            raise FullPipelineCPUPerformanceV1Error(
                f"cross-backend scientific parity changed at {path}"
            )
        absolute = abs(baseline - experimental)
        scaled = absolute / max(abs(baseline), abs(experimental), 1.0)
        if not math.isclose(
            baseline,
            experimental,
            rel_tol=PARITY_RELATIVE_TOLERANCE,
            abs_tol=PARITY_ABSOLUTE_TOLERANCE,
        ):
            raise FullPipelineCPUPerformanceV1Error(
                f"cross-backend scientific parity changed at {path}"
            )
        return 1, absolute, scaled
    if type(baseline) not in {bool, int, str, type(None)} or baseline != experimental:
        raise FullPipelineCPUPerformanceV1Error(
            f"cross-backend scientific parity changed at {path}"
        )
    return 0, 0.0, 0.0


def _compare_backend_evidence(
    baseline: _ValidatedEvidence,
    experimental: _ValidatedEvidence,
    *,
    phase: str,
    ordinal: int,
) -> Mapping[str, object]:
    baseline_candidates = baseline.document["candidates"]
    experimental_candidates = experimental.document["candidates"]
    compared, maximum_absolute, maximum_scaled = _compare_scientific_values(
        baseline_candidates,
        experimental_candidates,
        path="candidates",
    )
    if compared != EXPECTED_PARITY_F64_COUNT:
        raise FullPipelineCPUPerformanceV1Error(
            "cross-backend scientific parity f64 denominator changed"
        )
    return MappingProxyType(
        {
            "phase": phase,
            "pair_ordinal": ordinal,
            "compared_f64_count": compared,
            "maximum_absolute_difference": maximum_absolute,
            "maximum_scaled_difference": maximum_scaled,
            "baseline_scientific_projection_sha256": (
                baseline.scientific_projection_sha256
            ),
            "experimental_scientific_projection_sha256": (
                experimental.scientific_projection_sha256
            ),
            "exact_status_failure_rank_parity": True,
            "full_numeric_parity": True,
        }
    )


def _nearest_rank(values: Sequence[int], *, numerator: int) -> int:
    if not values or any(type(value) is not int or value <= 0 for value in values):
        raise FullPipelineCPUPerformanceV1Error("timing sample is invalid")
    rank = (len(values) * numerator + PERCENTILE_DENOMINATOR - 1) // (
        PERCENTILE_DENOMINATOR
    )
    return sorted(values)[max(1, rank) - 1]


def _run_injected_test_double(
    *,
    session_factory: Callable[[str], _PreparedSession],
    wall_clock_ns: Callable[[], int],
    process_clock_ns: Callable[[], int],
) -> TestDoubleMeasurementReceiptV1:
    """Exercise the frozen measurement core with injected sessions and clocks.

    This private helper is intentionally unavailable from the CLI and cannot
    produce live qualification evidence.  Unit tests use it to prove schedule,
    persistent-session reuse, timing boundaries, and fail-closed validation.
    """

    sessions: dict[str, _PreparedSession] = {}
    for backend in BACKENDS:
        session = session_factory(backend)
        _validate_session_metadata(session.describe(), backend=backend)
        sessions[backend] = session

    backend_receipts: dict[str, str] = {}
    parity_observations: list[Mapping[str, object]] = []
    warmup_pair: dict[str, _ValidatedEvidence] = {}
    for phase, ordinal, position, backend in _paired_schedule(
        phase="warmup", count=WARMUP_COUNT
    ):
        evidence = sessions[backend].run(surface=CONSUMER_SURFACE)
        validated = _validate_evidence(evidence.to_dict(), backend=backend)
        receipt = validated.pipeline_receipt_sha256
        previous = backend_receipts.setdefault(backend, receipt)
        if previous != receipt:
            raise FullPipelineCPUPerformanceV1Error(
                "test-double backend receipt is not repeat-stable"
            )
        warmup_pair[backend] = validated
        if position == 1:
            parity_observations.append(
                _compare_backend_evidence(
                    warmup_pair[BASELINE_BACKEND],
                    warmup_pair[EXPERIMENTAL_BACKEND],
                    phase=phase,
                    ordinal=ordinal,
                )
            )
            warmup_pair = {}

    observations: list[Mapping[str, object]] = []
    schedule_rows: list[dict[str, object]] = []
    sample_pair: dict[str, _ValidatedEvidence] = {}
    for phase, ordinal, position, backend in _paired_schedule(
        phase="sample", count=SAMPLE_COUNT
    ):
        wall_start = wall_clock_ns()
        process_start = process_clock_ns()
        evidence = sessions[backend].run(surface=CONSUMER_SURFACE)
        validated = _validate_evidence(evidence.to_dict(), backend=backend)
        receipt = validated.pipeline_receipt_sha256
        process_end = process_clock_ns()
        wall_end = wall_clock_ns()
        if any(
            type(value) is not int
            for value in (wall_start, process_start, process_end, wall_end)
        ):
            raise FullPipelineCPUPerformanceV1Error(
                "test-double clock returned a non-integer"
            )
        wall_duration = wall_end - wall_start
        process_duration = process_end - process_start
        if wall_duration <= 0 or process_duration <= 0:
            raise FullPipelineCPUPerformanceV1Error(
                "test-double timing duration is not positive"
            )
        if backend_receipts.get(backend) != receipt:
            raise FullPipelineCPUPerformanceV1Error(
                "test-double backend receipt changed during sampling"
            )
        row: Mapping[str, object] = MappingProxyType(
            {
                "phase": phase,
                "pair_ordinal": ordinal,
                "position": position,
                "backend": backend,
                "wall_duration_ns": wall_duration,
                "process_duration_ns": process_duration,
                "pipeline_receipt_sha256": receipt,
            }
        )
        observations.append(row)
        schedule_rows.append(
            {
                "phase": phase,
                "pair_ordinal": ordinal,
                "position": position,
                "backend": backend,
            }
        )
        sample_pair[backend] = validated
        if position == 1:
            parity_observations.append(
                _compare_backend_evidence(
                    sample_pair[BASELINE_BACKEND],
                    sample_pair[EXPERIMENTAL_BACKEND],
                    phase=phase,
                    ordinal=ordinal,
                )
            )
            sample_pair = {}
    summaries: dict[str, Mapping[str, int]] = {}
    for backend in BACKENDS:
        backend_rows = [row for row in observations if row["backend"] == backend]
        if len(backend_rows) != SAMPLE_COUNT:
            raise FullPipelineCPUPerformanceV1Error(
                "test-double sample denominator changed"
            )
        wall_values = [int(row["wall_duration_ns"]) for row in backend_rows]
        process_values = [int(row["process_duration_ns"]) for row in backend_rows]
        summaries[backend] = MappingProxyType(
            {
                "wall_p50_ns": _nearest_rank(wall_values, numerator=50),
                "wall_p95_ns": _nearest_rank(wall_values, numerator=95),
                "process_p50_ns": _nearest_rank(process_values, numerator=50),
                "process_p95_ns": _nearest_rank(process_values, numerator=95),
            }
        )
    return TestDoubleMeasurementReceiptV1(
        observations=tuple(observations),
        parity_observations=tuple(parity_observations),
        summaries=MappingProxyType(summaries),
        schedule_sha256=_sha256_bytes(_canonical_json_bytes(schedule_rows)),
        backend_pipeline_receipts=MappingProxyType(dict(backend_receipts)),
    )


def run_live_full_pipeline_cpu_performance_v1(
    *_args: object, **_kwargs: object
) -> None:
    """Fail closed until an exact-source activation contract is merged."""

    raise FullPipelineCPUPerformanceV1Error(
        "full-pipeline CPU performance v1 execution is not activated"
    )


__all__ = [
    "FullPipelineCPUPerformanceV1Error",
    "LOCAL_RUNTIME_EVIDENCE_SCHEMA_ID",
    "LocalRuntimeBindingEvidenceV1",
    "PROFILE_ID",
    "PROFILE_SCHEMA_ID",
    "PROFILE_SHA256",
    "SYNTHETIC_ONLY_ACKNOWLEDGMENT",
    "TestDoubleMeasurementReceiptV1",
    "run_live_full_pipeline_cpu_performance_v1",
    "verify_local_runtime_binding",
]
